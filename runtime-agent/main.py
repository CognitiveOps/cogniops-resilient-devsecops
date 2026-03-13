"""
runtime-agent – CogniOps Runtime Agent (Phase 0 + ADK bootstrap).

Endpoints:
  POST /events/runtime   – Pub/Sub push receiver (runtime event pipeline)
  GET  /healthz           – Liveness probe for Cloud Run
  GET  /agent/info        – ADK agent metadata (Step 1+)

Pipeline:  Event → Perception → Planning → Guard → Execution → (BQ write)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from execution.executor import execute
from guard.policy_check import check_policy
from models.schemas import (
    ALLOWED_EVENT_TYPES_PHASE0,
    DecisionType,
    PubSubPushEnvelope,
    RuntimeEvent,
)
from perception.handler import perceive
from planning.playbook import select_playbook
from storage.bigquery_writer import build_decision_row, write_decision
from telemetry.agentops_client import trace_pipeline
from telemetry.policy_refs import get_policy_refs
from telemetry.trace_emitter import build_action_trace, emit_action_trace

# ── Logging ──────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("runtime-agent")

# ── FastAPI app ──────────────────────────────────────────────────────

app = FastAPI(
    title="CogniOps Runtime Agent",
    description="Runtime agent with ADK cognitive planning (shadow mode)",
    version="0.2.0",
)


# ── Health check ─────────────────────────────────────────────────────


@app.get("/healthz")
async def healthz():
    """Liveness / readiness probe for Cloud Run."""
    return {"status": "ok", "mode": "shadow", "phase": 0}


# ── Pub/Sub push endpoint ───────────────────────────────────────────


@app.post("/events/runtime")
async def receive_runtime_event(request: Request):
    """
    Receive a Pub/Sub push message, decode the runtime event,
    and run the Phase 0 pipeline:
      Perception → Planning → Guard → Execution

    Returns 200 on success (acknowledges the Pub/Sub message).
    Returns 400 on validation errors (non-retryable — prevents infinite retry).
    Returns 500 on unexpected errors (retryable — Pub/Sub will redeliver).
    """
    # ── 1. Parse Pub/Sub push envelope ───────────────────────────────
    try:
        body = await request.json()
        envelope = PubSubPushEnvelope(**body)
    except Exception as exc:
        logger.warning("Invalid Pub/Sub envelope: %s", exc)
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_pubsub_envelope", "message": str(exc)},
        )

    # ── 2. Base64 decode the event payload ───────────────────────────
    try:
        raw_data = base64.b64decode(envelope.message.data)
        event_payload = json.loads(raw_data)
    except Exception as exc:
        logger.warning("Cannot decode Pub/Sub message data: %s", exc)
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_base64_payload", "message": str(exc)},
        )

    # ── 3. Validate against runtime-event-contract schema ────────────
    try:
        event = RuntimeEvent(**event_payload)
    except Exception as exc:
        logger.warning("Event validation failed: %s", exc)
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_event_schema", "message": str(exc)},
        )

    # Warn on unknown event types but still process them
    if event.event_type not in ALLOWED_EVENT_TYPES_PHASE0:
        logger.warning(
            "Unknown event_type '%s' (allowed: %s) — processing anyway",
            event.event_type,
            ", ".join(sorted(ALLOWED_EVENT_TYPES_PHASE0)),
        )

    logger.info(
        "Received event: id=%s type=%s source=%s",
        event.event_id,
        event.event_type,
        event.source,
    )

    # ── 4–7. Pipeline wrapped in AgentOps trace ─────────────────────
    t_start = time.monotonic()
    t_start_epoch = time.time()

    with trace_pipeline(event.event_id) as trace:

        # ── 4. Perception ────────────────────────────────────────────
        anomaly = perceive(event)

        # ── 5. Planning ──────────────────────────────────────────────
        decision = select_playbook(anomaly)

        # ── 5b. Enrich with ISO/NIST control references ─────────────
        try:
            decision_enum = DecisionType(decision.decision.value)
            policy_refs = get_policy_refs(decision_enum)
            if policy_refs:
                decision.policy_refs = policy_refs
        except (ValueError, KeyError):
            pass  # Unknown decision type — keep existing policy_refs

        # ── 6. Guard ─────────────────────────────────────────────────
        verdict = check_policy(decision)

        # ── 7. Execution ─────────────────────────────────────────────
        result = execute(decision, verdict)

        # Store trace metadata for AgentOps
        trace["decision"] = decision.decision.value
        trace["executed"] = result.decision_executed

    agentops_trace_id = trace.get("trace_id")

    # ── 8. Write decision to BigQuery ────────────────────────────────
    processed_at = datetime.now(timezone.utc)

    row = build_decision_row(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        source=event.source,
        context=event.context.model_dump() if event.context else None,
        decision=decision.decision.value,
        decision_executed=result.decision_executed,
        rationale=decision.rationale,
        policy_refs=decision.policy_refs,
        agentops_trace_id=agentops_trace_id,
    )

    bq_ok = write_decision(row)

    # ── 8b. Build + emit ActionTrace CloudEvent ──────────────────────
    action_trace = build_action_trace(
        event_id=event.event_id,
        event_type=event.event_type,
        scenario_id=event.context.scenario_id or "unknown",
        run_id=event.context.run_id or event.event_id,
        mode="shadow",
        decision=decision.decision.value,
        rationale=decision.rationale,
        policy_refs=decision.policy_refs,
        severity=anomaly.severity,
        risk_score=anomaly.risk_score,
        guard_approved=verdict.approved,
        guard_reason=verdict.reason,
        executed=result.decision_executed,
        agentops_trace_id=agentops_trace_id or "",
        t_start_epoch=t_start_epoch,
    )

    trace_ok = emit_action_trace(action_trace)

    # ── 9. Build response ────────────────────────────────────────────
    response_body = {
        "status": "accepted",
        "event_id": event.event_id,
        "decision": decision.decision.value,
        "decision_executed": result.decision_executed,
        "policy_refs": decision.policy_refs,
        "mode": "shadow",
        "processed_at": processed_at.isoformat(),
        "agentops_trace_id": agentops_trace_id,
        "bq_written": bq_ok,
        "trace_valid": trace_ok,
    }

    logger.info(
        "Pipeline complete: event_id=%s decision=%s executed=%s bq=%s trace=%s",
        event.event_id,
        decision.decision.value,
        result.decision_executed,
        bq_ok,
        trace_ok,
    )

    return JSONResponse(status_code=200, content=response_body)


# ── ADK Agent Integration (Step 1+) ─────────────────────────────────


@app.get("/agent/info")
async def agent_info():
    """Return ADK agent metadata — confirms the cognitive module loads."""
    try:
        from agent.cogniops_agent import cogniops_agent

        tool_names = [
            t.__name__ if callable(t) else str(t) for t in cogniops_agent.tools
        ]
        return {
            "agent_name": cogniops_agent.name,
            "model": str(cogniops_agent.model),
            "tools": tool_names,
            "has_guard": cogniops_agent.before_tool_callback is not None,
            "status": "loaded",
        }
    except Exception as exc:
        logger.warning("ADK agent not available: %s", exc)
        return {"status": "not_loaded", "detail": str(exc)}

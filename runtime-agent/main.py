"""
runtime-agent – CogniOps Runtime Agent (ADK Cognitive Pipeline).

Endpoints:
  POST /events/runtime   – Pub/Sub push receiver (runtime event pipeline)
  GET  /health            – Liveness probe for Cloud Run
  GET  /agent/info        – ADK agent metadata

Pipeline:  Event → ADK Runner (Perception → Planning → Guard → Execution) → BQ → Trace
Fallback:  ADK failure → Phase 0 stubs (NO_OP, zero risk)
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
from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.cogniops_agent import cogniops_agent
from models.schemas import (
    ALLOWED_EVENT_TYPES_PHASE0,
    DecisionType,
    PubSubPushEnvelope,
    RuntimeEvent,
)
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

COGNIOPS_MODE = os.getenv("COGNIOPS_MODE", "shadow")

app = FastAPI(
    title="CogniOps Runtime Agent",
    description="Runtime agent with ADK cognitive planning (shadow mode)",
    version="0.3.0",
)

# ── ADK Runner ───────────────────────────────────────────────────────

runner = InMemoryRunner(agent=cogniops_agent, app_name="cogniops_runtime")
runner.auto_create_session = True


# ── Health check ─────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Liveness / readiness probe for Cloud Run."""
    return {"status": "ok", "mode": COGNIOPS_MODE, "version": "0.3.0"}


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

    # ── 4–7. ADK Cognitive Pipeline (with Phase 0 fallback) ───────────
    t_start = time.monotonic()
    t_start_epoch = time.time()

    # Defaults for fallback
    decision_str = "NO_OP"
    rationale = "ADK fallback — no action taken"
    policy_refs: list[str] = []
    decision_executed = False
    severity = 0.5
    risk_score = 0.5
    guard_approved = True
    guard_reason = "no guard evaluated"
    agentops_trace_id: str | None = None

    with trace_pipeline(event.event_id) as trace:
        try:
            # Build user message with full event context for the LLM agent
            user_text = (
                f"Anomaly detected: event_id={event.event_id} "
                f"event_type={event.event_type} source={event.source} "
                f"occurred_at={event.occurred_at.isoformat()} "
                f"scenario_id={event.context.scenario_id or 'unknown'} "
                f"status={event.context.status}"
            )
            if event.context.severity:
                user_text += f" severity={event.context.severity}"

            user_msg = types.Content(
                role="user",
                parts=[types.Part(text=user_text)],
            )

            # Run ADK agent pipeline
            last_tool_result: dict | None = None
            async for adk_event in runner.run_async(
                user_id="runtime-agent",
                session_id=event.event_id,
                new_message=user_msg,
            ):
                # Extract tool call results from ADK events
                if hasattr(adk_event, "content") and adk_event.content:
                    for part in adk_event.content.parts or []:
                        if (
                            hasattr(part, "function_response")
                            and part.function_response
                        ):
                            resp = part.function_response.response
                            if isinstance(resp, dict) and "action" in resp:
                                last_tool_result = resp

            # Extract decision from ADK tool result
            if last_tool_result:
                decision_str = last_tool_result.get("action", "NO_OP")
                rationale = last_tool_result.get("rationale", rationale)
                decision_executed = last_tool_result.get("executed", False)
                guard_approved = not last_tool_result.get("guard_blocked", False)
                if not guard_approved:
                    guard_reason = last_tool_result.get("guard_reason", "blocked")

        except Exception as exc:
            logger.error("ADK runner failed — falling back to NO_OP: %s", exc)
            decision_str = "NO_OP"
            rationale = f"ADK fallback — {exc}"
            decision_executed = False

        # Enrich with policy refs
        try:
            decision_enum = DecisionType(decision_str)
            policy_refs = get_policy_refs(decision_enum)
        except (ValueError, KeyError):
            pass

        # Store trace metadata for AgentOps
        trace["decision"] = decision_str
        trace["executed"] = decision_executed

    agentops_trace_id = trace.get("trace_id")

    # ── 8. Write decision to BigQuery ────────────────────────────────
    processed_at = datetime.now(timezone.utc)

    row = build_decision_row(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        source=event.source,
        context=event.context.model_dump() if event.context else None,
        decision=decision_str,
        decision_executed=decision_executed,
        rationale=rationale,
        policy_refs=policy_refs,
        agentops_trace_id=agentops_trace_id,
    )

    bq_ok = write_decision(row)

    # ── 8b. Build + emit ActionTrace CloudEvent ──────────────────────
    action_trace = build_action_trace(
        event_id=event.event_id,
        event_type=event.event_type,
        scenario_id=event.context.scenario_id or "unknown",
        run_id=event.context.run_id or event.event_id,
        mode=COGNIOPS_MODE,
        decision=decision_str,
        rationale=rationale,
        policy_refs=policy_refs,
        severity=severity,
        risk_score=risk_score,
        guard_approved=guard_approved,
        guard_reason=guard_reason,
        executed=decision_executed,
        agentops_trace_id=agentops_trace_id or "",
        t_start_epoch=t_start_epoch,
    )

    trace_ok = emit_action_trace(action_trace)

    # ── 9. Build response ────────────────────────────────────────────
    response_body = {
        "status": "accepted",
        "event_id": event.event_id,
        "decision": decision_str,
        "decision_executed": decision_executed,
        "policy_refs": policy_refs,
        "mode": COGNIOPS_MODE,
        "processed_at": processed_at.isoformat(),
        "agentops_trace_id": agentops_trace_id,
        "bq_written": bq_ok,
        "trace_valid": trace_ok,
    }

    logger.info(
        "Pipeline complete: event_id=%s decision=%s executed=%s bq=%s trace=%s",
        event.event_id,
        decision_str,
        decision_executed,
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

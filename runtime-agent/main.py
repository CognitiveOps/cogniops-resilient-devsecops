"""
runtime-agent – Phase 0 FastAPI application.

Endpoints:
  POST /events/runtime   – Pub/Sub push receiver (runtime event pipeline)
  GET  /healthz           – Liveness probe for Cloud Run

Pipeline:  Event → Perception → Planning → Guard → Execution → (BQ write)
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from execution.executor import execute
from guard.policy_check import check_policy
from models.schemas import (
    ALLOWED_EVENT_TYPES_PHASE0,
    PubSubPushEnvelope,
    RuntimeEvent,
)
from perception.handler import perceive
from planning.playbook import select_playbook
from storage.bigquery_writer import build_decision_row, write_decision
from telemetry.agentops_client import trace_pipeline

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
    description="Phase 0 – shadow mode runtime agent (no destructive actions)",
    version="0.1.0",
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
    with trace_pipeline(event.event_id) as trace:

        # ── 4. Perception ────────────────────────────────────────────
        anomaly = perceive(event)

        # ── 5. Planning ──────────────────────────────────────────────
        decision = select_playbook(anomaly)

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

    # ── 9. Build response ────────────────────────────────────────────
    response_body = {
        "status": "accepted",
        "event_id": event.event_id,
        "decision": decision.decision.value,
        "decision_executed": result.decision_executed,
        "mode": "shadow",
        "processed_at": processed_at.isoformat(),
        "agentops_trace_id": agentops_trace_id,
        "bq_written": bq_ok,
    }

    logger.info(
        "Pipeline complete: event_id=%s decision=%s executed=%s bq=%s trace=%s",
        event.event_id,
        decision.decision.value,
        result.decision_executed,
        bq_ok,
        agentops_trace_id,
    )

    return JSONResponse(status_code=200, content=response_body)

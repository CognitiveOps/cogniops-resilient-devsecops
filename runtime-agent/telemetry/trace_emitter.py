"""
ActionTrace emitter — bridges runtime decisions to the baseline explainability kit.

Builds CloudEvent-compliant ActionTraces from agent pipeline outputs,
validates them against the baseline schema, and emits to the ingest endpoint.

IMPORTANT: This module EXTENDS the baseline explainability kit —
it IMPORTS from ``baseline.explainability`` but never modifies it.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Optional

from baseline.explainability.cloudevents import new_cloudevent
from baseline.explainability.schema import validate_action_trace

logger = logging.getLogger("runtime-agent.explainability")

METRICS_INGEST_URL = os.getenv("METRICS_INGEST_URL", "")
CE_SOURCE = "cogniops/runtime-agent"
CE_TYPE = "cogniops.runtime.decision"


def build_action_trace(
    *,
    event_id: str,
    event_type: str,
    scenario_id: str,
    run_id: str,
    mode: str,
    decision: str,
    rationale: str,
    policy_refs: list[str],
    severity: float,
    risk_score: float,
    guard_approved: bool,
    guard_reason: str,
    executed: bool,
    agentops_trace_id: str = "",
    commit_sha: str = "",
    t_start_epoch: Optional[float] = None,
) -> dict[str, Any]:
    """Build a CloudEvent ActionTrace from pipeline outputs.

    The trace conforms to ``baseline.explainability.schema.REQUIRED_*`` contracts
    and can be validated with ``validate_action_trace()``.
    """
    now_epoch = time.time()
    t_recommend = t_start_epoch or now_epoch
    _commit_sha = commit_sha or os.getenv("COMMIT_SHA", "unknown")

    risk_level = (
        "critical" if risk_score >= 0.9
        else "high" if risk_score >= 0.7
        else "medium" if risk_score >= 0.4
        else "low"
    )

    data: dict[str, Any] = {
        "schema_version": "1.0",
        "scenario_id": scenario_id,
        "stage": "runtime_decision",
        "mode": mode,
        "run_id": run_id,
        "case_id": event_id,
        "actor": "cogniops_planning",
        "action": decision,
        "recommendation": decision,
        "decision": "approved" if guard_approved else "denied",
        "rationale": rationale,
        "risk": {
            "score": round(risk_score, 4),
            "level": risk_level,
        },
        "evidence": [
            {
                "event_type": event_type,
                "severity": round(severity, 4),
                "risk_score": round(risk_score, 4),
                "guard_approved": guard_approved,
                "guard_reason": guard_reason,
                "executed": executed,
            }
        ],
        "timestamps": {
            "t_recommend_epoch": t_recommend,
            "t_decision_epoch": now_epoch,
        },
        "provenance": {
            "commit_sha": _commit_sha,
            "agent": "cogniops_planning",
            "mode": mode,
            "agentops_trace_id": agentops_trace_id or "",
        },
        "otel": {
            "trace_id": agentops_trace_id or f"local-{uuid.uuid4().hex[:12]}",
        },
        "policy_refs": policy_refs,
    }

    trace = new_cloudevent(
        source=CE_SOURCE,
        type=CE_TYPE,
        data=data,
        subject=event_id,
    )
    return trace


def emit_action_trace(trace: dict[str, Any]) -> bool:
    """Validate and emit an ActionTrace CloudEvent.

    Returns True if the trace was valid and emission succeeded (or was skipped
    because no ingest URL is configured).
    Returns False if validation failed — the trace is logged but NOT emitted.
    """
    valid, missing = validate_action_trace(trace)
    if not valid:
        logger.error(
            "ActionTrace validation FAILED (missing: %s) — trace NOT emitted",
            missing,
        )
        return False

    logger.info(
        "ActionTrace valid: case_id=%s action=%s",
        trace.get("data", {}).get("case_id", "?"),
        trace.get("data", {}).get("action", "?"),
    )

    ingest_url = METRICS_INGEST_URL
    if not ingest_url:
        logger.debug("No METRICS_INGEST_URL — ActionTrace logged only")
        return True

    # Best-effort emit using baseline kit
    try:
        from baseline.explainability.emit import emit_cloudevent

        emit_cloudevent(ingest_url=ingest_url, cloudevent=trace)
        return True
    except Exception as exc:
        logger.warning("ActionTrace emission failed (best-effort): %s", exc)
        return True  # Validation passed — emission failure is non-fatal

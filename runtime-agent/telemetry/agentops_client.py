"""
AgentOps telemetry client – Phase 0 optional integration.

Traces the perception → planning → guard → execution pipeline.
Activated only when AGENTOPS_API_KEY is set AND AGENTOPS_ENABLED=true.
If not configured, all calls are silent no-ops.

Redaction policy:
  - No secrets, PQC keys, or full policy files are sent to AgentOps.
  - Only event metadata, decision outcomes, and trace IDs are emitted.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY", "")
AGENTOPS_ENABLED = os.getenv("AGENTOPS_ENABLED", "false").lower() == "true"

_initialized = False


def _ensure_init() -> bool:
    """
    Lazy-initialize AgentOps SDK if configured.
    Returns True if AgentOps is active, False otherwise.
    """
    global _initialized  # noqa: PLW0603

    if not AGENTOPS_ENABLED or not AGENTOPS_API_KEY:
        return False

    if _initialized:
        return True

    try:
        import agentops  # type: ignore[import-untyped]

        agentops.init(
            api_key=AGENTOPS_API_KEY,
            tags=["cogniops", "runtime-agent", "phase0"],
        )
        _initialized = True
        logger.info("AgentOps initialized (Phase 0 trace mode)")
        return True
    except Exception as exc:
        logger.warning("AgentOps init failed (continuing without tracing): %s", exc)
        return False


@contextmanager
def trace_pipeline(event_id: str) -> Generator[dict[str, Any], None, None]:
    """
    Context manager that wraps the agent pipeline in an AgentOps trace.

    Yields a dict where callers can store trace metadata; on exit the
    trace is finalized.  If AgentOps is disabled, yields a dict with
    a locally-generated trace_id and does nothing else.

    Usage:
        with trace_pipeline(event.event_id) as trace:
            # ... run pipeline ...
            trace["decision"] = "NO_OP"
        agentops_trace_id = trace.get("trace_id")
    """
    trace_ctx: dict[str, Any] = {"trace_id": None}

    if not _ensure_init():
        # Generate a local trace ID even when AgentOps is off
        trace_ctx["trace_id"] = f"local-{uuid.uuid4().hex[:12]}"
        yield trace_ctx
        return

    try:
        import agentops  # type: ignore[import-untyped]

        session = agentops.start_session(tags=[f"event:{event_id}"])
        trace_ctx["trace_id"] = (
            str(session.session_id)
            if hasattr(session, "session_id")
            else f"ao-{uuid.uuid4().hex[:12]}"
        )

        yield trace_ctx

        # Record final event metadata (redacted — no secrets)
        agentops.record(
            agentops.ActionEvent(
                action_type="pipeline_complete",
                params={
                    "event_id": event_id,
                    "decision": trace_ctx.get("decision", "unknown"),
                    "executed": trace_ctx.get("executed", False),
                    "mode": "shadow",
                },
            )
        )
        agentops.end_session("Success")

        logger.info(
            "AgentOps: trace completed for event_id=%s trace_id=%s",
            event_id,
            trace_ctx["trace_id"],
        )

    except Exception as exc:
        logger.warning("AgentOps trace error (non-fatal): %s", exc)
        if not trace_ctx["trace_id"]:
            trace_ctx["trace_id"] = f"err-{uuid.uuid4().hex[:12]}"
        yield trace_ctx

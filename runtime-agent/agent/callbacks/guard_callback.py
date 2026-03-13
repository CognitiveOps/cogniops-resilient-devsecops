"""ADK before_tool_callback — OPA + PQC policy guard for execution tools.

Runs before every tool the LLM tries to call.  For *observation* tools
(``perceive_anomaly``, ``query_recent_decisions``) the guard is a pass-through.
For *execution* tools (``no_action``, ``block_deployment``, ``rollback_deployment``,
``quarantine_artifact``, ``escalate_to_human``) the guard performs:

1. **OPA policy evaluation** — fail-closed (OPA down → deny).
2. **PQC integrity check** — only for S4/SS2 scenarios when artifact
   context is present.

If either check fails the tool call is **blocked**: the guard returns a
``dict`` that ADK treats as the tool result (the tool itself never runs).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger("runtime-agent.guard")

# Tools that are *observation-only* — guard always allows them.
_OBSERVATION_TOOLS = frozenset(
    {
        "perceive_anomaly",
        "query_recent_decisions",
    }
)

# Execution tools that require OPA + PQC guard.
_EXECUTION_TOOLS = frozenset(
    {
        "no_action",
        "block_deployment",
        "rollback_deployment",
        "quarantine_artifact",
        "escalate_to_human",
    }
)


# ── helpers ──────────────────────────────────────────────────────────


def _get_session_state(tool_context: ToolContext) -> dict[str, Any]:
    """Safely extract session state dict from the ADK tool context."""
    try:
        state = tool_context.state or {}
        return dict(state)
    except Exception:
        return {}


async def _run_opa_check(
    tool_name: str,
    args: dict[str, Any],
    session_state: dict[str, Any],
) -> Optional[dict]:
    """Run OPA policy evaluation.  Returns ``None`` on allow or a
    block-dict on deny/error (fail-closed)."""
    from agent.callbacks.opa_client import OpaResult, build_opa_input, opa_eval

    opa_input = build_opa_input(
        action=tool_name,
        args=args,
        session_state=session_state,
    )

    result: OpaResult = await opa_eval(opa_input)

    if not result.allowed:
        reason = (
            ", ".join(result.denials)
            if result.denials
            else (result.error or "OPA denied")
        )
        logger.warning(
            "Guard BLOCKED by OPA: tool=%s reason=%s",
            tool_name,
            reason,
        )
        return {
            "action": "NO_OP",
            "rationale": f"Guard blocked: OPA — {reason}",
            "executed": False,
            "guard_blocked": True,
            "guard_reason": "opa_violation",
            "guard_details": result.denials,
        }
    return None


async def _run_pqc_check(session_state: dict[str, Any]) -> Optional[dict]:
    """PQC integrity check for S4/SS2 scenarios.

    Returns ``None`` on pass or a block-dict on failure.
    Only executes when the session state contains an ``artifact_manifest``
    **and** the scenario is S4 or SS2.
    """
    scenario = str(session_state.get("scenario", "")).upper()
    if scenario not in ("S4", "SS2"):
        return None

    manifest_path = session_state.get("artifact_manifest")
    sig_path = session_state.get("artifact_signature")
    pub_path = session_state.get("artifact_public_key")

    if not (manifest_path and sig_path and pub_path):
        # No artifact context — nothing to verify
        return None

    try:
        from baseline.security.pqc.verify import (
            load_bytes,
            load_manifest,
            verify_manifest,
        )

        backend = os.getenv("PQC_BACKEND", "oqs")
        algorithm = os.getenv("PQC_ALGORITHM", "Dilithium2")
        replay_cutoff = float(os.getenv("PQC_REPLAY_CUTOFF_SEC", "0"))

        manifest = load_manifest(manifest_path)
        signature = load_bytes(sig_path)
        public_key = load_bytes(pub_path)

        verified, reason, _, _ = verify_manifest(
            backend,
            algorithm,
            manifest,
            signature,
            public_key,
            replay_cutoff,
        )

        if not verified:
            logger.warning("Guard BLOCKED by PQC: reason=%s", reason)
            return {
                "action": "NO_OP",
                "rationale": f"Guard blocked: PQC integrity — {reason}",
                "executed": False,
                "guard_blocked": True,
                "guard_reason": "pqc_failure",
                "guard_details": [reason],
            }

        return None

    except Exception as exc:
        logger.error("PQC check error (fail-closed): %s", exc)
        return {
            "action": "NO_OP",
            "rationale": f"Guard blocked: PQC error — {exc}",
            "executed": False,
            "guard_blocked": True,
            "guard_reason": "pqc_error",
            "guard_details": [str(exc)],
        }


# ── main callback ────────────────────────────────────────────────────


def guard_callback(
    *,
    tool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Policy guard invoked before every tool execution.

    - Observation tools → always allowed.
    - Execution tools → OPA check, then PQC check (S4/SS2).
    - Any guard failure → block (return dict as tool result).

    Returns:
        None to allow execution, or dict to block (skip tool, use dict as result).
    """
    tool_name: str = getattr(tool, "name", "") or (
        tool.__name__ if callable(tool) else str(tool)
    )

    # Pass-through for observation tools
    if tool_name in _OBSERVATION_TOOLS:
        logger.debug("Guard pass-through: observation tool=%s", tool_name)
        return None

    # Only guard known execution tools (safety: unknown tools are blocked)
    if tool_name not in _EXECUTION_TOOLS:
        logger.warning("Guard BLOCKED: unknown tool=%s", tool_name)
        return {
            "action": "NO_OP",
            "rationale": f"Guard blocked: unknown tool '{tool_name}'",
            "executed": False,
            "guard_blocked": True,
            "guard_reason": "unknown_tool",
        }

    session_state = _get_session_state(tool_context)

    # Run async checks in the current event loop (or create one)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # ADK callbacks may already be inside an event loop — schedule as task
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                asyncio.run, _async_guard(tool_name, args, session_state)
            ).result(timeout=15)
    else:
        result = asyncio.run(_async_guard(tool_name, args, session_state))

    if result is not None:
        logger.info("Guard BLOCKED: tool=%s result=%s", tool_name, result)
    else:
        logger.info("Guard ALLOWED: tool=%s", tool_name)

    return result


async def _async_guard(
    tool_name: str,
    args: dict[str, Any],
    session_state: dict[str, Any],
) -> Optional[dict]:
    """Async orchestration of OPA + PQC checks."""
    # 1. OPA policy check
    opa_block = await _run_opa_check(tool_name, args, session_state)
    if opa_block is not None:
        return opa_block

    # 2. PQC integrity check (S4/SS2 only)
    pqc_block = await _run_pqc_check(session_state)
    if pqc_block is not None:
        return pqc_block

    return None

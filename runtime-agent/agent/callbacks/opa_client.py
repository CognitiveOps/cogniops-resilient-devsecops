"""OPA policy evaluation client for the guard callback.

Calls OPA REST API to evaluate runtime decisions against
organizational policies. Fail-closed: if OPA is unreachable
the result is *deny*.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("runtime-agent.guard.opa")

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
OPA_TIMEOUT_SEC = float(os.getenv("OPA_TIMEOUT_SEC", "5"))

# Policy path evaluated for runtime decisions
_POLICY_PATH = "/v1/data/cogniops/runtime/deny"


@dataclass
class OpaResult:
    """Outcome of an OPA policy evaluation."""

    allowed: bool
    denials: list[str] = field(default_factory=list)
    error: str | None = None


def build_opa_input(
    action: str,
    args: dict[str, Any],
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the OPA input document from tool context.

    The input mirrors the fields OPA policies expect:
      - action (the bounded action name)
      - scenario, severity, risk_score from session state
      - tool arguments (rationale, target, etc.)
    """
    state = session_state or {}
    return {
        "action": action,
        "scenario": state.get("scenario", "unknown"),
        "severity": state.get("severity", 0.5),
        "risk_score": state.get("risk_score", 0.5),
        "event_type": state.get("event_type", ""),
        "mode": os.getenv("COGNIOPS_MODE", "shadow"),
        "args": args,
    }


async def opa_eval(opa_input: dict[str, Any]) -> OpaResult:
    """Evaluate an OPA policy over HTTP.

    POST ``{OPA_URL}{_POLICY_PATH}`` with ``{"input": opa_input}``.
    OPA returns ``{"result": [<deny messages>]}``.

    On any error (network, timeout, non-200) the result is **deny**
    to ensure fail-closed semantics.
    """
    import httpx  # lazy import — not needed in tests that mock this fn

    url = f"{OPA_URL}{_POLICY_PATH}"
    payload = {"input": opa_input}

    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT_SEC) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            msg = f"OPA returned HTTP {resp.status_code}"
            logger.error(msg)
            return OpaResult(allowed=False, denials=[], error=msg)

        body = resp.json()
        denials: list[str] = body.get("result", []) or []

        if denials:
            logger.warning("OPA denied: %s", denials)
            return OpaResult(allowed=False, denials=denials)

        return OpaResult(allowed=True)

    except Exception as exc:
        msg = f"OPA unreachable: {exc}"
        logger.error(msg)
        return OpaResult(allowed=False, denials=[], error=msg)

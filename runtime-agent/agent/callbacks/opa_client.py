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

# Map ADK tool names → bounded action names used in OPA policies
_TOOL_TO_ACTION: dict[str, str] = {
    "no_action": "NO_OP",
    "block_deployment": "BLOCK",
    "rollback_deployment": "ROLLBACK",
    "quarantine_artifact": "QUARANTINE",
    "escalate_to_human": "ESCALATE",
}


@dataclass
class OpaResult:
    """Outcome of an OPA policy evaluation."""

    allowed: bool
    denials: list[str] = field(default_factory=list)
    error: str | None = None


def _get_oidc_token(audience: str) -> str | None:
    """Fetch an OIDC ID token for Cloud Run service-to-service auth.

    Uses the default service account on Cloud Run or
    GOOGLE_APPLICATION_CREDENTIALS locally.  Returns None
    on failure (caller falls back to unauthenticated).
    """
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        return google.oauth2.id_token.fetch_id_token(
            google.auth.transport.requests.Request(), audience
        )
    except Exception as exc:
        logger.debug("OIDC token fetch skipped: %s", exc)
        return None


def build_opa_input(
    action: str,
    args: dict[str, Any],
    session_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the OPA input document from tool context.

    The input mirrors the fields OPA policies expect:
      - action (the bounded action name, mapped from ADK tool name)
      - scenario, severity, risk_score from session state
      - tool arguments (rationale, target, etc.)
    """
    state = session_state or {}
    bounded_action = _TOOL_TO_ACTION.get(action, action)
    return {
        "action": bounded_action,
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

    Includes OIDC bearer token for Cloud Run service-to-service auth
    when OPA_URL is an https URL (Cloud Run).

    On any error (network, timeout, non-200) the result is **deny**
    to ensure fail-closed semantics.
    """
    import httpx  # lazy import — not needed in tests that mock this fn

    url = f"{OPA_URL}{_POLICY_PATH}"
    payload = {"input": opa_input}

    headers: dict[str, str] = {}
    if OPA_URL.startswith("https://"):
        token = _get_oidc_token(OPA_URL)
        if token:
            headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT_SEC) as client:
            resp = await client.post(url, json=payload, headers=headers)

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

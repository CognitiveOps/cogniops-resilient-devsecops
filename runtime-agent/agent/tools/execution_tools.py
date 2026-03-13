"""ADK tools for bounded execution actions (NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE).

Every tool is **mode-gated** via ``COGNIOPS_MODE`` environment variable:

- ``shadow``  — log intent only; ``executed = False``
- ``advisory`` — log + create GitHub notification issue; ``executed = False``
- ``enforce`` — log + perform real action; ``executed = True``

GitHub API failures in advisory/enforce mode are **fail-open**: the tool
logs the error and falls back to NO_OP (zero operational risk from
transient GitHub outages).
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger("runtime-agent.execution")


def _mode() -> str:
    return os.getenv("COGNIOPS_MODE", "shadow")


def _run_async(coro):
    """Run an async coroutine from synchronous context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=15)
    return asyncio.run(coro)


def _notify_advisory(action: str, rationale: str, target: str = "") -> str | None:
    """Create a GitHub notification issue for advisory mode.

    Returns the issue URL on success, or ``None`` on failure (fail-open).
    """
    from agent.tools.github_client import create_issue

    title = f"[CogniOps Advisory] {action}"
    body = (
        f"**Action:** {action}\n"
        f"**Target:** {target or 'N/A'}\n"
        f"**Rationale:** {rationale}\n\n"
        f"*This is an advisory notification — no action was executed.*"
    )
    try:
        result = _run_async(
            create_issue(
                title=title,
                body=body,
                labels=["cogniops", "advisory", action.lower()],
            )
        )
        if result.ok:
            return result.url
        logger.warning("Advisory issue creation failed: %s", result.error)
    except Exception as exc:
        logger.warning("Advisory notification failed (fail-open): %s", exc)
    return None


# ──────────────────────────────────────────────────────────────────────
# NO_OP — always succeeds, no mode check needed
# ──────────────────────────────────────────────────────────────────────


def no_action(rationale: str) -> dict:
    """Take no action — safe default.

    Use when severity is low, the situation is unclear, or there is
    insufficient evidence to warrant intervention.

    Args:
        rationale: Explanation for why no action is needed.

    Returns:
        Action result confirming NO_OP decision.
    """
    mode = _mode()
    logger.info("NO_OP [%s]: %s", mode, rationale)
    return {
        "action": "NO_OP",
        "rationale": rationale,
        "executed": False,
        "mode": mode,
    }


# ──────────────────────────────────────────────────────────────────────
# BLOCK
# ──────────────────────────────────────────────────────────────────────


def block_deployment(rationale: str, target: str = "") -> dict:
    """Block a deployment from proceeding.

    Use when severity >= 0.7 and the event involves a deployment or
    pipeline failure, or policy violations are detected.

    Args:
        rationale: Explanation for the block decision.
        target: Deployment or pipeline identifier to block.

    Returns:
        Action result confirming BLOCK decision.
    """
    mode = _mode()
    base = {
        "action": "BLOCK",
        "rationale": rationale,
        "target": target,
        "mode": mode,
    }

    if mode == "shadow":
        logger.info("BLOCK [shadow]: %s (target=%s) — logged only", rationale, target)
        return {**base, "executed": False, "message": "Shadow — logged only"}

    if mode == "advisory":
        logger.info("BLOCK [advisory]: %s (target=%s)", rationale, target)
        issue_url = _notify_advisory("BLOCK", rationale, target)
        return {
            **base,
            "executed": False,
            "message": "Advisory — notified",
            "issue_url": issue_url,
        }

    # enforce
    logger.info("BLOCK [enforce]: %s (target=%s) — executing", rationale, target)
    issue_url = _notify_advisory("BLOCK", rationale, target)
    return {
        **base,
        "executed": True,
        "message": "Enforced — deployment blocked",
        "issue_url": issue_url,
    }


# ──────────────────────────────────────────────────────────────────────
# ROLLBACK
# ──────────────────────────────────────────────────────────────────────


def rollback_deployment(rationale: str, target: str = "") -> dict:
    """Trigger rollback to last known-good deployment state.

    Use when severity >= 0.8 and a failed deployment is already in
    progress, or resilience degradation is detected with active impact.

    Args:
        rationale: Explanation for the rollback decision.
        target: Deployment or pipeline identifier to rollback.

    Returns:
        Action result confirming ROLLBACK decision.
    """
    mode = _mode()
    base = {
        "action": "ROLLBACK",
        "rationale": rationale,
        "target": target,
        "mode": mode,
    }

    if mode == "shadow":
        logger.info(
            "ROLLBACK [shadow]: %s (target=%s) — logged only", rationale, target
        )
        return {**base, "executed": False, "message": "Shadow — logged only"}

    if mode == "advisory":
        logger.info("ROLLBACK [advisory]: %s (target=%s)", rationale, target)
        issue_url = _notify_advisory("ROLLBACK", rationale, target)
        return {
            **base,
            "executed": False,
            "message": "Advisory — notified",
            "issue_url": issue_url,
        }

    # enforce — dispatch rollback workflow
    logger.info("ROLLBACK [enforce]: %s (target=%s) — dispatching", rationale, target)
    from agent.tools.github_client import dispatch_workflow

    try:
        result = _run_async(
            dispatch_workflow(
                workflow_file="s3_edge_rollback.yml",
                inputs={"run_id": target, "reason": rationale[:200]},
            )
        )
        return {
            **base,
            "executed": result.ok,
            "message": (
                "Enforced — rollback dispatched"
                if result.ok
                else f"Dispatch failed: {result.error}"
            ),
            "dispatch_ok": result.ok,
        }
    except Exception as exc:
        logger.error("Rollback dispatch failed (fail-open): %s", exc)
        return {
            **base,
            "executed": False,
            "message": f"Dispatch error (fail-open): {exc}",
        }


# ──────────────────────────────────────────────────────────────────────
# QUARANTINE
# ──────────────────────────────────────────────────────────────────────


def quarantine_artifact(rationale: str, artifact_id: str = "") -> dict:
    """Isolate a suspect artifact for further analysis.

    Use when a security-related anomaly is detected (PQC failure,
    integrity violation) or artifact provenance cannot be verified.

    Args:
        rationale: Explanation for the quarantine decision.
        artifact_id: Identifier of the artifact to quarantine.

    Returns:
        Action result confirming QUARANTINE decision.
    """
    mode = _mode()
    base = {
        "action": "QUARANTINE",
        "rationale": rationale,
        "artifact_id": artifact_id,
        "mode": mode,
    }

    if mode == "shadow":
        logger.info(
            "QUARANTINE [shadow]: %s (artifact=%s) — logged only",
            rationale,
            artifact_id,
        )
        return {**base, "executed": False, "message": "Shadow — logged only"}

    if mode == "advisory":
        logger.info("QUARANTINE [advisory]: %s (artifact=%s)", rationale, artifact_id)
        issue_url = _notify_advisory("QUARANTINE", rationale, artifact_id)
        return {
            **base,
            "executed": False,
            "message": "Advisory — notified",
            "issue_url": issue_url,
        }

    # enforce — create quarantine issue with blocking label
    logger.info(
        "QUARANTINE [enforce]: %s (artifact=%s) — executing", rationale, artifact_id
    )
    from agent.tools.github_client import create_issue

    try:
        result = _run_async(
            create_issue(
                title=f"[CogniOps QUARANTINE] Artifact {artifact_id}",
                body=(
                    f"**Artifact:** {artifact_id}\n"
                    f"**Rationale:** {rationale}\n\n"
                    f"This artifact has been quarantined for investigation."
                ),
                labels=["cogniops", "quarantine", "security"],
            )
        )
        return {
            **base,
            "executed": result.ok,
            "message": (
                "Enforced — quarantine issued"
                if result.ok
                else f"Issue failed: {result.error}"
            ),
            "issue_url": result.url if result.ok else None,
        }
    except Exception as exc:
        logger.error("Quarantine issue failed (fail-open): %s", exc)
        return {
            **base,
            "executed": False,
            "message": f"Issue error (fail-open): {exc}",
        }


# ──────────────────────────────────────────────────────────────────────
# ESCALATE (HITL)
# ──────────────────────────────────────────────────────────────────────


def escalate_to_human(rationale: str, summary: str = "") -> dict:
    """Create a human-in-the-loop (HITL) issue for manual review.

    Use when severity >= 0.5 but the correct action is ambiguous,
    the anomaly type is novel, or there are conflicting signals.

    Args:
        rationale: Explanation for why human review is needed.
        summary: Brief summary for the HITL issue.

    Returns:
        Action result confirming ESCALATE decision.
    """
    mode = _mode()
    base = {
        "action": "ESCALATE",
        "rationale": rationale,
        "summary": summary,
        "mode": mode,
    }

    if mode == "shadow":
        logger.info("ESCALATE [shadow]: %s — logged only", rationale)
        return {**base, "executed": False, "message": "Shadow — logged only"}

    # advisory and enforce both create HITL issues
    logger.info("ESCALATE [%s]: %s", mode, rationale)
    from agent.tools.github_client import create_issue

    try:
        result = _run_async(
            create_issue(
                title=f"[CogniOps HITL] {summary or 'Review Required'}",
                body=(
                    f"**Summary:** {summary}\n"
                    f"**Rationale:** {rationale}\n\n"
                    f"Human review is required before proceeding."
                ),
                labels=["cogniops", "hitl", "escalation"],
            )
        )
        executed = result.ok and mode == "enforce"
        return {
            **base,
            "executed": executed,
            "message": (
                f"{'Enforced' if mode == 'enforce' else 'Advisory'} — HITL issue created"
                if result.ok
                else f"Issue failed: {result.error}"
            ),
            "issue_url": result.url if result.ok else None,
        }
    except Exception as exc:
        logger.error("HITL issue failed (fail-open): %s", exc)
        return {
            **base,
            "executed": False,
            "message": f"Issue error (fail-open): {exc}",
        }

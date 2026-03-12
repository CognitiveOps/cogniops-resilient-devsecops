"""ADK tools for bounded execution actions (NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE)."""

from __future__ import annotations


def no_action(rationale: str) -> dict:
    """Take no action — safe default.

    Use when severity is low, the situation is unclear, or there is
    insufficient evidence to warrant intervention.

    Args:
        rationale: Explanation for why no action is needed.

    Returns:
        Action result confirming NO_OP decision.
    """
    return {
        "action": "NO_OP",
        "rationale": rationale,
        "executed": False,
    }


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
    return {
        "action": "BLOCK",
        "rationale": rationale,
        "target": target,
        "executed": False,
    }


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
    return {
        "action": "ROLLBACK",
        "rationale": rationale,
        "target": target,
        "executed": False,
    }


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
    return {
        "action": "QUARANTINE",
        "rationale": rationale,
        "artifact_id": artifact_id,
        "executed": False,
    }


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
    return {
        "action": "ESCALATE",
        "rationale": rationale,
        "summary": summary,
        "executed": False,
    }

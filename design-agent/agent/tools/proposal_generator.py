"""
Proposal Generator — assembles a validated DesignProposal from LLM output.

Deterministic tool: takes structured LLM analysis and packages it into
a DesignProposal with proper IDs, timestamps, and schema validation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("design-agent.proposal_generator")


def generate_proposal(
    intent: str,
    target_scenarios: list[str],
    analysis_summary: str,
    changes: list[dict],
    expected_impact: list[dict] | None = None,
    policy_refs: list[str] | None = None,
) -> dict:
    """Generate a structured design proposal from LLM analysis.

    Args:
        intent: Goal statement (e.g. "Reduce MTTR in S3").
        target_scenarios: Scenarios affected (e.g. ["S3", "SS2"]).
        analysis_summary: 2-5 sentence summary of the metric analysis.
        changes: List of proposed changes. Each dict must have:
            - change_type: one of threshold_adjustment, policy_addition,
              policy_modification, workflow_improvement, config_update
            - target_file: file to modify
            - description: what to change
            - proposed_value: the new value
            Optionally: current_value, rationale.
        expected_impact: Optional list of expected metric changes.
            Each dict: {metric_name, estimated_change, confidence}.
        policy_refs: Optional NIST/ISO control references.

    Returns:
        Serialized DesignProposal dict for validation and storage.
    """
    now = datetime.now(timezone.utc)
    proposal_id = f"design-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

    # Normalize changes
    normalized_changes = []
    for ch in changes:
        normalized_changes.append(
            {
                "change_type": ch.get("change_type", "config_update"),
                "target_file": ch.get("target_file", "unknown"),
                "description": ch.get("description", ""),
                "current_value": ch.get("current_value"),
                "proposed_value": ch.get("proposed_value", ""),
                "rationale": ch.get("rationale", ""),
            }
        )

    # Normalize expected impact
    normalized_impact = []
    for imp in expected_impact or []:
        normalized_impact.append(
            {
                "metric_name": imp.get("metric_name", ""),
                "estimated_change": imp.get("estimated_change", "unknown"),
                "confidence": min(max(float(imp.get("confidence", 0.5)), 0.0), 1.0),
            }
        )

    proposal = {
        "proposal_id": proposal_id,
        "created_at": now.isoformat(),
        "intent": intent,
        "target_scenarios": target_scenarios,
        "analysis_summary": analysis_summary,
        "changes": normalized_changes,
        "expected_impact": normalized_impact,
        "policy_refs": policy_refs or [],
        "validation": {
            "valid": False,
            "checks_passed": [],
            "errors": [],
            "warnings": [],
        },
        "requires_human_review": True,
    }

    logger.info("Generated proposal %s: %s", proposal_id, intent)
    return {"status": "proposal_generated", "proposal": proposal}


def no_proposal_needed(reason: str) -> dict:
    """Indicate that no structural changes are needed.

    Args:
        reason: Explanation of why no changes are warranted.

    Returns:
        Status dict with the reason logged.
    """
    logger.info("No proposal needed: %s", reason)
    return {"status": "no_proposal_needed", "reason": reason}

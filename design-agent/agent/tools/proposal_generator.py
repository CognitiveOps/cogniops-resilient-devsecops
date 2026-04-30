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
    target_scenarios: str,
    analysis_summary: str,
    changes: str,
    expected_impact: str = "",
    policy_refs: str = "",
    params: str = "",
) -> dict:
    """Generate a structured design proposal from LLM analysis.

    Args:
        intent: Goal statement (e.g. "Reduce MTTR in S3").
        target_scenarios: Comma-separated scenarios (e.g. "S3, SS2").
        analysis_summary: 2-5 sentence summary of the metric analysis.
        changes: JSON array of proposed changes. Each object must have:
            change_type, target_file, description, proposed_value.
            Optionally: current_value, rationale.
        expected_impact: JSON array of expected metric changes.
            Each object: {metric_name, estimated_change, confidence}.
        policy_refs: Comma-separated NIST/ISO control references.
        params: JSON object of concrete parameter overrides for workflows.
            Keys are environment variable names (e.g. S5_APPROVAL_DELAY_SEC),
            values are proposed string values (e.g. "3").
            These are fetched by agent-managed workflows at runtime.

    Returns:
        Serialized DesignProposal dict for validation and storage.
    """
    import json as _json

    now = datetime.now(timezone.utc)
    proposal_id = f"design-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"

    # Parse inputs
    scenarios_list = [s.strip() for s in target_scenarios.split(",") if s.strip()]

    try:
        changes_list = _json.loads(changes) if changes else []
    except _json.JSONDecodeError:
        changes_list = []

    try:
        impact_list = _json.loads(expected_impact) if expected_impact else []
    except _json.JSONDecodeError:
        impact_list = []

    refs_list = (
        [r.strip() for r in policy_refs.split(",") if r.strip()] if policy_refs else []
    )

    try:
        params_dict = _json.loads(params) if params else {}
    except _json.JSONDecodeError:
        params_dict = {}

    # Normalize changes
    normalized_changes = []
    for ch in changes_list:
        if not isinstance(ch, dict):
            continue
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
    for imp in impact_list:
        if not isinstance(imp, dict):
            continue
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
        "target_scenarios": scenarios_list,
        "analysis_summary": analysis_summary,
        "changes": normalized_changes,
        "expected_impact": normalized_impact,
        "params": params_dict,
        "policy_refs": refs_list,
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

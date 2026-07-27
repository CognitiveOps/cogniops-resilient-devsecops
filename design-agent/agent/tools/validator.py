"""
Validator — deterministic validation of DesignProposals.

Checks:
  1. Schema completeness (required fields, types)
  2. Change type validity (must be known ChangeType)
  3. Target file plausibility (non-empty, no path traversal)
  4. Intent and analysis quality (minimum length)
  5. Confidence bounds on expected impact
  6. requires_human_review must always be True
  7. YAML lint (if workflow/config changes proposed)
  8. At least one change proposed

All checks are deterministic — no LLM calls, no external APIs.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("design-agent.validator")

VALID_CHANGE_TYPES = frozenset(
    {
        "threshold_adjustment",
        "policy_addition",
        "policy_modification",
        "workflow_improvement",
        "config_update",
    }
)

# Matches patterns that indicate path traversal.
_PATH_TRAVERSAL_RE = re.compile(r"\.\.[/\\]")


# ── Individual validators ────────────────────────────────────────────


def validate_change_entry(change: dict) -> list[str]:
    """Validate a single ProposedChange dict. Returns list of errors."""
    errors: list[str] = []

    change_type = change.get("change_type", "")
    if change_type not in VALID_CHANGE_TYPES:
        errors.append(f"Unknown change_type: {change_type!r}")

    target = change.get("target_file", "")
    if not target or not isinstance(target, str):
        errors.append("Missing or empty target_file")
    elif _PATH_TRAVERSAL_RE.search(target):
        errors.append(f"Path traversal detected in target_file: {target!r}")

    if not change.get("description"):
        errors.append("Missing description for change")

    if not change.get("proposed_value") and change.get("proposed_value") != "":
        errors.append("Missing proposed_value for change")

    return errors


def validate_impact_entry(impact: dict) -> list[str]:
    """Validate a single ExpectedImpact dict. Returns list of errors."""
    errors: list[str] = []

    if not impact.get("metric_name"):
        errors.append("Missing metric_name in expected_impact")

    confidence = impact.get("confidence", -1)
    if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
        errors.append(f"confidence must be 0.0-1.0, got {confidence}")

    return errors


def validate_yaml_syntax(content: str) -> list[str]:
    """Check if a string is valid YAML. Returns list of errors."""
    try:
        import yaml

        yaml.safe_load(content)
        return []
    except Exception as exc:
        return [f"YAML syntax error: {exc}"]


# ── Main validation ──────────────────────────────────────────────────


def validate_proposal(proposal: dict) -> dict:
    """Validate a DesignProposal dict.

    Returns a ValidationResult dict with valid, checks_passed, errors, warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks_passed: list[str] = []

    # 1. Required fields
    for field in (
        "proposal_id",
        "created_at",
        "intent",
        "target_scenarios",
        "analysis_summary",
        "changes",
    ):
        if not proposal.get(field):
            errors.append(f"Missing required field: {field}")
    if not errors:
        checks_passed.append("required_fields")

    # 2. requires_human_review
    if proposal.get("requires_human_review") is not True:
        errors.append("requires_human_review must be True")
    else:
        checks_passed.append("human_review_flag")

    # 3. Intent quality
    intent = proposal.get("intent", "")
    if isinstance(intent, str) and len(intent) < 10:
        errors.append(f"intent too short ({len(intent)} chars, minimum 10)")
    elif intent:
        checks_passed.append("intent_quality")

    # 4. Analysis summary quality
    summary = proposal.get("analysis_summary", "")
    if isinstance(summary, str) and len(summary) < 20:
        errors.append(f"analysis_summary too short ({len(summary)} chars, minimum 20)")
    elif summary:
        checks_passed.append("analysis_quality")

    # 5. Changes validation
    changes = proposal.get("changes", [])
    if not isinstance(changes, list) or len(changes) == 0:
        errors.append("At least one change is required")
    else:
        for i, change in enumerate(changes):
            if not isinstance(change, dict):
                errors.append(f"changes[{i}] is not a dict")
                continue
            change_errors = validate_change_entry(change)
            errors.extend(change_errors)

        if not any(validate_change_entry(ch) for ch in changes if isinstance(ch, dict)):
            checks_passed.append("changes_valid")

    # 6. Expected impact validation
    impacts = proposal.get("expected_impact", [])
    if isinstance(impacts, list):
        for i, imp in enumerate(impacts):
            if isinstance(imp, dict):
                imp_errors = validate_impact_entry(imp)
                errors.extend(imp_errors)
        if impacts and not any(
            validate_impact_entry(imp) for imp in impacts if isinstance(imp, dict)
        ):
            checks_passed.append("impact_valid")

    # 7. Target scenarios
    target_scenarios = proposal.get("target_scenarios", [])
    if isinstance(target_scenarios, list) and len(target_scenarios) > 0:
        checks_passed.append("target_scenarios")
    elif isinstance(target_scenarios, list):
        errors.append("target_scenarios must not be empty")

    # 8. YAML lint for workflow/config changes
    for change in changes:
        if not isinstance(change, dict):
            continue
        ctype = change.get("change_type", "")
        proposed = change.get("proposed_value", "")
        if ctype in ("workflow_improvement", "config_update") and proposed:
            yaml_errors = validate_yaml_syntax(proposed)
            if yaml_errors:
                warnings.extend(yaml_errors)
            else:
                if "yaml_lint" not in checks_passed:
                    checks_passed.append("yaml_lint")

    valid = len(errors) == 0
    result = {
        "valid": valid,
        "checks_passed": checks_passed,
        "errors": errors,
        "warnings": warnings,
    }

    if valid:
        logger.info("Proposal %s passed validation", proposal.get("proposal_id", "?"))
    else:
        logger.warning(
            "Proposal %s failed validation: %s",
            proposal.get("proposal_id", "?"),
            errors,
        )

    return result

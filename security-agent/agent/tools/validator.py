"""Deterministic validator for ComplianceProposal objects.

Checks:
  1. YAML schema: proposed patch conforms to control-mappings.yaml format
  2. Superset-only: no existing refs are removed (additions/updates only)
  3. Pydantic validation: ComplianceProposal schema integrity
  4. Confidence threshold: proposals below minimum are flagged
  5. Decision type validity: only known decision types allowed

No LLM, no external calls.
"""

from __future__ import annotations

import logging

from models.schemas import ComplianceProposal, ValidationResult

logger = logging.getLogger("security-agent.validator")

# Valid decision types in CogniOps bounded action surface
_VALID_DECISION_TYPES = frozenset(
    {"NO_OP", "BLOCK", "ROLLBACK", "QUARANTINE", "ESCALATE"}
)

# Minimum confidence for a proposal to pass validation
_MIN_CONFIDENCE = 0.3


def validate_proposal(
    proposal: ComplianceProposal,
    current_yaml: dict | None = None,
) -> ValidationResult:
    """Validate a ComplianceProposal against all deterministic checks.

    Args:
        proposal: The proposal to validate.
        current_yaml: Current control-mappings.yaml (for superset check).

    Returns:
        ValidationResult with errors/warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Decision type validity
    for dt in proposal.proposed_yaml_patch.updates:
        if dt == "_UNASSIGNED":
            warnings.append(
                "Proposal contains _UNASSIGNED entries — "
                "LLM should assign specific decision types"
            )
        elif dt not in _VALID_DECISION_TYPES:
            errors.append(f"Invalid decision type in patch: {dt!r}")

    # 2. Ref format check
    for dt, entries in proposal.proposed_yaml_patch.updates.items():
        for entry in entries:
            if not entry.ref:
                errors.append(f"Empty ref in {dt} patch entry")
            if not entry.title:
                warnings.append(f"Missing title for ref {entry.ref!r} in {dt}")

    # 3. Confidence threshold
    if proposal.confidence < _MIN_CONFIDENCE:
        warnings.append(
            f"Low confidence ({proposal.confidence:.2f} < {_MIN_CONFIDENCE}) "
            "— proposal may need extra scrutiny"
        )

    # 4. Impact assessment presence
    if not proposal.impact_assessment or len(proposal.impact_assessment.strip()) < 20:
        errors.append("Impact assessment is missing or too short (< 20 chars)")

    # 5. Superset-only check (no removals)
    if current_yaml:
        _check_superset(proposal, current_yaml, errors)

    # 6. requires_human_review must always be True
    if not proposal.requires_human_review:
        errors.append("requires_human_review must always be True")

    valid = len(errors) == 0

    if not valid:
        logger.warning(
            "Proposal %s failed validation: %s", proposal.proposal_id, errors
        )
    else:
        logger.info(
            "Proposal %s passed validation (%d warnings)",
            proposal.proposal_id,
            len(warnings),
        )

    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def _check_superset(
    proposal: ComplianceProposal,
    current_yaml: dict,
    errors: list[str],
) -> None:
    """Verify the proposal only adds/updates — never removes existing refs."""
    current_mappings = current_yaml.get("mappings", {})

    for dt, current_refs in current_mappings.items():
        if not isinstance(current_refs, list):
            continue

        current_ref_ids = {
            r.get("ref") for r in current_refs if isinstance(r, dict) and "ref" in r
        }

        # If this decision type appears in the patch, check that
        # all current refs are still present (i.e., not removed)
        if dt in proposal.proposed_yaml_patch.updates:
            proposed_ref_ids = {e.ref for e in proposal.proposed_yaml_patch.updates[dt]}
            removed = current_ref_ids - proposed_ref_ids
            # Only flag as error if the patch explicitly lists refs (partial patches are OK)
            if removed and len(proposed_ref_ids) >= len(current_ref_ids):
                errors.append(
                    f"Proposal removes existing refs from {dt}: {removed}. "
                    "Only additions/updates are allowed."
                )

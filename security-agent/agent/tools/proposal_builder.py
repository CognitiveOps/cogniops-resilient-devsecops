"""Proposal builder — constructs ComplianceProposal from LLM output.

Deterministic: assembles the final proposal JSON from diff report
and LLM-generated impact assessment. The LLM reasoning is provided
by the ADK agent; this module structures it into a validated schema.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from models.schemas import (
    ComplianceProposal,
    DiffReport,
    YAMLPatch,
    YAMLPatchEntry,
)

logger = logging.getLogger("security-agent.proposal_builder")


def build_yaml_patch_from_diff(diff: DiffReport) -> YAMLPatch:
    """Build a YAML patch from diff report entries.

    For updated entries: proposes revision bump.
    For new entries: proposes addition to the most relevant decision type.
    """
    updates: dict[str, list[YAMLPatchEntry]] = {}

    for entry in diff.updated_entries:
        for dt in diff.affected_decision_types:
            patch_entry = YAMLPatchEntry(
                ref=(
                    entry.feed_entry.ref_id
                    if "SP 800-53" in entry.feed_entry.ref_id
                    else f"NIST SP 800-53 {entry.feed_entry.ref_id}"
                ),
                title=entry.feed_entry.change_summary or entry.feed_entry.ref_id,
                revision=entry.feed_entry.latest_revision or None,
            )
            updates.setdefault(dt, []).append(patch_entry)

    for entry in diff.new_entries:
        patch_entry = YAMLPatchEntry(
            ref=(
                entry.feed_entry.ref_id
                if "SP 800-53" in entry.feed_entry.ref_id
                else f"NIST SP 800-53 {entry.feed_entry.ref_id}"
            ),
            title=entry.feed_entry.change_summary or entry.feed_entry.ref_id,
            revision=entry.feed_entry.latest_revision or None,
        )
        # New entries go to a placeholder key; LLM will assign correct type
        updates.setdefault("_UNASSIGNED", []).append(patch_entry)

    return YAMLPatch(updates=updates)


def build_proposal(
    diff: DiffReport,
    impact_assessment: str,
    confidence: float,
    proposed_rego_suggestions: list[str] | None = None,
    yaml_patch_override: YAMLPatch | None = None,
) -> ComplianceProposal:
    """Assemble a ComplianceProposal from components.

    Args:
        diff: The enriched diff report.
        impact_assessment: LLM-generated reasoning text.
        confidence: LLM confidence score (0.0-1.0).
        proposed_rego_suggestions: Optional OPA policy suggestions.
        yaml_patch_override: If the LLM provided a refined patch, use it.

    Returns:
        Validated ComplianceProposal ready for storage.
    """
    proposal_id = (
        f"comp-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    )

    yaml_patch = yaml_patch_override or build_yaml_patch_from_diff(diff)

    proposal = ComplianceProposal(
        proposal_id=proposal_id,
        created_at=datetime.now(timezone.utc),
        diff_report=diff,
        proposed_yaml_patch=yaml_patch,
        proposed_rego_suggestions=proposed_rego_suggestions or [],
        impact_assessment=impact_assessment,
        confidence=max(0.0, min(1.0, confidence)),
        requires_human_review=True,
    )

    logger.info(
        "Proposal built: %s (%d updates, %d new, confidence=%.2f)",
        proposal.proposal_id,
        len(diff.updated_entries),
        len(diff.new_entries),
        proposal.confidence,
    )

    return proposal

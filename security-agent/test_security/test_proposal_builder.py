"""Tests for the proposal builder — security-agent/agent/tools/proposal_builder.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.tools.proposal_builder import build_proposal, build_yaml_patch_from_diff
from models.schemas import (
    DiffReport,
    EnrichedEntry,
    FeedEntry,
    FeedSource,
    YAMLPatch,
    YAMLPatchEntry,
)


def _make_diff(
    updated: int = 0,
    new: int = 0,
    affected: list[str] | None = None,
) -> DiffReport:
    """Helper to create a DiffReport with N entries."""
    updated_entries = [
        EnrichedEntry(
            feed_entry=FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id=f"SP 800-53 CM-{i}",
                current_revision="Rev. 5",
                latest_revision="Rev. 6",
                change_summary=f"Test control {i}",
            ),
            change_highlights=f"CM-{i}: 'Rev. 5' → 'Rev. 6'",
        )
        for i in range(updated)
    ]
    new_entries = [
        EnrichedEntry(
            feed_entry=FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id=f"SP 800-53 SI-{i}",
                latest_revision="Rev. 5",
                change_summary=f"New control {i}",
            ),
            change_highlights=f"New control: SP 800-53 SI-{i}",
        )
        for i in range(new)
    ]
    return DiffReport(
        checked_at=datetime.now(timezone.utc),
        updated_entries=updated_entries,
        new_entries=new_entries,
        affected_decision_types=affected or [],
    )


class TestBuildYAMLPatchFromDiff:
    def test_updated_entries_create_patch(self):
        diff = _make_diff(updated=1, affected=["BLOCK"])
        patch = build_yaml_patch_from_diff(diff)

        assert "BLOCK" in patch.updates
        assert len(patch.updates["BLOCK"]) == 1
        assert patch.updates["BLOCK"][0].revision == "Rev. 6"

    def test_new_entries_go_to_unassigned(self):
        diff = _make_diff(new=2)
        patch = build_yaml_patch_from_diff(diff)

        assert "_UNASSIGNED" in patch.updates
        assert len(patch.updates["_UNASSIGNED"]) == 2

    def test_empty_diff_empty_patch(self):
        diff = _make_diff()
        patch = build_yaml_patch_from_diff(diff)

        assert patch.updates == {}

    def test_ref_format_includes_sp800(self):
        """Ref should include 'SP 800-53' prefix."""
        diff = _make_diff(updated=1, affected=["QUARANTINE"])
        patch = build_yaml_patch_from_diff(diff)

        for dt, entries in patch.updates.items():
            for entry in entries:
                assert "SP 800-53" in entry.ref


class TestBuildProposal:
    def test_proposal_fields(self):
        diff = _make_diff(updated=1, affected=["BLOCK"])
        proposal = build_proposal(
            diff=diff,
            impact_assessment="CM-3 Rev.6 adds supply chain provisions.",
            confidence=0.85,
        )

        assert proposal.proposal_id.startswith("comp-")
        assert proposal.requires_human_review is True
        assert proposal.confidence == 0.85
        assert "supply chain" in proposal.impact_assessment

    def test_proposal_with_rego_suggestions(self):
        diff = _make_diff(updated=1, affected=["BLOCK"])
        proposal = build_proposal(
            diff=diff,
            impact_assessment="Test impact",
            confidence=0.7,
            proposed_rego_suggestions=["Lower BLOCK threshold to 0.5"],
        )

        assert len(proposal.proposed_rego_suggestions) == 1

    def test_proposal_with_yaml_override(self):
        diff = _make_diff(updated=1, affected=["BLOCK"])
        override = YAMLPatch(
            updates={
                "BLOCK": [
                    YAMLPatchEntry(ref="Custom Ref", title="Custom", revision="v1")
                ]
            }
        )
        proposal = build_proposal(
            diff=diff,
            impact_assessment="Test with override",
            confidence=0.9,
            yaml_patch_override=override,
        )

        assert "Custom Ref" in proposal.proposed_yaml_patch.updates["BLOCK"][0].ref

    def test_confidence_clamped(self):
        """Confidence should be clamped to [0.0, 1.0]."""
        diff = _make_diff()
        proposal = build_proposal(diff=diff, impact_assessment="Test", confidence=2.0)
        assert proposal.confidence == 1.0

        proposal2 = build_proposal(diff=diff, impact_assessment="Test", confidence=-0.5)
        assert proposal2.confidence == 0.0

    def test_unique_proposal_ids(self):
        """Each proposal should have a unique ID."""
        diff = _make_diff()
        p1 = build_proposal(diff=diff, impact_assessment="Test", confidence=0.5)
        p2 = build_proposal(diff=diff, impact_assessment="Test", confidence=0.5)
        assert p1.proposal_id != p2.proposal_id

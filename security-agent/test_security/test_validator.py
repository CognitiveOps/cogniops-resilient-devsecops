"""Tests for the validator — security-agent/agent/tools/validator.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.tools.validator import validate_proposal
from models.schemas import (
    ComplianceProposal,
    DiffReport,
    YAMLPatch,
    YAMLPatchEntry,
)

SAMPLE_YAML = {
    "mappings": {
        "BLOCK": [
            {
                "ref": "NIST SP 800-53 CM-3",
                "title": "Configuration Change Control",
                "revision": "Rev. 5",
            },
        ],
        "ROLLBACK": [
            {
                "ref": "NIST SP 800-53 CP-10",
                "title": "System Recovery",
                "revision": "Rev. 5",
            },
        ],
        "NO_OP": [],
    },
}


def _make_proposal(
    impact: str = "CM-3 Rev.6 strengthens supply chain controls for S1 CI/CD.",
    confidence: float = 0.8,
    patch_updates: dict | None = None,
) -> ComplianceProposal:
    if patch_updates is None:
        patch_updates = {
            "BLOCK": [
                YAMLPatchEntry(
                    ref="NIST SP 800-53 CM-3", title="Test", revision="Rev. 6"
                )
            ]
        }
    return ComplianceProposal(
        proposal_id="comp-20260314-test0001",
        created_at=datetime.now(timezone.utc),
        diff_report=DiffReport(
            checked_at=datetime.now(timezone.utc),
            affected_decision_types=list(patch_updates.keys()),
        ),
        proposed_yaml_patch=YAMLPatch(updates=patch_updates),
        impact_assessment=impact,
        confidence=confidence,
        requires_human_review=True,
    )


class TestValidateProposal:
    def test_valid_proposal_passes(self):
        proposal = _make_proposal()
        result = validate_proposal(proposal)

        assert result.valid
        assert result.errors == []

    def test_invalid_decision_type_fails(self):
        proposal = _make_proposal(
            patch_updates={"INVALID_TYPE": [YAMLPatchEntry(ref="test", title="test")]}
        )
        result = validate_proposal(proposal)

        assert not result.valid
        assert any("Invalid decision type" in e for e in result.errors)

    def test_empty_ref_fails(self):
        proposal = _make_proposal(
            patch_updates={"BLOCK": [YAMLPatchEntry(ref="", title="test")]}
        )
        result = validate_proposal(proposal)

        assert not result.valid
        assert any("Empty ref" in e for e in result.errors)

    def test_low_confidence_warning(self):
        proposal = _make_proposal(confidence=0.1)
        result = validate_proposal(proposal)

        assert result.valid  # warning, not error
        assert any("Low confidence" in w for w in result.warnings)

    def test_missing_impact_fails(self):
        proposal = _make_proposal(impact="short")
        result = validate_proposal(proposal)

        assert not result.valid
        assert any("too short" in e for e in result.errors)

    def test_unassigned_warning(self):
        proposal = _make_proposal(
            patch_updates={
                "_UNASSIGNED": [YAMLPatchEntry(ref="test ref", title="test")]
            }
        )
        result = validate_proposal(proposal)

        assert result.valid  # warning, not error
        assert any("_UNASSIGNED" in w for w in result.warnings)

    def test_missing_title_warning(self):
        proposal = _make_proposal(
            patch_updates={
                "BLOCK": [YAMLPatchEntry(ref="NIST SP 800-53 CM-3", title="")]
            }
        )
        result = validate_proposal(proposal)

        assert any("Missing title" in w for w in result.warnings)

    def test_superset_check_allows_additions(self):
        """Adding new refs to existing decision types should pass."""
        proposal = _make_proposal(
            patch_updates={
                "BLOCK": [
                    YAMLPatchEntry(
                        ref="NIST SP 800-53 CM-3", title="Existing", revision="Rev. 6"
                    ),
                    YAMLPatchEntry(ref="NIST SP 800-53 CM-4", title="New addition"),
                ]
            }
        )
        result = validate_proposal(proposal, SAMPLE_YAML)

        assert result.valid

    def test_no_current_yaml_skips_superset(self):
        """Without current YAML, superset check is skipped."""
        proposal = _make_proposal()
        result = validate_proposal(proposal, None)

        assert result.valid

    def test_valid_with_rego_suggestions(self):
        proposal = _make_proposal()
        proposal.proposed_rego_suggestions = ["Consider lowering BLOCK threshold"]
        result = validate_proposal(proposal)

        assert result.valid

    def test_multiple_decision_types(self):
        proposal = _make_proposal(
            patch_updates={
                "BLOCK": [YAMLPatchEntry(ref="NIST SP 800-53 CM-3", title="Test")],
                "ROLLBACK": [YAMLPatchEntry(ref="NIST SP 800-53 CP-10", title="Test")],
            }
        )
        result = validate_proposal(proposal)

        assert result.valid

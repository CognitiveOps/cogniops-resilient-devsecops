"""Tests for agent/tools/proposal_generator.py — proposal assembly."""

from __future__ import annotations

import unittest

from agent.tools.proposal_generator import generate_proposal, no_proposal_needed


class TestGenerateProposal(unittest.TestCase):
    def _make_proposal(self, **overrides):
        import json

        defaults = {
            "intent": "Reduce MTTR in S3",
            "target_scenarios": "S3, SS2",
            "analysis_summary": "MTTR trending upward. Recovery activation is the bottleneck.",
            "changes": json.dumps([
                {
                    "change_type": "threshold_adjustment",
                    "target_file": "s3_rollback.yml",
                    "description": "Reduce poll interval during recovery",
                    "current_value": "5",
                    "proposed_value": "2",
                    "rationale": "Faster recovery confirmation",
                },
            ]),
        }
        defaults.update(overrides)
        return generate_proposal(**defaults)

    def test_returns_proposal_generated(self):
        result = self._make_proposal()
        assert result["status"] == "proposal_generated"
        assert "proposal" in result

    def test_proposal_id_format(self):
        result = self._make_proposal()
        proposal = result["proposal"]
        assert proposal["proposal_id"].startswith("design-")
        assert len(proposal["proposal_id"]) > 15

    def test_contains_intent(self):
        result = self._make_proposal()
        assert result["proposal"]["intent"] == "Reduce MTTR in S3"

    def test_contains_changes(self):
        result = self._make_proposal()
        changes = result["proposal"]["changes"]
        assert len(changes) == 1
        assert changes[0]["change_type"] == "threshold_adjustment"
        assert changes[0]["target_file"] == "s3_rollback.yml"

    def test_target_scenarios_parsed(self):
        result = self._make_proposal()
        assert result["proposal"]["target_scenarios"] == ["S3", "SS2"]

    def test_requires_human_review(self):
        result = self._make_proposal()
        assert result["proposal"]["requires_human_review"] is True

    def test_normalizes_changes(self):
        import json

        result = self._make_proposal(
            changes=json.dumps([{"target_file": "test.yml", "description": "test"}])
        )
        ch = result["proposal"]["changes"][0]
        assert ch["change_type"] == "config_update"  # default
        assert ch["proposed_value"] == ""  # default

    def test_with_expected_impact(self):
        import json

        result = self._make_proposal(
            expected_impact=json.dumps([
                {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": 0.6},
            ])
        )
        impact = result["proposal"]["expected_impact"]
        assert len(impact) == 1
        assert impact[0]["confidence"] == 0.6

    def test_confidence_clamped(self):
        import json

        result = self._make_proposal(
            expected_impact=json.dumps([
                {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": 1.5},
            ])
        )
        assert result["proposal"]["expected_impact"][0]["confidence"] == 1.0

    def test_confidence_clamped_negative(self):
        import json

        result = self._make_proposal(
            expected_impact=json.dumps([
                {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": -0.5},
            ])
        )
        assert result["proposal"]["expected_impact"][0]["confidence"] == 0.0

    def test_with_policy_refs(self):
        result = self._make_proposal(policy_refs="NIST CP-10, ISO 27001 A.17.1.2")
        assert "NIST CP-10" in result["proposal"]["policy_refs"]

    def test_empty_policy_refs_default(self):
        result = self._make_proposal()
        assert result["proposal"]["policy_refs"] == []

    def test_validation_starts_invalid(self):
        result = self._make_proposal()
        assert result["proposal"]["validation"]["valid"] is False

    def test_unique_proposal_ids(self):
        r1 = self._make_proposal()
        r2 = self._make_proposal()
        assert r1["proposal"]["proposal_id"] != r2["proposal"]["proposal_id"]


class TestNoProposalNeeded(unittest.TestCase):
    def test_returns_status(self):
        result = no_proposal_needed("All metrics within healthy ranges")
        assert result["status"] == "no_proposal_needed"
        assert "healthy" in result["reason"]

    def test_preserves_reason(self):
        reason = "S3 MTTR improved 20% this week, no action needed"
        result = no_proposal_needed(reason)
        assert result["reason"] == reason

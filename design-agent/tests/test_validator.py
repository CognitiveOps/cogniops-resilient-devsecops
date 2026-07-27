"""Tests for agent/tools/validator.py — deterministic proposal validation."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from agent.tools.validator import (
    validate_change_entry,
    validate_impact_entry,
    validate_proposal,
    validate_yaml_syntax,
)


class TestValidateChangeEntry(unittest.TestCase):
    def _valid_change(self, **overrides):
        ch = {
            "change_type": "threshold_adjustment",
            "target_file": "s3_rollback.yml",
            "description": "Reduce poll interval",
            "proposed_value": "2",
        }
        ch.update(overrides)
        return ch

    def test_valid_change(self):
        errors = validate_change_entry(self._valid_change())
        assert errors == []

    def test_unknown_change_type(self):
        errors = validate_change_entry(self._valid_change(change_type="unknown"))
        assert any("change_type" in e for e in errors)

    def test_empty_target_file(self):
        errors = validate_change_entry(self._valid_change(target_file=""))
        assert any("target_file" in e for e in errors)

    def test_path_traversal(self):
        errors = validate_change_entry(self._valid_change(target_file="../etc/passwd"))
        assert any("traversal" in e.lower() for e in errors)

    def test_missing_description(self):
        errors = validate_change_entry(self._valid_change(description=""))
        assert any("description" in e for e in errors)

    def test_missing_proposed_value(self):
        ch = self._valid_change()
        del ch["proposed_value"]
        errors = validate_change_entry(ch)
        assert any("proposed_value" in e for e in errors)


class TestValidateImpactEntry(unittest.TestCase):
    def test_valid_impact(self):
        errors = validate_impact_entry(
            {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": 0.6}
        )
        assert errors == []

    def test_missing_metric_name(self):
        errors = validate_impact_entry(
            {"metric_name": "", "estimated_change": "-25%", "confidence": 0.6}
        )
        assert any("metric_name" in e for e in errors)

    def test_confidence_too_high(self):
        errors = validate_impact_entry(
            {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": 1.5}
        )
        assert any("confidence" in e for e in errors)

    def test_confidence_negative(self):
        errors = validate_impact_entry(
            {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": -0.1}
        )
        assert any("confidence" in e for e in errors)


class TestValidateYamlSyntax(unittest.TestCase):
    def test_valid_yaml(self):
        errors = validate_yaml_syntax("key: value\nlist:\n  - a\n  - b\n")
        assert errors == []

    def test_invalid_yaml(self):
        errors = validate_yaml_syntax("key: [unclosed bracket")
        assert len(errors) > 0

    def test_empty_string(self):
        errors = validate_yaml_syntax("")
        assert errors == []


class TestValidateProposal(unittest.TestCase):
    def _valid_proposal(self, **overrides):
        p = {
            "proposal_id": "design-20260319-abc12345",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "intent": "Reduce MTTR in S3 by optimizing recovery",
            "target_scenarios": ["S3"],
            "analysis_summary": "MTTR trending upward. Recovery activation is the bottleneck for edge OTA rollback.",
            "changes": [
                {
                    "change_type": "threshold_adjustment",
                    "target_file": "s3_rollback.yml",
                    "description": "Reduce poll interval during recovery",
                    "proposed_value": "2",
                    "rationale": "Faster recovery confirmation",
                },
            ],
            "expected_impact": [
                {"metric_name": "MTTR", "estimated_change": "-25%", "confidence": 0.6},
            ],
            "policy_refs": ["NIST CP-10"],
            "requires_human_review": True,
        }
        p.update(overrides)
        return p

    def test_valid_proposal_passes(self):
        result = validate_proposal(self._valid_proposal())
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert "required_fields" in result["checks_passed"]

    def test_missing_required_field(self):
        p = self._valid_proposal()
        del p["intent"]
        result = validate_proposal(p)
        assert result["valid"] is False
        assert any("intent" in e for e in result["errors"])

    def test_human_review_false(self):
        result = validate_proposal(self._valid_proposal(requires_human_review=False))
        assert result["valid"] is False
        assert any("human_review" in e for e in result["errors"])

    def test_intent_too_short(self):
        result = validate_proposal(self._valid_proposal(intent="Fix"))
        assert result["valid"] is False
        assert any("intent too short" in e for e in result["errors"])

    def test_analysis_too_short(self):
        result = validate_proposal(self._valid_proposal(analysis_summary="Bad"))
        assert result["valid"] is False
        assert any("analysis_summary too short" in e for e in result["errors"])

    def test_empty_changes(self):
        result = validate_proposal(self._valid_proposal(changes=[]))
        assert result["valid"] is False
        assert any("change is required" in e for e in result["errors"])

    def test_invalid_change_type(self):
        result = validate_proposal(
            self._valid_proposal(
                changes=[
                    {
                        "change_type": "invalid_type",
                        "target_file": "test.yml",
                        "description": "test change",
                        "proposed_value": "test",
                    }
                ]
            )
        )
        assert result["valid"] is False

    def test_path_traversal_in_change(self):
        result = validate_proposal(
            self._valid_proposal(
                changes=[
                    {
                        "change_type": "config_update",
                        "target_file": "../../secrets.yaml",
                        "description": "steal secrets",
                        "proposed_value": "x",
                    }
                ]
            )
        )
        assert result["valid"] is False
        assert any("traversal" in e.lower() for e in result["errors"])

    def test_empty_target_scenarios(self):
        result = validate_proposal(self._valid_proposal(target_scenarios=[]))
        assert result["valid"] is False

    def test_yaml_lint_warning(self):
        result = validate_proposal(
            self._valid_proposal(
                changes=[
                    {
                        "change_type": "config_update",
                        "target_file": "config.yaml",
                        "description": "update config",
                        "proposed_value": "key: [unclosed",
                        "rationale": "test",
                    }
                ]
            )
        )
        assert len(result["warnings"]) > 0

    def test_valid_yaml_in_change(self):
        result = validate_proposal(
            self._valid_proposal(
                changes=[
                    {
                        "change_type": "config_update",
                        "target_file": "config.yaml",
                        "description": "update config",
                        "proposed_value": "key: value",
                        "rationale": "test",
                    }
                ]
            )
        )
        assert result["valid"] is True
        assert "yaml_lint" in result["checks_passed"]

    def test_impact_confidence_invalid(self):
        result = validate_proposal(
            self._valid_proposal(
                expected_impact=[
                    {
                        "metric_name": "MTTR",
                        "estimated_change": "-25%",
                        "confidence": 2.0,
                    },
                ]
            )
        )
        assert result["valid"] is False

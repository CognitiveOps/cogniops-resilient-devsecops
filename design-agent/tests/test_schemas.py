"""Tests for models/schemas.py — Pydantic v2 schemas."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.schemas import (
    AnalysisContext,
    ChangeType,
    DesignProposal,
    ExpectedImpact,
    ProposedChange,
    RuntimeDecisionSummary,
    ScenarioMetricSummary,
    ValidationResult,
)


class TestScenarioMetricSummary(unittest.TestCase):
    def test_create_basic(self):
        s = ScenarioMetricSummary(
            scenario_id="s3",
            metric_name="MTTR",
            mean_value=45.2,
            sample_count=30,
            unit="seconds",
        )
        assert s.scenario_id == "s3"
        assert s.metric_name == "MTTR"
        assert s.mean_value == 45.2
        assert s.sample_count == 30
        assert s.trend_direction is None

    def test_with_trend(self):
        s = ScenarioMetricSummary(
            scenario_id="s1",
            metric_name="TTD",
            mean_value=120.0,
            sample_count=50,
            trend_direction="improving",
            unit="seconds",
        )
        assert s.trend_direction == "improving"

    def test_optional_percentiles(self):
        s = ScenarioMetricSummary(
            scenario_id="s2",
            metric_name="TDL",
            mean_value=25.0,
            p50_value=22.0,
            p95_value=48.0,
            sample_count=40,
        )
        assert s.p50_value == 22.0
        assert s.p95_value == 48.0


class TestRuntimeDecisionSummary(unittest.TestCase):
    def test_defaults(self):
        r = RuntimeDecisionSummary()
        assert r.total_decisions == 0
        assert r.by_action == {}
        assert r.execution_rate == 0.0

    def test_with_data(self):
        r = RuntimeDecisionSummary(
            total_decisions=50,
            by_action={"NO_OP": 40, "BLOCK": 5, "ROLLBACK": 5},
            by_scenario={"s3": 30, "ss2": 20},
            execution_rate=0.1,
        )
        assert r.total_decisions == 50
        assert r.by_action["BLOCK"] == 5


class TestAnalysisContext(unittest.TestCase):
    def test_create_empty(self):
        ctx = AnalysisContext(built_at=datetime.now(timezone.utc))
        assert ctx.scenario_metrics == []
        assert ctx.runtime_decisions.total_decisions == 0
        assert ctx.window_days == 30

    def test_with_metrics(self):
        ctx = AnalysisContext(
            built_at=datetime.now(timezone.utc),
            window_days=14,
            scenario_metrics=[
                ScenarioMetricSummary(
                    scenario_id="s3",
                    metric_name="MTTR",
                    mean_value=45.2,
                    sample_count=30,
                )
            ],
        )
        assert len(ctx.scenario_metrics) == 1
        assert ctx.window_days == 14


class TestChangeType(unittest.TestCase):
    def test_all_types(self):
        assert ChangeType.THRESHOLD_ADJUSTMENT == "threshold_adjustment"
        assert ChangeType.POLICY_ADDITION == "policy_addition"
        assert ChangeType.POLICY_MODIFICATION == "policy_modification"
        assert ChangeType.WORKFLOW_IMPROVEMENT == "workflow_improvement"
        assert ChangeType.CONFIG_UPDATE == "config_update"


class TestProposedChange(unittest.TestCase):
    def test_create(self):
        ch = ProposedChange(
            change_type=ChangeType.THRESHOLD_ADJUSTMENT,
            target_file="s3_rollback.yml",
            description="Reduce poll interval",
            proposed_value="2",
            rationale="Faster recovery",
        )
        assert ch.target_file == "s3_rollback.yml"
        assert ch.current_value is None

    def test_with_current_value(self):
        ch = ProposedChange(
            change_type=ChangeType.POLICY_ADDITION,
            target_file="ss1.rego",
            description="Add SA check",
            current_value=None,
            proposed_value="deny_unauthorized_sa",
            rationale="Close FDR gap",
        )
        assert ch.change_type == ChangeType.POLICY_ADDITION


class TestExpectedImpact(unittest.TestCase):
    def test_create(self):
        imp = ExpectedImpact(
            metric_name="MTTR",
            estimated_change="-25%",
            confidence=0.6,
        )
        assert imp.confidence == 0.6

    def test_confidence_bounds(self):
        # Valid at bounds
        ExpectedImpact(metric_name="CFR", estimated_change="+5%", confidence=0.0)
        ExpectedImpact(metric_name="CFR", estimated_change="+5%", confidence=1.0)


class TestValidationResult(unittest.TestCase):
    def test_defaults(self):
        v = ValidationResult(valid=True)
        assert v.errors == []
        assert v.checks_passed == []

    def test_with_errors(self):
        v = ValidationResult(
            valid=False,
            errors=["missing field"],
            warnings=["low confidence"],
        )
        assert not v.valid
        assert len(v.errors) == 1


class TestDesignProposal(unittest.TestCase):
    def _make_proposal(self, **overrides):
        defaults = {
            "proposal_id": "design-20260319-abc12345",
            "created_at": datetime.now(timezone.utc),
            "intent": "Reduce MTTR in S3",
            "target_scenarios": ["S3"],
            "analysis_summary": "MTTR trending upward, recovery bottleneck identified.",
            "changes": [
                ProposedChange(
                    change_type=ChangeType.THRESHOLD_ADJUSTMENT,
                    target_file="s3_rollback.yml",
                    description="Reduce poll interval",
                    proposed_value="2",
                    rationale="Faster recovery",
                ),
            ],
        }
        defaults.update(overrides)
        return DesignProposal(**defaults)

    def test_create_valid(self):
        p = self._make_proposal()
        assert p.requires_human_review is True
        assert len(p.changes) == 1

    def test_requires_human_review_always_true(self):
        p = self._make_proposal()
        assert p.requires_human_review is True

    def test_proposal_id_format(self):
        p = self._make_proposal()
        assert p.proposal_id.startswith("design-")

    def test_with_impact(self):
        p = self._make_proposal(
            expected_impact=[
                ExpectedImpact(
                    metric_name="MTTR",
                    estimated_change="-25%",
                    confidence=0.6,
                ),
            ],
        )
        assert len(p.expected_impact) == 1

    def test_with_policy_refs(self):
        p = self._make_proposal(
            policy_refs=["NIST CP-10", "ISO 27001 A.17.1.2"],
        )
        assert "NIST CP-10" in p.policy_refs

    def test_serialization_roundtrip(self):
        p = self._make_proposal()
        data = p.model_dump(mode="json")
        p2 = DesignProposal.model_validate(data)
        assert p2.proposal_id == p.proposal_id
        assert p2.intent == p.intent

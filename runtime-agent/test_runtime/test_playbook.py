"""
Unit tests for the Risk/Planning module.

Spec: anomaly → NO_OP decision (Phase 0)
  - decision = NO_OP
  - rationale = "Phase 0 shadow mode — no action taken"
  - policy_refs = []
"""

from __future__ import annotations

from models.schemas import DecisionType
from planning.playbook import select_playbook


class TestSelectPlaybook:
    """Tests for select_playbook()."""

    def test_returns_no_op_decision(self, sample_anomaly):
        """Phase 0 always returns NO_OP."""
        decision = select_playbook(sample_anomaly)

        assert decision.decision == DecisionType.NO_OP
        assert decision.decision.value == "NO_OP"

    def test_rationale_is_shadow_mode(self, sample_anomaly):
        """Rationale must match exact spec string."""
        decision = select_playbook(sample_anomaly)

        assert decision.rationale == "Phase 0 shadow mode — no action taken"

    def test_policy_refs_empty(self, sample_anomaly):
        """Phase 0 has no policy references."""
        decision = select_playbook(sample_anomaly)

        assert decision.policy_refs == []

    def test_decision_is_consistent_across_event_types(self):
        """NO_OP regardless of anomaly type."""
        from models.schemas import AnomalyOutput

        for event_type in [
            "pipeline_failure",
            "policy_violation",
            "resilience_degradation",
        ]:
            anomaly = AnomalyOutput(
                scenario="S1",
                anomaly_type=event_type,
                severity=0.5,
                risk_score=0.5,
                source_event_id="test-consistent",
            )
            decision = select_playbook(anomaly)
            assert decision.decision == DecisionType.NO_OP

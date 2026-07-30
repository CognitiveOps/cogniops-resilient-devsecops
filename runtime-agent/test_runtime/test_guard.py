"""
Unit tests for the Policy Guard module.

Spec: decision → approved=True (Phase 0)
  - approved = True
  - reason = "Phase 0 — guard bypassed"
"""

from __future__ import annotations

from guard.policy_check import check_policy
from models.schemas import DecisionType, PlanningDecision


class TestCheckPolicy:
    """Tests for check_policy()."""

    def test_always_approved(self, sample_decision):
        """Phase 0 guard always approves."""
        verdict = check_policy(sample_decision)

        assert verdict.approved is True

    def test_reason_is_guard_bypassed(self, sample_decision):
        """Reason must match exact spec string."""
        verdict = check_policy(sample_decision)

        assert verdict.reason == "Phase 0 — guard bypassed"

    def test_approved_for_all_decision_types(self):
        """Guard approves regardless of decision type (Phase 0 bypass)."""
        for dt in DecisionType:
            decision = PlanningDecision(
                decision=dt,
                rationale="test",
                policy_refs=[],
            )
            verdict = check_policy(decision)
            assert verdict.approved is True

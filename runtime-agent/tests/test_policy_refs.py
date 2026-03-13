"""
Tests for telemetry.policy_refs — ISO/NIST control mapping.

Verifies that every DecisionType maps to correct control references.
"""

from __future__ import annotations

import pytest

from models.schemas import DecisionType
from telemetry.policy_refs import get_policy_refs


class TestPolicyRefsMapping:
    """Verify control reference mapping for all decision types."""

    def test_no_op_has_no_refs(self) -> None:
        refs = get_policy_refs(DecisionType.NO_OP)
        assert refs == []

    def test_block_has_nist_cm3(self) -> None:
        refs = get_policy_refs(DecisionType.BLOCK)
        assert "NIST SP 800-53 CM-3" in refs

    def test_block_has_iso_change_management(self) -> None:
        refs = get_policy_refs(DecisionType.BLOCK)
        assert "ISO 27001:2022 A.12.1.2" in refs

    def test_block_has_imo_ref(self) -> None:
        refs = get_policy_refs(DecisionType.BLOCK)
        assert any("IMO" in r for r in refs)

    def test_rollback_has_nist_cp10(self) -> None:
        refs = get_policy_refs(DecisionType.ROLLBACK)
        assert "NIST SP 800-53 CP-10" in refs

    def test_rollback_has_iso_continuity(self) -> None:
        refs = get_policy_refs(DecisionType.ROLLBACK)
        assert "ISO 27001:2022 A.17.1.2" in refs

    def test_quarantine_has_nist_si3(self) -> None:
        refs = get_policy_refs(DecisionType.QUARANTINE)
        assert "NIST SP 800-53 SI-3" in refs

    def test_quarantine_has_iso_malware(self) -> None:
        refs = get_policy_refs(DecisionType.QUARANTINE)
        assert "ISO 27001:2022 A.12.2.1" in refs

    def test_escalate_has_nist_ir6(self) -> None:
        refs = get_policy_refs(DecisionType.ESCALATE)
        assert "NIST SP 800-53 IR-6" in refs

    def test_escalate_has_iso_reporting(self) -> None:
        refs = get_policy_refs(DecisionType.ESCALATE)
        assert "ISO 27001:2022 A.16.1.2" in refs

    @pytest.mark.parametrize(
        "decision",
        [DecisionType.BLOCK, DecisionType.ROLLBACK, DecisionType.QUARANTINE, DecisionType.ESCALATE],
    )
    def test_action_types_have_three_refs(self, decision: DecisionType) -> None:
        """Each action type maps to exactly 3 control refs (NIST + ISO + IMO)."""
        refs = get_policy_refs(decision)
        assert len(refs) == 3

    @pytest.mark.parametrize("decision", list(DecisionType))
    def test_returns_new_list(self, decision: DecisionType) -> None:
        """get_policy_refs returns a copy — mutating the result does not affect the map."""
        refs1 = get_policy_refs(decision)
        refs1.append("mutated")
        refs2 = get_policy_refs(decision)
        assert "mutated" not in refs2

    @pytest.mark.parametrize("decision", list(DecisionType))
    def test_all_refs_are_strings(self, decision: DecisionType) -> None:
        refs = get_policy_refs(decision)
        assert all(isinstance(r, str) for r in refs)

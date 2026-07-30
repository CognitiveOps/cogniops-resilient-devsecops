"""Tests for cogniops_runtime.rego OPA policy.

Uses OPA CLI (`opa eval`) to evaluate the Rego policy with test inputs.
Skips gracefully if OPA CLI is not installed.
"""

from __future__ import annotations

import json
import subprocess

import sys
from pathlib import Path

import pytest

# Resolve path to policy file relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = str(_PROJECT_ROOT / "security" / "policies" / "cogniops_runtime.rego")


def _opa_available() -> bool:
    """Check if OPA CLI is installed."""
    try:
        subprocess.run(["opa", "version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _opa_eval(input_data: dict) -> list[str]:
    """Evaluate the policy and return deny reasons."""
    input_json = json.dumps(input_data)
    result = subprocess.run(
        [
            "opa",
            "eval",
            "-d",
            POLICY_PATH,
            "-i",
            "/dev/stdin",
            "data.cogniops.runtime.deny",
            "--format",
            "json",
        ],
        input=input_json,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    # OPA eval returns {"result": [{"expressions": [{"value": [...]}]}]}
    expressions = parsed.get("result", [{}])[0].get("expressions", [])
    if expressions:
        return list(expressions[0].get("value", []))
    return []


pytestmark = pytest.mark.skipif(
    not _opa_available(), reason="OPA CLI not installed"
)


# ── Shadow mode tests ───────────────────────────────────────────────


class TestShadowMode:
    """In shadow mode, only NO_OP is allowed."""

    def test_no_op_in_shadow_allowed(self):
        denials = _opa_eval(
            {"action": "NO_OP", "mode": "shadow", "severity": 0.3, "scenario": "S1"}
        )
        assert len(denials) == 0

    def test_block_in_shadow_denied(self):
        denials = _opa_eval(
            {"action": "BLOCK", "mode": "shadow", "severity": 0.8, "scenario": "S1"}
        )
        assert any("shadow" in d for d in denials)

    def test_rollback_in_shadow_denied(self):
        denials = _opa_eval(
            {"action": "ROLLBACK", "mode": "shadow", "severity": 0.9, "scenario": "S3"}
        )
        assert any("shadow" in d for d in denials)

    def test_escalate_in_shadow_denied(self):
        denials = _opa_eval(
            {"action": "ESCALATE", "mode": "shadow", "severity": 0.5, "scenario": "S1"}
        )
        assert any("shadow" in d for d in denials)


# ── Severity threshold tests ────────────────────────────────────────


class TestSeverityThresholds:
    """Enforce severity requirements for ROLLBACK and BLOCK."""

    def test_rollback_below_threshold_denied(self):
        denials = _opa_eval(
            {"action": "ROLLBACK", "mode": "enforce", "severity": 0.5, "scenario": "S3"}
        )
        assert any("ROLLBACK requires severity >= 0.7" in d for d in denials)

    def test_rollback_at_threshold_allowed(self):
        denials = _opa_eval(
            {"action": "ROLLBACK", "mode": "enforce", "severity": 0.7, "scenario": "S3"}
        )
        # Should not have the severity denial
        severity_denials = [d for d in denials if "severity" in d]
        assert len(severity_denials) == 0

    def test_rollback_above_threshold_allowed(self):
        denials = _opa_eval(
            {"action": "ROLLBACK", "mode": "enforce", "severity": 0.9, "scenario": "S3"}
        )
        severity_denials = [d for d in denials if "severity" in d]
        assert len(severity_denials) == 0

    def test_block_below_threshold_denied(self):
        denials = _opa_eval(
            {"action": "BLOCK", "mode": "enforce", "severity": 0.4, "scenario": "S1"}
        )
        assert any("BLOCK requires severity >= 0.6" in d for d in denials)

    def test_block_at_threshold_allowed(self):
        denials = _opa_eval(
            {"action": "BLOCK", "mode": "enforce", "severity": 0.6, "scenario": "S1"}
        )
        severity_denials = [d for d in denials if "severity" in d]
        assert len(severity_denials) == 0


# ── QUARANTINE scenario restriction tests ───────────────────────────


class TestQuarantineScenario:
    """QUARANTINE is only allowed for S4 and SS2 scenarios."""

    def test_quarantine_s4_allowed(self):
        denials = _opa_eval(
            {"action": "QUARANTINE", "mode": "enforce", "severity": 0.7, "scenario": "S4"}
        )
        scenario_denials = [d for d in denials if "QUARANTINE only" in d]
        assert len(scenario_denials) == 0

    def test_quarantine_ss2_allowed(self):
        denials = _opa_eval(
            {"action": "QUARANTINE", "mode": "enforce", "severity": 0.7, "scenario": "SS2"}
        )
        scenario_denials = [d for d in denials if "QUARANTINE only" in d]
        assert len(scenario_denials) == 0

    def test_quarantine_s1_denied(self):
        denials = _opa_eval(
            {"action": "QUARANTINE", "mode": "enforce", "severity": 0.7, "scenario": "S1"}
        )
        assert any("QUARANTINE only for S4/SS2" in d for d in denials)

    def test_quarantine_s3_denied(self):
        denials = _opa_eval(
            {"action": "QUARANTINE", "mode": "enforce", "severity": 0.7, "scenario": "S3"}
        )
        assert any("QUARANTINE only for S4/SS2" in d for d in denials)


# ── Combined rules tests ────────────────────────────────────────────


class TestCombinedRules:
    """Multiple deny rules can fire simultaneously."""

    def test_quarantine_shadow_s1_gets_multiple_denials(self):
        denials = _opa_eval(
            {"action": "QUARANTINE", "mode": "shadow", "severity": 0.3, "scenario": "S1"}
        )
        # shadow mode denial + S1 not in S4/SS2
        assert len(denials) >= 2

    def test_no_op_enforce_no_denials(self):
        denials = _opa_eval(
            {"action": "NO_OP", "mode": "enforce", "severity": 0.1, "scenario": "S1"}
        )
        assert len(denials) == 0

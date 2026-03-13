"""
Tests for telemetry.trace_emitter — ActionTrace CloudEvent builder + emitter.

Validates that:
- build_action_trace() produces CloudEvents passing validate_action_trace()
- ACR = 1.0 for valid traces
- emit_action_trace() returns True for valid traces, False for invalid
- Missing ingest URL is gracefully handled
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import pytest

from baseline.explainability.schema import compute_acr, validate_action_trace
from telemetry.trace_emitter import build_action_trace, emit_action_trace


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_trace(**overrides: Any) -> dict[str, Any]:
    """Build a valid ActionTrace with sensible defaults."""
    defaults = {
        "event_id": "evt-001",
        "event_type": "pipeline_failure",
        "scenario_id": "S3",
        "run_id": "run-001",
        "mode": "shadow",
        "decision": "ROLLBACK",
        "rationale": "High severity anomaly with active impact on S3",
        "policy_refs": [
            "NIST SP 800-53 CP-10",
            "ISO 27001:2022 A.17.1.2",
            "IMO MSC.428(98) §4.4",
        ],
        "severity": 0.85,
        "risk_score": 0.78,
        "guard_approved": True,
        "guard_reason": "OPA policy allows ROLLBACK",
        "executed": False,
        "agentops_trace_id": "local-abc123",
        "commit_sha": "deadbeef",
        "t_start_epoch": time.time(),
    }
    defaults.update(overrides)
    return build_action_trace(**defaults)


# ── Schema Validation Tests ──────────────────────────────────────────


class TestBuildActionTrace:
    """Verify build_action_trace() produces valid CloudEvent ActionTraces."""

    def test_valid_trace_passes_validation(self) -> None:
        trace = _make_trace()
        valid, missing = validate_action_trace(trace)
        assert valid, f"Validation failed, missing: {missing}"

    def test_has_cloudevent_envelope(self) -> None:
        trace = _make_trace()
        assert trace["specversion"] == "1.0"
        assert "id" in trace
        assert trace["source"] == "cogniops/runtime-agent"
        assert trace["type"] == "cogniops.runtime.decision"
        assert "time" in trace
        assert trace["datacontenttype"] == "application/json"

    def test_data_has_required_fields(self) -> None:
        trace = _make_trace()
        data = trace["data"]
        assert data["schema_version"] == "1.0"
        assert data["scenario_id"] == "S3"
        assert data["stage"] == "runtime_decision"
        assert data["mode"] == "shadow"
        assert data["run_id"] == "run-001"
        assert data["case_id"] == "evt-001"
        assert data["actor"] == "cogniops_planning"
        assert data["action"] == "ROLLBACK"
        assert data["recommendation"] == "ROLLBACK"
        assert data["decision"] == "approved"
        assert data["rationale"] != ""

    def test_risk_block(self) -> None:
        trace = _make_trace(risk_score=0.78)
        risk = trace["data"]["risk"]
        assert risk["score"] == 0.78
        assert risk["level"] == "high"

    def test_risk_level_critical(self) -> None:
        trace = _make_trace(risk_score=0.95)
        assert trace["data"]["risk"]["level"] == "critical"

    def test_risk_level_medium(self) -> None:
        trace = _make_trace(risk_score=0.5)
        assert trace["data"]["risk"]["level"] == "medium"

    def test_risk_level_low(self) -> None:
        trace = _make_trace(risk_score=0.2)
        assert trace["data"]["risk"]["level"] == "low"

    def test_evidence_contains_pipeline_output(self) -> None:
        trace = _make_trace()
        evidence = trace["data"]["evidence"]
        assert len(evidence) == 1
        assert evidence[0]["event_type"] == "pipeline_failure"
        assert evidence[0]["guard_approved"] is True

    def test_timestamps_has_recommend_epoch(self) -> None:
        t_start = time.time()
        trace = _make_trace(t_start_epoch=t_start)
        ts = trace["data"]["timestamps"]
        assert ts["t_recommend_epoch"] == t_start
        assert "t_decision_epoch" in ts

    def test_provenance_has_commit_sha(self) -> None:
        trace = _make_trace(commit_sha="abc123")
        prov = trace["data"]["provenance"]
        assert prov["commit_sha"] == "abc123"

    def test_otel_has_trace_id(self) -> None:
        trace = _make_trace(agentops_trace_id="ao-xyz")
        assert trace["data"]["otel"]["trace_id"] == "ao-xyz"

    def test_subject_is_event_id(self) -> None:
        trace = _make_trace(event_id="evt-special")
        assert trace.get("subject") == "evt-special"

    def test_guard_denied(self) -> None:
        trace = _make_trace(guard_approved=False)
        assert trace["data"]["decision"] == "denied"
        assert trace["data"]["evidence"][0]["guard_approved"] is False


# ── ACR Tests ────────────────────────────────────────────────────────


class TestACRCompliance:
    """Verify that valid traces achieve ACR = 1.0."""

    def test_single_valid_trace_acr_1(self) -> None:
        trace = _make_trace()
        acr = compute_acr([trace])
        assert acr == 1.0

    def test_multiple_valid_traces_acr_1(self) -> None:
        traces = [_make_trace(event_id=f"evt-{i}") for i in range(10)]
        acr = compute_acr(traces)
        assert acr == 1.0

    def test_empty_traces_acr_0(self) -> None:
        acr = compute_acr([])
        assert acr == 0.0

    def test_mixed_valid_invalid_acr(self) -> None:
        valid = _make_trace(event_id="good")
        invalid = {"specversion": "1.0", "id": "bad"}  # Incomplete
        acr = compute_acr([valid, invalid])
        assert acr == 0.5


# ── Emit Tests ───────────────────────────────────────────────────────


class TestEmitActionTrace:
    """Verify emit_action_trace() validation + emission."""

    def test_valid_trace_returns_true(self) -> None:
        trace = _make_trace()
        assert emit_action_trace(trace) is True

    def test_invalid_trace_returns_false(self) -> None:
        invalid = {"specversion": "1.0", "id": "bad"}
        assert emit_action_trace(invalid) is False

    @patch.dict("os.environ", {"METRICS_INGEST_URL": ""})
    def test_no_ingest_url_still_succeeds(self) -> None:
        trace = _make_trace()
        assert emit_action_trace(trace) is True

    @patch.dict("os.environ", {"METRICS_INGEST_URL": "http://localhost:9999/ingest"})
    def test_with_ingest_url_calls_emit(self) -> None:
        """When METRICS_INGEST_URL is set, emission is attempted."""
        trace = _make_trace()
        with patch("telemetry.trace_emitter.METRICS_INGEST_URL", "http://localhost:9999/ingest"), \
             patch("baseline.explainability.emit.emit_cloudevent") as mock_emit:
            result = emit_action_trace(trace)
            assert result is True
            mock_emit.assert_called_once()


# ── All Decision Types ───────────────────────────────────────────────


class TestAllDecisionTypes:
    """Ensure every decision type produces a valid ActionTrace."""

    @pytest.mark.parametrize(
        "decision",
        ["NO_OP", "BLOCK", "ROLLBACK", "QUARANTINE", "ESCALATE"],
    )
    def test_decision_type_produces_valid_trace(self, decision: str) -> None:
        from telemetry.policy_refs import get_policy_refs
        from models.schemas import DecisionType

        refs = get_policy_refs(DecisionType(decision))
        trace = _make_trace(decision=decision, policy_refs=refs or ["none"])
        valid, missing = validate_action_trace(trace)
        assert valid, f"{decision} trace missing: {missing}"

"""
Step 2 perception tests — z-score + threshold anomaly detection.

Tests cover:
  - z-score detection (normal vs. outlier)
  - Threshold detection per scenario (normal / warning / critical)
  - Combined scoring
  - Graceful degradation (no baseline → threshold-only)
  - perceive_anomaly tool with mocked BQ
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure runtime-agent root on sys.path
_AGENT_ROOT = str(Path(__file__).resolve().parent.parent)
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from agent.tools.anomaly_detection import (
    BaselineStats,
    ThresholdRule,
    compute_severity,
    threshold_severity,
    z_score_check,
    z_score_to_severity,
)

# ── Load mock baselines fixture ──────────────────────────────────────

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_bq_baselines.json"
_FIXTURES = json.loads(_FIXTURE_PATH.read_text())


def _make_baseline(scenario: str) -> BaselineStats:
    """Build a BaselineStats from the fixture file."""
    data = _FIXTURES[scenario]
    return BaselineStats(
        scenario_id=scenario,
        avg_duration=data["avg_duration"],
        stddev_duration=data["stddev_duration"],
        sample_count=data["sample_count"],
        metric_averages=data["metric_averages"],
        metric_stddevs=data["metric_stddevs"],
    )


# ── Z-Score Tests ────────────────────────────────────────────────────


class TestZScore:
    """Z-score detection unit tests."""

    def test_zero_stddev_returns_zero(self):
        assert z_score_check(100.0, 50.0, 0.0) == 0.0

    def test_normal_value(self):
        z = z_score_check(120.0, 120.0, 25.0)
        assert z == 0.0

    def test_one_sigma(self):
        z = z_score_check(145.0, 120.0, 25.0)
        assert z == pytest.approx(1.0)

    def test_two_sigma(self):
        z = z_score_check(170.0, 120.0, 25.0)
        assert z == pytest.approx(2.0)

    def test_three_sigma_outlier(self):
        z = z_score_check(195.0, 120.0, 25.0)
        assert z == pytest.approx(3.0)

    def test_negative_deviation(self):
        z = z_score_check(70.0, 120.0, 25.0)
        assert z == pytest.approx(2.0)


class TestZScoreToSeverity:
    """z-score → severity mapping."""

    def test_below_one_sigma(self):
        assert z_score_to_severity(0.5) == 0.0

    def test_at_one_sigma(self):
        assert z_score_to_severity(1.0) == pytest.approx(0.1)

    def test_at_one_point_five_sigma(self):
        assert z_score_to_severity(1.5) == pytest.approx(0.25)

    def test_at_two_sigma(self):
        assert z_score_to_severity(2.0) == pytest.approx(0.5)

    def test_at_two_point_five_sigma(self):
        assert z_score_to_severity(2.5) == pytest.approx(0.6)

    def test_at_three_sigma(self):
        assert z_score_to_severity(3.0) == pytest.approx(0.8)

    def test_extreme_outlier_capped_at_one(self):
        assert z_score_to_severity(5.0) == pytest.approx(1.0)


# ── Threshold Tests ──────────────────────────────────────────────────


class TestThresholdSeverity:
    """Threshold detection — above and below directions."""

    def test_above_normal(self):
        rule = ThresholdRule(
            metric="ttd_sec", warning=180.0, critical=300.0, direction="above"
        )
        assert threshold_severity(100.0, rule) == 0.0

    def test_above_warning(self):
        rule = ThresholdRule(
            metric="ttd_sec", warning=180.0, critical=300.0, direction="above"
        )
        sev = threshold_severity(200.0, rule)
        assert 0.5 <= sev < 0.7

    def test_above_critical(self):
        rule = ThresholdRule(
            metric="ttd_sec", warning=180.0, critical=300.0, direction="above"
        )
        sev = threshold_severity(350.0, rule)
        assert sev >= 0.8

    def test_below_normal(self):
        rule = ThresholdRule(
            metric="dsr", warning=0.95, critical=0.85, direction="below"
        )
        assert threshold_severity(0.98, rule) == 0.0

    def test_below_warning(self):
        rule = ThresholdRule(
            metric="dsr", warning=0.95, critical=0.85, direction="below"
        )
        sev = threshold_severity(0.92, rule)
        assert 0.5 <= sev < 0.8

    def test_below_critical(self):
        rule = ThresholdRule(
            metric="dsr", warning=0.95, critical=0.85, direction="below"
        )
        sev = threshold_severity(0.80, rule)
        assert sev >= 0.8


# ── Combined Scoring Tests ───────────────────────────────────────────


class TestCombinedScoring:
    """compute_severity tests with z-score + thresholds."""

    def test_normal_s1_with_baseline(self):
        """Normal S1 pipeline — low severity."""
        baseline = _make_baseline("S1")
        sev, risk = compute_severity(
            scenario_id="S1",
            duration_sec=115.0,
            event_metrics={"ttd_sec": 105.0},
            baseline=baseline,
        )
        assert sev < 0.3
        assert risk < 0.3

    def test_outlier_s1_with_baseline(self):
        """S1 pipeline with extreme duration — high severity via z-score."""
        baseline = _make_baseline("S1")
        sev, risk = compute_severity(
            scenario_id="S1",
            duration_sec=250.0,  # ~5σ from mean 120±25
            event_metrics={"ttd_sec": 250.0},
            baseline=baseline,
        )
        assert sev >= 0.7

    def test_s1_threshold_critical_without_baseline(self):
        """S1 exceeds critical TTD threshold — no baseline needed."""
        sev, risk = compute_severity(
            scenario_id="S1",
            duration_sec=350.0,
            baseline=None,
        )
        assert sev >= 0.8

    def test_s3_mttd_warning(self):
        """S3 MTTD exceeds warning threshold."""
        sev, risk = compute_severity(
            scenario_id="S3",
            event_metrics={"mttd_sec": 80.0},
            baseline=None,
        )
        assert 0.5 <= sev < 0.8

    def test_s3_mttr_critical_with_baseline(self):
        """S3 MTTR exceeds critical with z-score amplification."""
        baseline = _make_baseline("S3")
        sev, risk = compute_severity(
            scenario_id="S3",
            event_metrics={"mttr_sec": 350.0},
            baseline=baseline,
        )
        assert sev >= 0.8
        assert risk >= 0.8  # S3 weight = 1.0

    def test_s2_dsr_critical(self):
        """S2 delivery success rate below critical."""
        sev, risk = compute_severity(
            scenario_id="S2",
            event_metrics={"dsr": 0.80},
            baseline=None,
        )
        assert sev >= 0.8

    def test_s4_fdr_normal(self):
        """S4 false detection rate above warning threshold (normal)."""
        sev, risk = compute_severity(
            scenario_id="S4",
            event_metrics={"fdr": 0.95},
            baseline=None,
        )
        assert sev == 0.0

    def test_unknown_scenario_returns_neutral(self):
        """Unknown scenario with no metrics → neutral 0.5."""
        sev, risk = compute_severity(
            scenario_id="UNKNOWN",
            baseline=None,
        )
        assert sev == 0.5

    def test_risk_score_uses_weight(self):
        """S5 has weight 0.6 — risk_score < severity."""
        sev, risk = compute_severity(
            scenario_id="S5",
            baseline=None,
        )
        assert risk <= sev * 0.6 + 0.001

    def test_empty_baseline_ignored(self):
        """Baseline with sample_count < 3 is effectively ignored."""
        empty = _make_baseline("empty")
        sev, risk = compute_severity(
            scenario_id="S1",
            duration_sec=350.0,
            baseline=empty,
        )
        # Falls back to threshold-only → critical for 350s
        assert sev >= 0.8


# ── Graceful Degradation ─────────────────────────────────────────────


class TestGracefulDegradation:
    """Verify the tool works when BQ is unavailable."""

    @patch("agent.tools.perception_tool.query_baseline", return_value=None)
    def test_perceive_anomaly_no_bq(self, mock_bq):
        """perceive_anomaly works with BQ returning None."""
        from agent.tools.perception_tool import perceive_anomaly

        result = perceive_anomaly(
            event_id="test-degrade-001",
            event_type="pipeline_failure",
            source="test",
            occurred_at="2026-03-01T12:00:00Z",
            scenario_id="S1",
            status="fail",
            duration_sec=350.0,
        )
        assert isinstance(result, dict)
        assert result["severity"] >= 0.8  # threshold-only
        assert result["scenario"] == "S1"
        mock_bq.assert_called_once_with("S1")

    @patch("agent.tools.perception_tool.query_baseline", return_value=None)
    def test_perceive_anomaly_with_metrics_json(self, mock_bq):
        """metrics_json is parsed and used for threshold detection."""
        from agent.tools.perception_tool import perceive_anomaly

        result = perceive_anomaly(
            event_id="test-metrics-001",
            event_type="resilience_degradation",
            source="test",
            occurred_at="2026-03-01T12:00:00Z",
            scenario_id="S3",
            status="fail",
            metrics_json='{"mttd_sec": 150, "mttr_sec": 400}',
        )
        assert result["severity"] >= 0.8

    @patch("agent.tools.perception_tool.query_baseline", return_value=None)
    def test_perceive_anomaly_invalid_metrics_json(self, mock_bq):
        """Invalid metrics_json is silently ignored."""
        from agent.tools.perception_tool import perceive_anomaly

        result = perceive_anomaly(
            event_id="test-bad-json-001",
            event_type="pipeline_failure",
            source="test",
            occurred_at="2026-03-01T12:00:00Z",
            scenario_id="S1",
            status="fail",
            metrics_json="not valid json{",
        )
        assert isinstance(result, dict)
        # No metrics → neutral scenario
        assert result["severity"] == 0.5

    @patch("agent.tools.perception_tool.query_baseline")
    def test_perceive_anomaly_with_baseline(self, mock_bq):
        """Full path: BQ baseline + metrics → real scoring."""
        mock_bq.return_value = _make_baseline("S3")

        from agent.tools.perception_tool import perceive_anomaly

        result = perceive_anomaly(
            event_id="test-full-001",
            event_type="resilience_degradation",
            source="test",
            occurred_at="2026-03-01T12:00:00Z",
            scenario_id="S3",
            status="fail",
            duration_sec=100.0,  # ~5.5σ from mean 45±10
            metrics_json='{"mttd_sec": 75, "mttr_sec": 120}',
        )
        assert result["severity"] >= 0.7  # z-score or threshold triggers

    @patch("agent.tools.perception_tool.query_baseline", return_value=None)
    def test_perceive_unknown_scenario(self, mock_bq):
        """Unknown scenario → neutral severity, no BQ query."""
        from agent.tools.perception_tool import perceive_anomaly

        result = perceive_anomaly(
            event_id="test-unknown-001",
            event_type="manual_test_event",
            source="test",
            occurred_at="2026-03-01T12:00:00Z",
        )
        assert result["severity"] == 0.5
        assert result["scenario"] == "unknown"
        mock_bq.assert_not_called()  # unknown scenario skips BQ

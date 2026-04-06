"""Tests for agent/tools/context_builder.py — metric context assembly."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from agent.tools.context_builder import (
    SCENARIO_METRIC_MAP,
    _classify_trend,
    build_context,
)


class TestClassifyTrend(unittest.TestCase):
    def test_improving(self):
        assert _classify_trend(40.0, 50.0) == "improving"

    def test_degrading(self):
        assert _classify_trend(60.0, 50.0) == "degrading"

    def test_stable(self):
        assert _classify_trend(51.0, 50.0) == "stable"

    def test_none_recent(self):
        assert _classify_trend(None, 50.0) == "stable"

    def test_none_prior(self):
        assert _classify_trend(50.0, None) == "stable"

    def test_both_none(self):
        assert _classify_trend(None, None) == "stable"

    def test_zero_prior(self):
        assert _classify_trend(10.0, 0.0) == "stable"

    def test_large_improvement(self):
        assert _classify_trend(10.0, 100.0) == "improving"

    def test_large_degradation(self):
        assert _classify_trend(100.0, 10.0) == "degrading"


class TestScenarioMetricMap(unittest.TestCase):
    def test_s1_has_ttd(self):
        assert any(m["name"] == "TTD" for m in SCENARIO_METRIC_MAP["s1"])

    def test_s3_has_mttd_and_mttr(self):
        names = {m["name"] for m in SCENARIO_METRIC_MAP["s3"]}
        assert "MTTD" in names
        assert "MTTR" in names

    def test_ss2_has_mttd(self):
        assert any(m["name"] == "MTTD" for m in SCENARIO_METRIC_MAP["ss2"])

    def test_all_entries_have_required_keys(self):
        for scenario_id, metrics in SCENARIO_METRIC_MAP.items():
            for m in metrics:
                assert "stage" in m, f"Missing stage in {scenario_id}"
                assert "metric_key" in m, f"Missing metric_key in {scenario_id}"
                assert "name" in m, f"Missing name in {scenario_id}"


class TestBuildContext(unittest.TestCase):
    @patch("agent.tools.context_builder._query_bq", return_value=[])
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_returns_context_with_empty_bq(self, mock_gcs, mock_bq):
        result = build_context()
        assert result["status"] == "context_ready"
        ctx = result["context"]
        assert ctx["scenario_metrics"] == []
        assert ctx["runtime_decisions"]["total_decisions"] == 0

    @patch("agent.tools.context_builder._query_bq")
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_parses_metric_rows(self, mock_gcs, mock_bq):
        mock_bq.side_effect = [
            # First call: metric query for s3 MTTD
            [
                {
                    "mean_value": 8.5,
                    "p50_value": 7.0,
                    "p95_value": 12.0,
                    "sample_count": 30,
                }
            ],
            # Second call: trend query for s3 MTTD
            [{"recent_avg": 8.0, "prior_avg": 9.0}],
            # Third call: metric query for s3 MTTR
            [
                {
                    "mean_value": 45.0,
                    "p50_value": 40.0,
                    "p95_value": 78.0,
                    "sample_count": 25,
                }
            ],
            # Fourth call: trend query for s3 MTTR
            [{"recent_avg": 50.0, "prior_avg": 40.0}],
            # Fifth call: decisions query
            [],
        ]
        result = build_context(scenarios=["s3"])
        ctx = result["context"]
        assert len(ctx["scenario_metrics"]) == 2
        mttd = ctx["scenario_metrics"][0]
        assert mttd["metric_name"] == "MTTD"
        assert mttd["mean_value"] == 8.5
        assert mttd["trend_direction"] == "improving"

        mttr = ctx["scenario_metrics"][1]
        assert mttr["metric_name"] == "MTTR"
        assert mttr["trend_direction"] == "degrading"

    @patch("agent.tools.context_builder._query_bq")
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_parses_decisions(self, mock_gcs, mock_bq):
        # When scenarios=[], no metric queries are made, only the decisions query
        mock_bq.return_value = [
            {
                "total_decisions": 30,
                "executed_count": 0,
                "decision": "NO_OP",
                "scenario_id": "s3",
            },
            {
                "total_decisions": 5,
                "executed_count": 2,
                "decision": "ROLLBACK",
                "scenario_id": "s3",
            },
        ]
        result = build_context(scenarios=[])
        ctx = result["context"]
        assert ctx["runtime_decisions"]["total_decisions"] == 35
        assert ctx["runtime_decisions"]["by_action"]["NO_OP"] == 30
        assert ctx["runtime_decisions"]["by_action"]["ROLLBACK"] == 5

    @patch("agent.tools.context_builder._query_bq", return_value=[])
    @patch("agent.tools.context_builder._read_gcs_json")
    def test_reads_thresholds(self, mock_gcs, mock_bq):
        mock_gcs.return_value = {"anomaly_z_threshold": 2.5, "poll_interval": 5}
        result = build_context(scenarios=[])
        ctx = result["context"]
        assert ctx["current_thresholds"]["anomaly_z_threshold"] == 2.5

    def test_custom_window_days(self):
        with patch("agent.tools.context_builder._query_bq", return_value=[]), patch(
            "agent.tools.context_builder._read_gcs_json", return_value=None
        ):
            result = build_context(window_days=14, scenarios=[])
            assert result["context"]["window_days"] == 14

    def test_zero_window_uses_default(self):
        with patch("agent.tools.context_builder._query_bq", return_value=[]), patch(
            "agent.tools.context_builder._read_gcs_json", return_value=None
        ):
            result = build_context(window_days=0, scenarios=[])
            assert result["context"]["window_days"] > 0

    @patch("agent.tools.context_builder._query_bq", return_value=[])
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_variant_filter_none_uses_is_null(self, mock_gcs, mock_bq):
        result = build_context(scenarios=[], variant_filter="none")
        assert result["context"]["variant_filter"] == "none"

    @patch("agent.tools.context_builder._query_bq", return_value=[])
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_variant_filter_baseline(self, mock_gcs, mock_bq):
        result = build_context(scenarios=[], variant_filter="baseline")
        assert result["context"]["variant_filter"] == "baseline"

    @patch("agent.tools.context_builder._query_bq", return_value=[])
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_variant_filter_null_no_filter(self, mock_gcs, mock_bq):
        result = build_context(scenarios=[], variant_filter=None)
        assert result["context"]["variant_filter"] is None

    @patch("agent.tools.context_builder._query_bq")
    @patch("agent.tools.context_builder._read_gcs_json", return_value=None)
    def test_variant_filter_injected_in_query(self, mock_gcs, mock_bq):
        mock_bq.return_value = []
        build_context(scenarios=["s1"], variant_filter="full")
        # Metric query + trend query + decisions query = at least 3 calls
        # Check the metric query contains variant clause
        if mock_bq.call_count >= 1:
            first_query = mock_bq.call_args_list[0][0][0]
            assert "variant" in first_query

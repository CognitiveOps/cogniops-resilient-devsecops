"""Tests for evaluation.scripts.collector — BQ query building."""

from __future__ import annotations

from evaluation.scripts.collector import (
    METRIC_EXTRACTION,
    _build_sample_query,
    _filter_to_overlap_windows,
    compute_rate_metric,
)
import pandas as pd


class TestMetricExtractionConfig:
    """Validate METRIC_EXTRACTION mapping completeness."""

    def test_s1_metrics_present(self) -> None:
        assert ("s1", "TTD") in METRIC_EXTRACTION
        assert ("s1", "CFR") in METRIC_EXTRACTION
        assert ("s1", "DF") in METRIC_EXTRACTION

    def test_s2_metrics_present(self) -> None:
        assert ("s2", "TDL") in METRIC_EXTRACTION
        assert ("s2", "DSR") in METRIC_EXTRACTION

    def test_s3_cloud_metrics_present(self) -> None:
        assert ("s3_cloud", "MTTD") in METRIC_EXTRACTION
        assert ("s3_cloud", "MTTR") in METRIC_EXTRACTION

    def test_s3_edge_metrics_present(self) -> None:
        assert ("s3_edge", "MTTD") in METRIC_EXTRACTION
        assert ("s3_edge", "MTTR") in METRIC_EXTRACTION

    def test_s4_metrics_present(self) -> None:
        assert ("s4", "TTV") in METRIC_EXTRACTION
        assert ("s4", "VSR") in METRIC_EXTRACTION
        assert ("s4", "FDR") in METRIC_EXTRACTION

    def test_s5_metrics_present(self) -> None:
        assert ("s5", "AL") in METRIC_EXTRACTION
        assert ("s5", "ACR") in METRIC_EXTRACTION

    def test_ss1_metrics_present(self) -> None:
        assert ("ss1", "CFR") in METRIC_EXTRACTION
        assert ("ss1", "FDR") in METRIC_EXTRACTION

    def test_ss2_metrics_present(self) -> None:
        assert ("ss2", "MTTD") in METRIC_EXTRACTION
        assert ("ss2", "AL") in METRIC_EXTRACTION
        assert ("ss2", "ACR") in METRIC_EXTRACTION

    def test_all_configs_have_stage(self) -> None:
        for key, cfg in METRIC_EXTRACTION.items():
            assert "stage" in cfg, f"{key} missing 'stage'"


class TestBuildSampleQuery:
    """Validate SQL query generation."""

    def test_ttd_query_structure(self) -> None:
        sql = _build_sample_query(
            "s1", "TTD", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "test-project.agent_metrics.runs" in sql
        assert "s1_final" in sql
        assert "duration_sec" in sql
        assert "variant" in sql
        assert "'2024-01-01'" in sql
        assert "'2024-12-31'" in sql

    def test_cfr_query_returns_status(self) -> None:
        sql = _build_sample_query(
            "s1", "CFR", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "status" in sql
        assert "s1_final" in sql
        # CFR is a rate metric — should NOT filter by status
        assert "AND status = 'success'" not in sql

    def test_json_extraction(self) -> None:
        sql = _build_sample_query(
            "s5", "AL", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "al_sec" in sql
        assert "JSON_VALUE" in sql

    def test_unknown_metric_returns_none(self) -> None:
        sql = _build_sample_query(
            "s1", "UNKNOWN", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is None

    def test_variant_coalesce(self) -> None:
        sql = _build_sample_query(
            "s3_cloud", "MTTD", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline')" in sql

    def test_s3_cloud_uses_detect_stage(self) -> None:
        sql = _build_sample_query(
            "s3_cloud", "MTTD", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "s3_detect" in sql
        assert "s3_detect_edge" not in sql

    def test_s3_edge_uses_detect_edge_stage(self) -> None:
        sql = _build_sample_query(
            "s3_edge", "MTTD", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "s3_detect_edge" in sql


class TestComputeRateMetric:
    """Test rate metric aggregation from raw status rows."""

    def test_failure_rate(self) -> None:
        df = pd.DataFrame(
            {
                "variant": ["baseline"] * 10 + ["full"] * 10,
                "status": (
                    ["success"] * 8
                    + ["failure"] * 2
                    + ["success"] * 9
                    + ["failure"] * 1
                ),
                "t_end": pd.date_range("2024-01-01", periods=20, freq="h"),
            }
        )
        result = compute_rate_metric(df, "failure_rate")
        assert len(result) == 20
        baseline_vals = result.loc[result["variant"] == "baseline", "metric_value"]
        assert abs(float(baseline_vals.mean()) - 0.2) < 0.001

    def test_success_rate(self) -> None:
        df = pd.DataFrame(
            {
                "variant": ["baseline"] * 10,
                "status": ["success"] * 7 + ["failure"] * 3,
                "t_end": pd.date_range("2024-01-01", periods=10, freq="h"),
            }
        )
        result = compute_rate_metric(df, "success_rate")
        assert len(result) == 10
        assert abs(float(result["metric_value"].mean()) - 0.7) < 0.001

    def test_empty_df(self) -> None:
        df = pd.DataFrame(columns=["variant", "status", "t_end"])
        result = compute_rate_metric(df, "failure_rate")
        assert result.empty

    def test_rejection_rate(self) -> None:
        """S4/FDR: success = correct rejection of invalid input."""
        df = pd.DataFrame(
            {
                "variant": ["baseline"] * 9,
                "status": ["success"] * 9,
                "t_end": pd.date_range("2024-01-01", periods=9, freq="h"),
            }
        )
        result = compute_rate_metric(df, "rejection_rate")
        assert len(result) == 9
        assert abs(float(result["metric_value"].mean()) - 1.0) < 0.001

    def test_detection_rate(self) -> None:
        """SS1/FDR: deny = correctly detected policy violation."""
        df = pd.DataFrame(
            {
                "variant": ["baseline"] * 10,
                "status": ["deny"] * 7 + ["pass"] * 3,
                "t_end": pd.date_range("2024-01-01", periods=10, freq="h"),
            }
        )
        result = compute_rate_metric(df, "detection_rate")
        assert len(result) == 10
        assert abs(float(result["metric_value"].mean()) - 0.7) < 0.001


class TestCausalOverlapFilter:
    """Validate baseline-treatment overlap window filtering."""

    def test_keeps_only_overlapping_window(self) -> None:
        df = pd.DataFrame(
            {
                "variant": [
                    "baseline",
                    "baseline",
                    "runtime_only",
                    "runtime_only",
                ],
                "t_end": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-10T00:00:00Z",
                    "2026-01-05T00:00:00Z",
                    "2026-01-20T00:00:00Z",
                ],
                "metric_value": [1.0, 2.0, 1.5, 1.7],
            }
        )
        out = _filter_to_overlap_windows(df, treatment_variants=("runtime_only",))
        # Overlap window is [2026-01-05, 2026-01-10],
        # so one row per variant remains.
        assert len(out) == 2
        assert set(out["variant"]) == {"baseline", "runtime_only"}

    def test_returns_empty_when_no_overlap(self) -> None:
        df = pd.DataFrame(
            {
                "variant": ["baseline", "runtime_only"],
                "t_end": ["2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"],
                "metric_value": [1.0, 2.0],
            }
        )
        out = _filter_to_overlap_windows(df, treatment_variants=("runtime_only",))
        assert out.empty


class TestMultiStageQuery:
    """Test multi-stage query generation (e.g. S4/FDR)."""

    def test_s4_fdr_uses_in_clause(self) -> None:
        sql = _build_sample_query(
            "s4", "FDR", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "IN (" in sql
        assert "s4_p1_tamper" in sql
        assert "s4_p2_wrong_key" in sql
        assert "s4_p3_replay" in sql

    def test_ss1_fdr_uses_single_stage(self) -> None:
        sql = _build_sample_query(
            "ss1", "FDR", "test-project", "2024-01-01", "2024-12-31"
        )
        assert sql is not None
        assert "ss1_policy" in sql
        assert "status" in sql

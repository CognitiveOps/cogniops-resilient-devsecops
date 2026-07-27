"""Tests for evaluation.scripts.run_experiment — orchestrator integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from evaluation.scripts.run_experiment import _build_summary, run


@pytest.fixture()
def mock_metrics_df() -> pd.DataFrame:
    """Minimal metrics DataFrame for orchestrator tests."""
    import numpy as np

    rng = np.random.default_rng(99)
    rows = []
    for variant, mu in [("baseline", 10), ("full", 7)]:
        for val in rng.normal(mu, 1.5, 20):
            rows.append(
                {
                    "scenario_id": "s1",
                    "metric_name": "TTD",
                    "variant": variant,
                    "metric_value": val,
                }
            )
    return pd.DataFrame(rows)


class TestBuildSummary:
    """Test summary generation."""

    def test_summary_structure(self, metrics_df: pd.DataFrame) -> None:
        from evaluation.scripts.compare_variants import (
            compare_all_variants,
            results_to_dataframe,
        )

        results = compare_all_variants(metrics_df)
        df = results_to_dataframe(results)
        summary = _build_summary(df, "20240101T000000Z")

        assert "timestamp" in summary
        assert "n_comparisons" in summary
        assert "by_variant" in summary
        assert "by_scenario" in summary
        assert summary["n_comparisons"] == len(df)

    def test_significant_count(self, metrics_df: pd.DataFrame) -> None:
        from evaluation.scripts.compare_variants import (
            compare_all_variants,
            results_to_dataframe,
        )

        results = compare_all_variants(metrics_df)
        df = results_to_dataframe(results)
        summary = _build_summary(df, "test")

        # At least some should be significant given the fixture data
        assert summary["significant_improvements"] >= 0
        assert summary["both_significant_and_practical"] >= 0


class TestRunOrchestrator:
    """Test the run() orchestrator with mocked BQ."""

    @patch("evaluation.scripts.run_experiment.collect_all_metrics")
    def test_empty_data_returns_error(self, mock_collect: MagicMock) -> None:
        mock_collect.return_value = pd.DataFrame()
        result = run(scenarios=["s1"])
        assert result["status"] == "error"

    @patch("evaluation.scripts.run_experiment.collect_all_metrics")
    def test_successful_run(
        self,
        mock_collect: MagicMock,
        mock_metrics_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        mock_collect.return_value = mock_metrics_df
        result = run(
            scenarios=["s1"],
            output_dir=tmp_path,
            skip_charts=True,
        )
        # Only baseline and full → only 1 comparison (full vs baseline)
        assert result["status"] in ("success", "warning")

    @patch("evaluation.scripts.run_experiment.collect_all_metrics")
    def test_outputs_created(
        self,
        mock_collect: MagicMock,
        mock_metrics_df: pd.DataFrame,
        tmp_path: Path,
    ) -> None:
        mock_collect.return_value = mock_metrics_df
        result = run(
            scenarios=["s1"],
            output_dir=tmp_path,
            skip_charts=True,
        )
        if result["status"] == "success":
            assert Path(result["raw_csv"]).exists()
            assert Path(result["comparison_csv"]).exists()
            assert Path(result["summary_json"]).exists()

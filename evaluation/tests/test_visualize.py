"""Tests for evaluation.scripts.visualize — chart generation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from evaluation.scripts.compare_variants import (
    compare_all_variants,
    results_to_dataframe,
)
from evaluation.scripts.visualize import (
    bar_chart_metric,
    effect_size_heatmap,
    generate_all_charts,
    two_axis_quadrant,
)


@pytest.fixture()
def comparison_df(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Comparison results from fixture data."""
    results = compare_all_variants(metrics_df)
    return results_to_dataframe(results)


class TestBarChart:
    """Test bar chart generation."""

    def test_generates_png(self, comparison_df: pd.DataFrame, tmp_path: Path) -> None:
        path = bar_chart_metric(comparison_df, "s1", "TTD", output_dir=tmp_path)
        assert path is not None
        assert path.exists()
        assert path.suffix == ".png"

    def test_returns_none_for_missing(
        self, comparison_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        path = bar_chart_metric(comparison_df, "unknown", "FAKE", output_dir=tmp_path)
        assert path is None


class TestHeatmap:
    """Test heatmap generation."""

    def test_generates_png(self, comparison_df: pd.DataFrame, tmp_path: Path) -> None:
        path = effect_size_heatmap(comparison_df, output_dir=tmp_path)
        assert path is not None
        assert path.exists()
        assert "heatmap" in path.name

    def test_empty_df_returns_none(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            columns=["treatment_variant", "scenario_id", "metric_name", "cohens_d"]
        )
        path = effect_size_heatmap(df, output_dir=tmp_path)
        assert path is None


class TestQuadrantChart:
    """Test 2-axis quadrant chart."""

    def test_generates_png(self, comparison_df: pd.DataFrame, tmp_path: Path) -> None:
        path = two_axis_quadrant(comparison_df, output_dir=tmp_path)
        assert path is not None
        assert path.exists()
        assert "quadrant" in path.name

    def test_empty_returns_none(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            columns=[
                "treatment_variant",
                "scenario_id",
                "metric_name",
                "delta_pct",
                "direction",
            ]
        )
        path = two_axis_quadrant(df, output_dir=tmp_path)
        assert path is None


class TestGenerateAllCharts:
    """Test the full chart generation pipeline."""

    def test_generates_multiple(
        self, comparison_df: pd.DataFrame, tmp_path: Path
    ) -> None:
        paths = generate_all_charts(comparison_df, output_dir=tmp_path)
        # At least: 2 bar charts (s1/TTD, s3/MTTD) + 1 heatmap + 1 quadrant = 4
        assert len(paths) >= 4
        for p in paths:
            assert p.exists()

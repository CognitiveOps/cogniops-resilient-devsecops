"""Tests for evaluation.scripts.compare_variants — statistical comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evaluation.scripts.compare_variants import (
    ComparisonResult,
    _bootstrap_ci,
    _cohens_d,
    _effect_magnitude,
    compare_all_variants,
    compare_pair,
    results_to_dataframe,
)


class TestCohensD:
    """Unit tests for Cohen's d calculation."""

    def test_identical_distributions(self) -> None:
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        d = _cohens_d(a, a.copy())
        assert abs(d) < 0.01

    def test_large_effect(self, rng: np.random.Generator) -> None:
        a = rng.normal(0, 1, 100)
        b = rng.normal(2, 1, 100)
        d = _cohens_d(a, b)
        assert d > 1.5  # expect ~2.0

    def test_small_samples_returns_zero(self) -> None:
        a = np.array([1.0])
        b = np.array([2.0])
        d = _cohens_d(a, b)
        assert d == 0.0

    def test_zero_variance(self) -> None:
        a = np.array([5.0, 5.0, 5.0])
        b = np.array([5.0, 5.0, 5.0])
        d = _cohens_d(a, b)
        assert d == 0.0


class TestEffectMagnitude:
    """Unit tests for effect magnitude classification."""

    def test_negligible(self) -> None:
        assert _effect_magnitude(0.1) == "negligible"

    def test_small(self) -> None:
        assert _effect_magnitude(0.3) == "small"

    def test_medium(self) -> None:
        assert _effect_magnitude(0.6) == "medium"

    def test_large(self) -> None:
        assert _effect_magnitude(1.0) == "large"

    def test_negative_uses_absolute(self) -> None:
        assert _effect_magnitude(-0.9) == "large"


class TestBootstrapCI:
    """Unit tests for bootstrap confidence interval."""

    def test_ci_contains_true_delta(self, rng: np.random.Generator) -> None:
        a = rng.normal(10, 2, 50)
        b = rng.normal(8, 2, 50)
        lo, hi = _bootstrap_ci(a, b, rng=rng)
        true_delta = np.mean(b) - np.mean(a)
        assert lo <= true_delta <= hi

    def test_ci_bounds_ordered(self, rng: np.random.Generator) -> None:
        a = rng.normal(5, 1, 30)
        b = rng.normal(5, 1, 30)
        lo, hi = _bootstrap_ci(a, b, rng=rng)
        assert lo < hi


class TestComparePair:
    """Unit tests for compare_pair function."""

    def test_significant_improvement(
        self,
        baseline_samples: np.ndarray,
        improved_samples: np.ndarray,
    ) -> None:
        result = compare_pair(
            scenario_id="s1",
            metric_name="TTD",
            baseline_samples=baseline_samples,
            treatment_samples=improved_samples,
            treatment_variant="full",
            direction="lower_is_better",
        )
        assert result is not None
        assert result.significant == True
        assert result.improved == True
        assert result.delta < 0
        assert result.cohens_d < 0  # treatment is lower
        assert result.effect_magnitude in ("medium", "large")

    def test_no_improvement(
        self,
        baseline_samples: np.ndarray,
        unchanged_samples: np.ndarray,
    ) -> None:
        result = compare_pair(
            scenario_id="s1",
            metric_name="TTD",
            baseline_samples=baseline_samples,
            treatment_samples=unchanged_samples,
            treatment_variant="design_only",
            direction="lower_is_better",
        )
        assert result is not None
        assert result.effect_magnitude in ("negligible", "small")

    def test_insufficient_samples_returns_none(
        self,
        baseline_samples: np.ndarray,
        small_samples: np.ndarray,
    ) -> None:
        result = compare_pair(
            scenario_id="s1",
            metric_name="TTD",
            baseline_samples=baseline_samples,
            treatment_samples=small_samples,
            treatment_variant="runtime_only",
            direction="lower_is_better",
        )
        assert result is None

    def test_higher_is_better_direction(
        self,
        rng: np.random.Generator,
    ) -> None:
        baseline = rng.normal(0.7, 0.05, 30)
        treatment = rng.normal(0.9, 0.05, 30)
        result = compare_pair(
            scenario_id="s5",
            metric_name="ACR",
            baseline_samples=baseline,
            treatment_samples=treatment,
            treatment_variant="full",
            direction="higher_is_better",
        )
        assert result is not None
        assert result.improved is True
        assert result.delta > 0

    def test_result_fields_populated(
        self,
        baseline_samples: np.ndarray,
        improved_samples: np.ndarray,
    ) -> None:
        result = compare_pair(
            scenario_id="s3",
            metric_name="MTTD",
            baseline_samples=baseline_samples,
            treatment_samples=improved_samples,
            treatment_variant="runtime_only",
            direction="lower_is_better",
        )
        assert result is not None
        assert result.scenario_id == "s3"
        assert result.metric_name == "MTTD"
        assert result.baseline_variant == "baseline"
        assert result.treatment_variant == "runtime_only"
        assert result.n_baseline == 30
        assert result.n_treatment == 30
        assert result.ci_lower < result.ci_upper
        assert 0 <= result.p_value <= 1


class TestCompareAllVariants:
    """Integration tests for compare_all_variants."""

    def test_returns_results_for_all_metrics(
        self,
        metrics_df: pd.DataFrame,
    ) -> None:
        results = compare_all_variants(metrics_df)
        # 2 metrics × 3 treatments = 6 comparisons
        assert len(results) == 6

    def test_all_result_types(
        self,
        metrics_df: pd.DataFrame,
    ) -> None:
        results = compare_all_variants(metrics_df)
        variants_seen = {r.treatment_variant for r in results}
        assert variants_seen == {"design_only", "runtime_only", "full"}

    def test_results_to_dataframe(
        self,
        metrics_df: pd.DataFrame,
    ) -> None:
        results = compare_all_variants(metrics_df)
        df = results_to_dataframe(results)
        assert len(df) == len(results)
        assert "scenario_id" in df.columns
        assert "cohens_d" in df.columns
        assert "p_value" in df.columns

    def test_s1_ttd_full_is_improved(
        self,
        metrics_df: pd.DataFrame,
    ) -> None:
        """In fixture data, full variant has μ=7 vs baseline μ=10."""
        results = compare_all_variants(metrics_df)
        s1_full = [
            r
            for r in results
            if r.scenario_id == "s1"
            and r.metric_name == "TTD"
            and r.treatment_variant == "full"
        ]
        assert len(s1_full) == 1
        assert s1_full[0].improved == True
        assert s1_full[0].significant == True

    def test_s3_mttd_design_no_improvement(
        self,
        metrics_df: pd.DataFrame,
    ) -> None:
        """In fixture data, design_only has μ=5 same as baseline μ=5."""
        results = compare_all_variants(metrics_df)
        s3_design = [
            r
            for r in results
            if r.scenario_id == "s3"
            and r.metric_name == "MTTD"
            and r.treatment_variant == "design_only"
        ]
        assert len(s3_design) == 1
        assert s3_design[0].effect_magnitude in ("negligible", "small")

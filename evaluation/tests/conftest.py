"""Shared fixtures for evaluation tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def rng() -> np.random.Generator:
    """Deterministic RNG for reproducible tests."""
    return np.random.default_rng(42)


@pytest.fixture()
def baseline_samples(rng: np.random.Generator) -> np.ndarray:
    """Baseline metric samples — μ=10, σ=2, n=30."""
    return rng.normal(loc=10.0, scale=2.0, size=30)


@pytest.fixture()
def improved_samples(rng: np.random.Generator) -> np.ndarray:
    """Treatment samples that are clearly better (lower) — μ=7, σ=1.5, n=30."""
    return rng.normal(loc=7.0, scale=1.5, size=30)


@pytest.fixture()
def unchanged_samples(rng: np.random.Generator) -> np.ndarray:
    """Treatment samples with no improvement — μ=10.1, σ=2, n=30."""
    return rng.normal(loc=10.1, scale=2.0, size=30)


@pytest.fixture()
def small_samples(rng: np.random.Generator) -> np.ndarray:
    """Too few samples to be statistically valid — n=5."""
    return rng.normal(loc=8.0, scale=2.0, size=5)


@pytest.fixture()
def metrics_df(rng: np.random.Generator) -> pd.DataFrame:
    """Long-format metrics DataFrame with all 4 variants for s1/TTD and s3/MTTD."""
    rows = []
    # s1/TTD: baseline μ=10, design μ=8, runtime μ=9, full μ=7
    for variant, mu in [
        ("baseline", 10),
        ("design_only", 8),
        ("runtime_only", 9),
        ("full", 7),
    ]:
        for val in rng.normal(loc=mu, scale=1.5, size=20):
            rows.append(
                {
                    "scenario_id": "s1",
                    "metric_name": "TTD",
                    "variant": variant,
                    "metric_value": val,
                }
            )
    # s3_cloud/MTTD: baseline μ=5, design μ=5, runtime μ=3, full μ=3
    for variant, mu in [
        ("baseline", 5),
        ("design_only", 5),
        ("runtime_only", 3),
        ("full", 3),
    ]:
        for val in rng.normal(loc=mu, scale=0.8, size=20):
            rows.append(
                {
                    "scenario_id": "s3_cloud",
                    "metric_name": "MTTD",
                    "variant": variant,
                    "metric_value": val,
                }
            )
    return pd.DataFrame(rows)

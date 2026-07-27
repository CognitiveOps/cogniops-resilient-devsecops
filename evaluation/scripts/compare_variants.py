"""
Compare Variants — statistical comparison of metric samples across variants.

Implements the 2-Axis Evaluation Model:
  Axis 1 (Design-Time Intelligence): baseline → design_only
  Axis 2 (Runtime Intelligence):     baseline → runtime_only
  Combined:                           baseline → full

Statistical methods:
  - Mann-Whitney U test (non-parametric, two-sided)
  - Cohen's d effect size
  - Bootstrap 95% CI for mean difference
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("evaluation.compare")

CONFIGS_DIR = Path(__file__).resolve().parent.parent / "configs"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


@dataclass
class ComparisonResult:
    """Result of comparing two variant sample distributions."""

    scenario_id: str
    metric_name: str
    baseline_variant: str
    treatment_variant: str
    n_baseline: int
    n_treatment: int
    mean_baseline: float
    mean_treatment: float
    std_baseline: float
    std_treatment: float
    delta: float
    delta_pct: float
    direction: str  # "lower_is_better" or "higher_is_better"
    improved: bool
    p_value: float
    statistic: float
    cohens_d: float
    effect_magnitude: str  # "negligible", "small", "medium", "large"
    ci_lower: float
    ci_upper: float
    significant: bool
    practical: bool


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Cohen's d (pooled std)."""
    n_a, n_b = len(a), len(b)
    if n_a < 2 or n_b < 2:
        return 0.0
    var_a = np.var(a, ddof=1)
    var_b = np.var(b, ddof=1)
    pooled_std = np.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))
    if pooled_std == 0:
        return 0.0
    return float((np.mean(b) - np.mean(a)) / pooled_std)


def _effect_magnitude(d: float) -> str:
    """Classify effect size per Cohen's conventions."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def _bootstrap_ci(
    a: np.ndarray,
    b: np.ndarray,
    n_boot: int = 10000,
    ci: float = 0.95,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Bootstrap confidence interval for mean(b) - mean(a)."""
    rng = rng or np.random.default_rng(42)
    deltas = np.empty(n_boot)
    for i in range(n_boot):
        sa = rng.choice(a, size=len(a), replace=True)
        sb = rng.choice(b, size=len(b), replace=True)
        deltas[i] = np.mean(sb) - np.mean(sa)
    alpha = (1 - ci) / 2
    return float(np.percentile(deltas, alpha * 100)), float(
        np.percentile(deltas, (1 - alpha) * 100)
    )


def load_thresholds() -> dict:
    """Load statistical thresholds from configs."""
    path = CONFIGS_DIR / "thresholds.json"
    with open(path) as f:
        return json.load(f)


def compare_pair(
    scenario_id: str,
    metric_name: str,
    baseline_samples: np.ndarray,
    treatment_samples: np.ndarray,
    treatment_variant: str,
    direction: str = "lower_is_better",
    thresholds: dict | None = None,
) -> ComparisonResult | None:
    """Compare treatment vs baseline for one metric.

    Returns None if sample sizes are insufficient.
    """
    thresholds = thresholds or load_thresholds()
    min_samples = thresholds["statistical"]["min_samples_per_variant"]

    n_b = len(baseline_samples)
    n_t = len(treatment_samples)
    if n_b < min_samples or n_t < min_samples:
        logger.warning(
            "%s/%s %s: insufficient samples (baseline=%d, treatment=%d, min=%d)",
            scenario_id,
            metric_name,
            treatment_variant,
            n_b,
            n_t,
            min_samples,
        )
        return None

    mean_b = float(np.mean(baseline_samples))
    mean_t = float(np.mean(treatment_samples))
    std_b = float(np.std(baseline_samples, ddof=1))
    std_t = float(np.std(treatment_samples, ddof=1))
    delta = mean_t - mean_b
    delta_pct = (delta / mean_b * 100) if mean_b != 0 else 0.0

    # Direction of improvement
    if direction == "lower_is_better":
        improved = delta < 0
    else:
        improved = delta > 0

    # Mann-Whitney U test
    stat_val, p_val = stats.mannwhitneyu(
        baseline_samples, treatment_samples, alternative="two-sided"
    )

    # Effect size
    d = _cohens_d(baseline_samples, treatment_samples)
    magnitude = _effect_magnitude(d)

    # Bootstrap CI
    ci_lo, ci_hi = _bootstrap_ci(baseline_samples, treatment_samples)

    # Significance
    alpha = thresholds["statistical"]["alpha"]
    significant = p_val < alpha

    # Practical relevance
    practical_thresholds = thresholds.get("practical", {})
    metric_threshold = practical_thresholds.get(metric_name, {})
    min_delta = metric_threshold.get("meaningful_delta_pct", 5)
    practical = abs(delta_pct) >= min_delta

    return ComparisonResult(
        scenario_id=scenario_id,
        metric_name=metric_name,
        baseline_variant="baseline",
        treatment_variant=treatment_variant,
        n_baseline=n_b,
        n_treatment=n_t,
        mean_baseline=mean_b,
        mean_treatment=mean_t,
        std_baseline=std_b,
        std_treatment=std_t,
        delta=delta,
        delta_pct=delta_pct,
        direction=direction,
        improved=improved,
        p_value=p_val,
        statistic=stat_val,
        cohens_d=d,
        effect_magnitude=magnitude,
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        significant=significant,
        practical=practical,
    )


def compare_all_variants(
    metrics_df: pd.DataFrame,
    direction_map: dict[str, str] | None = None,
) -> list[ComparisonResult]:
    """Compare all treatment variants against baseline for every scenario/metric.

    Args:
        metrics_df: Long-format DF with columns: scenario_id, metric_name, variant, metric_value
        direction_map: metric_name → "lower_is_better" / "higher_is_better"
    """
    from evaluation.configs import load_experiment_matrix

    matrix = load_experiment_matrix()
    thresholds = load_thresholds()

    # Build direction map from experiment matrix if not supplied
    if direction_map is None:
        direction_map = {}
        for _sid, scfg in matrix["scenarios"].items():
            for metric_name_key, stage_cfg in scfg.get("stages", {}).items():
                if stage_cfg.get("lower_is_better"):
                    direction_map.setdefault(metric_name_key, "lower_is_better")
                elif stage_cfg.get("higher_is_better"):
                    direction_map.setdefault(metric_name_key, "higher_is_better")
                else:
                    direction_map.setdefault(metric_name_key, "lower_is_better")

    treatment_variants = ["design_only", "runtime_only", "full"]
    results: list[ComparisonResult] = []

    for (scenario_id, metric_name), group in metrics_df.groupby(
        ["scenario_id", "metric_name"]
    ):
        baseline_vals = group.loc[
            group["variant"] == "baseline", "metric_value"
        ].to_numpy(dtype=float)

        direction = direction_map.get(str(metric_name), "lower_is_better")

        for tv in treatment_variants:
            treatment_vals = group.loc[group["variant"] == tv, "metric_value"].to_numpy(
                dtype=float
            )

            result = compare_pair(
                scenario_id=str(scenario_id),
                metric_name=str(metric_name),
                baseline_samples=baseline_vals,
                treatment_samples=treatment_vals,
                treatment_variant=tv,
                direction=direction,
                thresholds=thresholds,
            )
            if result:
                results.append(result)

    return results


def results_to_dataframe(results: list[ComparisonResult]) -> pd.DataFrame:
    """Convert list of ComparisonResult to a DataFrame."""
    return pd.DataFrame([asdict(r) for r in results])


def export_results(
    results: list[ComparisonResult],
    output_dir: Path | None = None,
    prefix: str = "comparison",
) -> Path:
    """Export comparison results to CSV and JSON."""
    out = output_dir or RESULTS_DIR / "analysis"
    out.mkdir(parents=True, exist_ok=True)

    df = results_to_dataframe(results)
    csv_path = out / f"{prefix}.csv"
    df.to_csv(csv_path, index=False)
    logger.info("Exported %d results to %s", len(results), csv_path)

    json_path = out / f"{prefix}.json"
    records = [asdict(r) for r in results]
    with open(json_path, "w") as f:
        json.dump(records, f, indent=2, default=str)

    return csv_path

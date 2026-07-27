"""
Visualization — generate thesis-quality graphs for 2-Axis evaluation.

Produces:
  - Per-metric bar charts (variant comparison)
  - Effect-size heatmap (scenarios × metrics)
  - 2-Axis quadrant chart (design-time Δ vs runtime Δ)
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger("evaluation.visualize")

GRAPHS_DIR = Path(__file__).resolve().parent.parent / "results" / "analysis" / "graphs"

# Thesis-quality style
plt.rcParams.update(
    {
        "figure.figsize": (10, 6),
        "figure.dpi": 150,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
    }
)

VARIANT_COLORS = {
    "baseline": "#9E9E9E",
    "design_only": "#2196F3",
    "runtime_only": "#FF9800",
    "full": "#4CAF50",
}

VARIANT_LABELS = {
    "baseline": "Baseline",
    "design_only": "Design-Time",
    "runtime_only": "Runtime",
    "full": "Full (Both)",
}


def bar_chart_metric(
    comparison_df: pd.DataFrame,
    scenario_id: str,
    metric_name: str,
    output_dir: Path | None = None,
) -> Path | None:
    """Bar chart comparing variant means for one scenario/metric."""
    out = output_dir or GRAPHS_DIR
    out.mkdir(parents=True, exist_ok=True)

    subset = comparison_df[
        (comparison_df["scenario_id"] == scenario_id)
        & (comparison_df["metric_name"] == metric_name)
    ]
    if subset.empty:
        return None

    # Build bars: baseline + treatments
    variants = ["baseline"]
    means = [subset.iloc[0]["mean_baseline"]]
    stds = [subset.iloc[0]["std_baseline"]]
    for _, row in subset.iterrows():
        variants.append(row["treatment_variant"])
        means.append(row["mean_treatment"])
        stds.append(row["std_treatment"])

    colors = [VARIANT_COLORS.get(v, "#666") for v in variants]
    labels = [VARIANT_LABELS.get(v, v) for v in variants]

    fig, ax = plt.subplots()
    x = np.arange(len(variants))
    bars = ax.bar(
        x, means, yerr=stds, capsize=5, color=colors, edgecolor="black", linewidth=0.5
    )

    # Significance stars
    for i, (_, row) in enumerate(subset.iterrows()):
        idx = i + 1  # treatment bars start at index 1
        if row["significant"] and row["practical"]:
            ax.text(
                idx,
                means[idx] + stds[idx] + 0.02 * max(means),
                "**",
                ha="center",
                va="bottom",
                fontsize=14,
                fontweight="bold",
            )
        elif row["significant"]:
            ax.text(
                idx,
                means[idx] + stds[idx] + 0.02 * max(means),
                "*",
                ha="center",
                va="bottom",
                fontsize=14,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel(metric_name)
    ax.set_title(f"{scenario_id.upper()} — {metric_name}")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    path = out / f"{scenario_id}_{metric_name.lower()}_bars.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("Saved bar chart: %s", path)
    return path


def effect_size_heatmap(
    comparison_df: pd.DataFrame,
    output_dir: Path | None = None,
) -> Path | None:
    """Heatmap of Cohen's d across scenarios × metrics for 'full' variant."""
    out = output_dir or GRAPHS_DIR
    out.mkdir(parents=True, exist_ok=True)

    full = comparison_df[comparison_df["treatment_variant"] == "full"]
    if full.empty:
        return None

    pivot = full.pivot_table(
        index="scenario_id", columns="metric_name", values="cohens_d"
    )
    if pivot.empty:
        return None

    fig, ax = plt.subplots(
        figsize=(max(8, len(pivot.columns) * 1.3), max(4, len(pivot) * 0.8))
    )
    cmap = plt.cm.RdYlGn  # Red = negative, Green = positive
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto", vmin=-2, vmax=2)

    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(
                    j,
                    i,
                    f"{val:.2f}",
                    ha="center",
                    va="center",
                    color="white" if abs(val) > 1 else "black",
                    fontsize=10,
                )

    fig.colorbar(im, ax=ax, label="Cohen's d")
    ax.set_title("Effect Size Heatmap (Full Variant vs Baseline)")

    path = out / "effect_size_heatmap.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("Saved heatmap: %s", path)
    return path


def two_axis_quadrant(
    comparison_df: pd.DataFrame,
    output_dir: Path | None = None,
) -> Path | None:
    """2-Axis quadrant chart: X = design-time delta %, Y = runtime delta %.

    Each point = one scenario/metric combination.
    """
    out = output_dir or GRAPHS_DIR
    out.mkdir(parents=True, exist_ok=True)

    design = comparison_df[comparison_df["treatment_variant"] == "design_only"][
        ["scenario_id", "metric_name", "delta_pct", "direction"]
    ].rename(columns={"delta_pct": "design_delta_pct"})

    runtime = comparison_df[comparison_df["treatment_variant"] == "runtime_only"][
        ["scenario_id", "metric_name", "delta_pct"]
    ].rename(columns={"delta_pct": "runtime_delta_pct"})

    merged = design.merge(runtime, on=["scenario_id", "metric_name"])
    if merged.empty:
        return None

    # Normalize direction: positive = improvement
    for _, row in merged.iterrows():
        if row["direction"] == "lower_is_better":
            merged.loc[merged.index == row.name, "design_delta_pct"] *= -1
            merged.loc[merged.index == row.name, "runtime_delta_pct"] *= -1

    fig, ax = plt.subplots(figsize=(8, 8))

    # Quadrant shading
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax.axvline(0, color="gray", linewidth=0.5, linestyle="--")

    ax.scatter(
        merged["design_delta_pct"],
        merged["runtime_delta_pct"],
        c="#4CAF50",
        s=100,
        edgecolors="black",
        zorder=3,
    )

    for _, row in merged.iterrows():
        ax.annotate(
            f"{row['scenario_id']}/{row['metric_name']}",
            (row["design_delta_pct"], row["runtime_delta_pct"]),
            textcoords="offset points",
            xytext=(8, 4),
            fontsize=8,
        )

    ax.set_xlabel("Design-Time Improvement (%)")
    ax.set_ylabel("Runtime Improvement (%)")
    ax.set_title("2-Axis Evaluation: Design-Time vs Runtime Impact")

    # Quadrant labels
    ax.text(
        0.95,
        0.95,
        "Both improve",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color="green",
        alpha=0.7,
    )
    ax.text(
        0.05,
        0.05,
        "Both degrade",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        color="red",
        alpha=0.7,
    )
    ax.text(
        0.95,
        0.05,
        "Design helps\nRuntime hurts",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        color="orange",
        alpha=0.7,
    )
    ax.text(
        0.05,
        0.95,
        "Runtime helps\nDesign hurts",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="orange",
        alpha=0.7,
    )

    path = out / "two_axis_quadrant.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    logger.info("Saved quadrant chart: %s", path)
    return path


def generate_all_charts(
    comparison_df: pd.DataFrame,
    output_dir: Path | None = None,
) -> list[Path]:
    """Generate all evaluation charts from comparison results."""
    paths: list[Path] = []
    out = output_dir or GRAPHS_DIR

    # Per-metric bar charts
    for (sid, mn), _grp in comparison_df.groupby(["scenario_id", "metric_name"]):
        p = bar_chart_metric(comparison_df, str(sid), str(mn), output_dir=out)
        if p:
            paths.append(p)

    # Effect size heatmap
    p = effect_size_heatmap(comparison_df, output_dir=out)
    if p:
        paths.append(p)

    # 2-Axis quadrant
    p = two_axis_quadrant(comparison_df, output_dir=out)
    if p:
        paths.append(p)

    logger.info("Generated %d charts total", len(paths))
    return paths

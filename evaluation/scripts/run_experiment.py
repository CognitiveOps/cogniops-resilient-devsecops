"""
Run Experiment — orchestrator for the 2-Axis evaluation.

Usage:
    python -m evaluation.scripts.run_experiment --scenarios s1 s3
  python -m evaluation.scripts.run_experiment --all
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from evaluation.scripts.collector import collect_all_metrics
from evaluation.scripts.compare_variants import (
    compare_all_variants,
    export_results,
    results_to_dataframe,
)
from evaluation.scripts.visualize import generate_all_charts

logger = logging.getLogger("evaluation.run_experiment")

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def run(
    scenarios: list[str] | None = None,
    project: str | None = None,
    start_ts: str = "2020-01-01",
    end_ts: str = "2099-12-31",
    output_dir: Path | None = None,
    skip_charts: bool = False,
    causal_mode: bool = False,
) -> dict:
    """Execute full evaluation pipeline.

    1. Collect metrics from BQ
    2. Run statistical comparisons
    3. Generate charts
    4. Export results
    """
    out = output_dir or RESULTS_DIR
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Step 1: Collect
    logger.info("Collecting metrics from BigQuery...")
    metrics_df = collect_all_metrics(
        scenarios=scenarios,
        project=project,
        start_ts=start_ts,
        end_ts=end_ts,
        causal_mode=causal_mode,
    )
    if metrics_df.empty:
        logger.error("No metrics collected — aborting.")
        return {"status": "error", "reason": "no_data"}

    raw_csv = raw_dir / f"metrics_{timestamp}.csv"
    metrics_df.to_csv(raw_csv, index=False)
    logger.info("Saved raw metrics (%d rows) to %s", len(metrics_df), raw_csv)

    # Step 2: Compare
    logger.info("Running statistical comparisons...")
    results = compare_all_variants(metrics_df)
    if not results:
        logger.warning(
            "No comparison results — insufficient data or variants."
        )
        return {
            "status": "warning",
            "reason": "no_comparisons",
            "raw_csv": str(raw_csv),
        }

    csv_path = export_results(
        results, output_dir=out / "analysis", prefix=f"comparison_{timestamp}"
    )
    comparison_df = results_to_dataframe(results)

    # Step 3: Charts
    chart_paths: list[Path] = []
    if not skip_charts:
        logger.info("Generating charts...")
        chart_paths = generate_all_charts(
            comparison_df, output_dir=out / "analysis" / "graphs"
        )

    # Step 4: Summary
    summary = _build_summary(comparison_df, timestamp, causal_mode=causal_mode)
    summary_path = out / "analysis" / f"summary_{timestamp}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info("Evaluation complete. Summary: %s", summary_path)
    return {
        "status": "success",
        "timestamp": timestamp,
        "n_metrics": len(metrics_df),
        "n_comparisons": len(results),
        "n_charts": len(chart_paths),
        "causal_mode": causal_mode,
        "raw_csv": str(raw_csv),
        "comparison_csv": str(csv_path),
        "summary_json": str(summary_path),
    }


def _build_summary(
    comparison_df: pd.DataFrame,
    timestamp: str,
    causal_mode: bool = False,
) -> dict:
    """Build structured summary of evaluation results."""
    summary: dict = {
        "timestamp": timestamp,
        "causal_mode": causal_mode,
        "n_comparisons": len(comparison_df),
        "significant_improvements": 0,
        "practical_improvements": 0,
        "both_significant_and_practical": 0,
        "by_variant": {},
        "by_scenario": {},
    }

    for variant in ["design_only", "runtime_only", "full"]:
        v_df = comparison_df[comparison_df["treatment_variant"] == variant]
        n_sig = int(v_df["significant"].sum())
        n_prac = int(v_df["practical"].sum())
        n_improved = int(v_df["improved"].sum())
        summary["by_variant"][variant] = {
            "total": len(v_df),
            "improved": n_improved,
            "significant": n_sig,
            "practical": n_prac,
            "mean_cohens_d": (
                float(v_df["cohens_d"].mean()) if len(v_df) > 0 else 0
            ),
        }

    for scenario_id, s_df in comparison_df.groupby("scenario_id"):
        summary["by_scenario"][str(scenario_id)] = {
            "total": len(s_df),
            "significant": int(s_df["significant"].sum()),
            "improved": int(s_df["improved"].sum()),
        }

    summary["significant_improvements"] = int(
        (comparison_df["significant"] & comparison_df["improved"]).sum()
    )
    summary["practical_improvements"] = int(
        (comparison_df["practical"] & comparison_df["improved"]).sum()
    )
    summary["both_significant_and_practical"] = int(
        (
            comparison_df["significant"]
            & comparison_df["practical"]
            & comparison_df["improved"]
        ).sum()
    )

    return summary


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="CogniOps 2-Axis Evaluation")
    parser.add_argument(
        "--scenarios", nargs="+", help="Scenario IDs to evaluate"
    )
    parser.add_argument("--project", help="GCP project ID")
    parser.add_argument(
        "--start", default="2020-01-01", help="Start timestamp (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", default="2099-12-31", help="End timestamp (YYYY-MM-DD)"
    )
    parser.add_argument("--output", type=Path, help="Output directory")
    parser.add_argument(
        "--skip-charts", action="store_true", help="Skip chart generation"
    )
    parser.add_argument(
        "--causal-mode",
        action="store_true",
        help=(
            "Filter samples to baseline-treatment overlap windows "
            "before comparison"
        ),
    )
    parser.add_argument(
        "--all", action="store_true", help="Evaluate all scenarios"
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    scenarios = None if args.all else args.scenarios
    result = run(
        scenarios=scenarios,
        project=args.project,
        start_ts=args.start,
        end_ts=args.end,
        output_dir=args.output,
        skip_charts=args.skip_charts,
        causal_mode=args.causal_mode,
    )
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("status") != "error" else 1)


if __name__ == "__main__":
    main()

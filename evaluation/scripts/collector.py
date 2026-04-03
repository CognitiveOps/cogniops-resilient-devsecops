"""
Metric Collector — query BigQuery for per-variant metric samples.

Deterministic: queries BQ, returns structured DataFrames.
All queries are parameterized (no hardcoded project IDs).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger("evaluation.collector")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "agent_metrics")
QUERIES_DIR = Path(__file__).resolve().parent.parent / "queries"

# ── Scenario × metric → BQ extraction config ────────────────────────

# Maps (scenario_id, metric_name) → how to extract per-sample values.
METRIC_EXTRACTION: dict[tuple[str, str], dict[str, Any]] = {
    # S1 — uses s1_final (96 rows) instead of s1_health (5 rows)
    ("s1", "TTD"): {
        "stage": "s1_final",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    ("s1", "CFR"): {
        "stage": "s1_final",
        "aggregation": "failure_rate",
    },
    ("s1", "DF"): {
        "stage": "s1_final",
        "aggregation": "frequency_per_day",
    },
    # S2
    ("s2", "TDL"): {
        "stage": "s2_activate",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.tdl_sec') AS FLOAT64)",
        "status_filter": "success",
    },
    ("s2", "DSR"): {
        "stage": "s2_activate",
        "aggregation": "success_rate",
    },
    ("s2", "TTD_edge"): {
        "stage": "s2_ttd_edge",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    # S3 Cloud (Cloud Run substrate — 218 rows)
    ("s3_cloud", "MTTD"): {
        "stage": "s3_detect",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    ("s3_cloud", "MTTR"): {
        "stage": "s3_recover",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    # S3 Edge (Edge OTA substrate — 18 rows)
    ("s3_edge", "MTTD"): {
        "stage": "s3_detect_edge",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    ("s3_edge", "MTTR"): {
        "stage": "s3_recover_edge",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    # S4
    ("s4", "TTV"): {
        "stage": "s4_p0_valid",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.ttv_ms') AS FLOAT64)",
        "status_filter": "success",
    },
    ("s4", "VSR"): {
        "stage": "s4_p0_valid",
        "aggregation": "success_rate",
    },
    ("s4", "FDR"): {
        "stages": ["s4_p1_tamper", "s4_p2_wrong_key", "s4_p3_replay"],
        "stage": "s4_p1_tamper",
        "aggregation": "rejection_rate",
    },
    # S5
    ("s5", "AL"): {
        "stage": "s5_final",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64)",
        "status_filter": "success",
    },
    ("s5", "ACR"): {
        "stage": "s5_final",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)",
        "status_filter": "success",
    },
    # SS1
    ("ss1", "CFR"): {
        "stage": "ss1_health",
        "aggregation": "failure_rate",
    },
    ("ss1", "FDR"): {
        "stage": "ss1_policy",
        "aggregation": "detection_rate",
    },
    # SS2
    ("ss2", "MTTD"): {
        "stage": "ss2_detect",
        "value_expr": "duration_sec",
        "status_filter": "success",
    },
    ("ss2", "AL"): {
        "stage": "s5_final",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64)",
        "status_filter": "success",
        "extra_where": (
            "AND CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64) "
            "BETWEEN 5 AND 50"
        ),
    },
    ("ss2", "ACR"): {
        "stage": "s5_final",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)",
        "status_filter": "success",
    },
}


# Maps logical scenario_id used in experiment_matrix → actual BQ scenario_id.
# s3_cloud and s3_edge share scenario_id='s3' in BQ.
# Stage suffix distinguishes them.
_BQ_SCENARIO_ID: dict[str, str] = {
    "s3_cloud": "s3",
    "s3_edge": "s3",
}


def _build_sample_query(
    scenario_id: str,
    metric_name: str,
    project: str,
    start_ts: str,
    end_ts: str,
) -> str | None:
    """Build a BQ SQL query to extract per-sample metric values by variant."""
    key = (scenario_id, metric_name)
    config = METRIC_EXTRACTION.get(key)
    if not config:
        logger.warning(
            "No extraction config for %s/%s", scenario_id, metric_name
        )
        return None

    bq_scenario_id = _BQ_SCENARIO_ID.get(scenario_id, scenario_id)
    stage = config["stage"]

    if "aggregation" in config:
        # Rate metrics need the raw status column, not per-sample values.
        # Multi-stage aggregations (e.g. S4/FDR) use IN(...) clause.
        stages = config.get("stages", [stage])
        if len(stages) == 1:
            stage_clause = f"stage = '{stages[0]}'"
        else:
            quoted = ", ".join(f"'{s}'" for s in stages)
            stage_clause = f"stage IN ({quoted})"
        return f"""
SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  run_id,
  status,
    t_end,
    JSON_VALUE(labels, '$.experiment_id') AS experiment_id,
    JSON_VALUE(labels, '$.pair_id') AS pair_id,
    JSON_VALUE(labels, '$.pair_order') AS pair_order
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = '{bq_scenario_id}'
  AND {stage_clause}
  AND t_end BETWEEN TIMESTAMP('{start_ts}') AND TIMESTAMP('{end_ts}')
ORDER BY variant, t_end
"""

    value_expr = config.get("value_expr", "duration_sec")
    status_filter = config.get("status_filter", "success")
    extra_where = config.get("extra_where", "")
    return f"""
SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  run_id,
  {value_expr} AS metric_value,
    t_end,
    JSON_VALUE(labels, '$.experiment_id') AS experiment_id,
    JSON_VALUE(labels, '$.pair_id') AS pair_id,
    JSON_VALUE(labels, '$.pair_order') AS pair_order
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = '{bq_scenario_id}'
  AND stage = '{stage}'
  AND status = '{status_filter}'
  AND t_end BETWEEN TIMESTAMP('{start_ts}') AND TIMESTAMP('{end_ts}')
  AND {value_expr} IS NOT NULL
  {extra_where}
ORDER BY variant, t_end
"""


def query_metric_samples(
    scenario_id: str,
    metric_name: str,
    project: str | None = None,
    start_ts: str = "2020-01-01",
    end_ts: str = "2099-12-31",
) -> pd.DataFrame:
    """Query BQ for per-sample metric values, grouped by variant.

    Returns a DataFrame with columns:
    variant, metric_value (or status for rates), t_end.
    """
    proj = project or GCP_PROJECT_ID
    if not proj:
        logger.error("GCP_PROJECT_ID not set")
        return pd.DataFrame()

    query = _build_sample_query(
        scenario_id, metric_name, proj, start_ts, end_ts
    )
    if not query:
        return pd.DataFrame()

    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=proj)
        df = client.query(query).to_dataframe()
        logger.info(
            "Fetched %d rows for %s/%s", len(df), scenario_id, metric_name
        )
        return df
    except Exception:  # pragma: no cover - network/credentials failures
        logger.warning(
            "BQ query failed for %s/%s", scenario_id, metric_name, exc_info=True
        )
        return pd.DataFrame()


def compute_rate_metric(df: pd.DataFrame, aggregation: str) -> pd.DataFrame:
    """Compute rate-based metrics as per-run binary values.

    Each run produces a 0/1 metric_value so we have enough samples
    for non-parametric statistical tests (Mann-Whitney U).

    Supported aggregations:
      - failure_rate:    1 if run failed, 0 if success  (S1/CFR, SS1/CFR)
      - success_rate:    1 if run succeeded, 0 otherwise  (S2/DSR, S4/VSR)
      - frequency_per_day: successful runs per calendar day (S1/DF)
      - rejection_rate:  1 if correctly rejected, 0 otherwise  (S4/FDR)
      - detection_rate:  1 if correctly detected, 0 otherwise  (SS1/FDR)

    Returns DataFrame with: variant, metric_value (per-run 0/1 or rate), t_end.
    """
    if df.empty:
        return pd.DataFrame(columns=["variant", "metric_value", "t_end"])

    if aggregation == "failure_rate":
        result = df[["variant"]].copy()
        result["metric_value"] = (df["status"] == "failure").astype(float)
        result["t_end"] = df["t_end"]
    elif aggregation == "success_rate":
        result = df[["variant"]].copy()
        result["metric_value"] = (df["status"] == "success").astype(float)
        result["t_end"] = df["t_end"]
    elif aggregation == "frequency_per_day":
        # Group by variant and day, count successful runs per day
        success_df = df[df["status"] == "success"].copy()
        if success_df.empty:
            return pd.DataFrame(columns=["variant", "metric_value"])
        success_df["day"] = pd.to_datetime(success_df["t_end"]).dt.date
        daily = (
            success_df.groupby(["variant", "day"])
            .size()
            .reset_index(name="metric_value")
        )
        daily["metric_value"] = daily["metric_value"].astype(float)
        daily["t_end"] = pd.to_datetime(daily["day"])
        result = daily[["variant", "metric_value", "t_end"]]
    elif aggregation == "rejection_rate":
        result = df[["variant"]].copy()
        result["metric_value"] = (df["status"] == "success").astype(float)
        result["t_end"] = df["t_end"]
    elif aggregation == "detection_rate":
        result = df[["variant"]].copy()
        result["metric_value"] = (df["status"] == "deny").astype(float)
        result["t_end"] = df["t_end"]
    else:
        return pd.DataFrame(columns=["variant", "metric_value", "t_end"])

    return result[["variant", "metric_value", "t_end"]].reset_index(drop=True)


def _filter_to_overlap_windows(
    df: pd.DataFrame,
    treatment_variants: tuple[str, ...] = (
        "design_only",
        "runtime_only",
        "full",
    ),
) -> pd.DataFrame:
    """Keep only rows that fall in baseline-vs-treatment overlap windows.

    For each treatment variant, we compute the timestamp overlap window
    against baseline:
      [max(min_baseline, min_treatment), min(max_baseline, max_treatment)]
    and retain baseline+treatment rows inside that window.
    """
    if df.empty or "variant" not in df.columns or "t_end" not in df.columns:
        return df

    work = df.copy()
    work["t_end"] = pd.to_datetime(work["t_end"], utc=True, errors="coerce")
    work = work.dropna(subset=["t_end"])
    if work.empty:
        return work

    baseline = work[work["variant"] == "baseline"]
    if baseline.empty:
        return pd.DataFrame(columns=work.columns)

    selected_frames: list[pd.DataFrame] = []
    for tv in treatment_variants:
        treat = work[work["variant"] == tv]
        if treat.empty:
            continue

        overlap_start = max(baseline["t_end"].min(), treat["t_end"].min())
        overlap_end = min(baseline["t_end"].max(), treat["t_end"].max())
        if overlap_start > overlap_end:
            continue

        b_sel = baseline[
            (baseline["t_end"] >= overlap_start)
            & (baseline["t_end"] <= overlap_end)
        ]
        t_sel = treat[
            (treat["t_end"] >= overlap_start)
            & (treat["t_end"] <= overlap_end)
        ]
        if b_sel.empty or t_sel.empty:
            continue

        selected_frames.extend([b_sel, t_sel])

    if not selected_frames:
        return pd.DataFrame(columns=work.columns)

    return pd.concat(selected_frames, ignore_index=True)


def collect_all_metrics(
    scenarios: list[str] | None = None,
    project: str | None = None,
    start_ts: str = "2020-01-01",
    end_ts: str = "2099-12-31",
    causal_mode: bool = False,
) -> pd.DataFrame:
    """Collect all metrics for all scenarios in long format.

    Columns: scenario_id, metric_name, variant, metric_value, t_end
    """
    from evaluation.configs import load_experiment_matrix

    matrix = load_experiment_matrix()
    target_scenarios = scenarios or list(matrix["scenarios"].keys())

    all_rows: list[dict] = []

    for scenario_id in target_scenarios:
        scenario_cfg = matrix["scenarios"].get(scenario_id, {})
        metrics = scenario_cfg.get("metrics", [])

        for metric_name in metrics:
            df = query_metric_samples(
                scenario_id,
                metric_name,
                project=project,
                start_ts=start_ts,
                end_ts=end_ts,
            )
            if df.empty:
                continue

            if causal_mode:
                df = _filter_to_overlap_windows(df)
                if df.empty:
                    logger.info(
                        "No overlap window samples for %s/%s (causal mode)",
                        scenario_id,
                        metric_name,
                    )
                    continue

            key = (scenario_id, metric_name)
            config = METRIC_EXTRACTION.get(key, {})

            if "aggregation" in config:
                result = compute_rate_metric(df, config["aggregation"])
                for _, row in result.iterrows():
                    all_rows.append(
                        {
                            "scenario_id": scenario_id,
                            "metric_name": metric_name,
                            "variant": row["variant"],
                            "metric_value": row["metric_value"],
                            "t_end": row.get("t_end"),
                        }
                    )
            else:
                for _, row in df.iterrows():
                    all_rows.append(
                        {
                            "scenario_id": scenario_id,
                            "metric_name": metric_name,
                            "variant": row["variant"],
                            "metric_value": row["metric_value"],
                            "t_end": row.get("t_end"),
                        }
                    )

    return pd.DataFrame(all_rows)

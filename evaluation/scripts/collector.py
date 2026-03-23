"""
Metric Collector — query BigQuery for per-variant metric samples.

Deterministic: queries BQ, returns structured DataFrames.
All queries are parameterized (no hardcoded project IDs).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
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
        "stage": "s5_approve",
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
    ("ss1", "ACR"): {
        "stage": "ss1_final",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)",
        "status_filter": "success",
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
    },
    ("ss2", "ACR"): {
        "stage": "s5_final",
        "value_expr": "CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)",
        "status_filter": "success",
    },
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
        logger.warning("No extraction config for %s/%s", scenario_id, metric_name)
        return None

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
  t_end
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = '{scenario_id}'
  AND {stage_clause}
  AND t_end BETWEEN TIMESTAMP('{start_ts}') AND TIMESTAMP('{end_ts}')
ORDER BY variant, t_end
"""

    value_expr = config.get("value_expr", "duration_sec")
    status_filter = config.get("status_filter", "success")
    return f"""
SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  run_id,
  {value_expr} AS metric_value,
  t_end
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = '{scenario_id}'
  AND stage = '{stage}'
  AND status = '{status_filter}'
  AND t_end BETWEEN TIMESTAMP('{start_ts}') AND TIMESTAMP('{end_ts}')
  AND {value_expr} IS NOT NULL
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

    Returns a DataFrame with columns: variant, metric_value (or status for rates).
    """
    proj = project or GCP_PROJECT_ID
    if not proj:
        logger.error("GCP_PROJECT_ID not set")
        return pd.DataFrame()

    query = _build_sample_query(scenario_id, metric_name, proj, start_ts, end_ts)
    if not query:
        return pd.DataFrame()

    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=proj)
        df = client.query(query).to_dataframe()
        logger.info("Fetched %d rows for %s/%s", len(df), scenario_id, metric_name)
        return df
    except Exception:
        logger.warning(
            "BQ query failed for %s/%s", scenario_id, metric_name, exc_info=True
        )
        return pd.DataFrame()


def compute_rate_metric(df: pd.DataFrame, aggregation: str) -> pd.DataFrame:
    """Compute rate-based metrics from raw status rows.

    Supported aggregations:
      - failure_rate:    failures / total  (S1/CFR, SS1/CFR)
      - success_rate:    successes / total (S2/DSR, S4/VSR)
      - frequency_per_day: successful runs per calendar day (S1/DF)
      - rejection_rate:  correct rejections / total  (S4/FDR — status=success
                         means the invalid input was correctly rejected)
      - detection_rate:  detections / total  (SS1/FDR — status=deny means
                         the policy correctly detected a violation)

    Returns DataFrame with: variant, metric_value (the rate).
    """
    if df.empty:
        return pd.DataFrame(columns=["variant", "metric_value"])

    if aggregation == "failure_rate":
        grouped = df.groupby("variant").agg(
            total=("status", "count"),
            failures=("status", lambda x: (x == "failure").sum()),
        )
        grouped["metric_value"] = grouped["failures"] / grouped["total"]
    elif aggregation == "success_rate":
        grouped = df.groupby("variant").agg(
            total=("status", "count"),
            successes=("status", lambda x: (x == "success").sum()),
        )
        grouped["metric_value"] = grouped["successes"] / grouped["total"]
    elif aggregation == "frequency_per_day":
        grouped = df.groupby("variant").agg(
            total=("status", lambda x: (x == "success").sum()),
            min_t=("t_end", "min"),
            max_t=("t_end", "max"),
        )
        days = (grouped["max_t"] - grouped["min_t"]).dt.total_seconds() / 86400
        grouped["metric_value"] = grouped["total"] / days.clip(lower=1)
    elif aggregation == "rejection_rate":
        # S4/FDR: invalid PQC scenarios (p1/p2/p3) — status=success means
        # the verifier correctly rejected the invalid input.
        grouped = df.groupby("variant").agg(
            total=("status", "count"),
            correct=("status", lambda x: (x == "success").sum()),
        )
        grouped["metric_value"] = grouped["correct"] / grouped["total"]
    elif aggregation == "detection_rate":
        # SS1/FDR: policy gate — status=deny means the policy correctly
        # detected a violation. FDR = deny / total.
        grouped = df.groupby("variant").agg(
            total=("status", "count"),
            detected=("status", lambda x: (x == "deny").sum()),
        )
        grouped["metric_value"] = grouped["detected"] / grouped["total"]
    else:
        return pd.DataFrame(columns=["variant", "metric_value"])

    return grouped[["metric_value"]].reset_index()


def collect_all_metrics(
    scenarios: list[str] | None = None,
    project: str | None = None,
    start_ts: str = "2020-01-01",
    end_ts: str = "2099-12-31",
) -> pd.DataFrame:
    """Collect all metrics for all scenarios, returning a long-format DataFrame.

    Columns: scenario_id, metric_name, variant, metric_value
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
                        }
                    )

    return pd.DataFrame(all_rows)

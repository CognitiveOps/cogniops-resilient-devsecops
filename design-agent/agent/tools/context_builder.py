"""
Context Builder — assembles structured analysis context from BQ + GCS.

Deterministic tool: queries BigQuery for metric trends and runtime decisions,
reads threshold config from GCS, and returns an AnalysisContext for the LLM.

All external calls are fail-safe: errors → empty/default values, never raises.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("design-agent.context_builder")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "agent_metrics")
CONFIG_BUCKET = os.getenv("CONFIG_BUCKET", "")
WINDOW_DAYS = int(os.getenv("CONTEXT_WINDOW_DAYS", "30"))

# ── Metric extraction queries ────────────────────────────────────────

# Maps scenario stages to their primary metric keys and units.
SCENARIO_METRIC_MAP: dict[str, list[dict[str, str]]] = {
    "s1": [
        {
            "stage": "s1_final",
            "metric_key": "ttd_sec",
            "name": "TTD",
            "unit": "seconds",
        },
    ],
    "s2": [
        {
            "stage": "s2_activate",
            "metric_key": "tdl_sec",
            "name": "TDL",
            "unit": "seconds",
        },
    ],
    "s3": [
        {
            "stage": "s3_detect_edge",
            "metric_key": "ttd_sample_sec",
            "name": "MTTD",
            "unit": "seconds",
        },
        {
            "stage": "s3_recover_edge",
            "metric_key": "ttr_sample_sec",
            "name": "MTTR",
            "unit": "seconds",
        },
    ],
    "s4": [
        {
            "stage": "s4_p0_valid",
            "metric_key": "ttv_ms",
            "name": "TTV",
            "unit": "milliseconds",
        },
    ],
    "ss2": [
        {
            "stage": "ss2_detect",
            "metric_key": "mttd_sample_sec",
            "name": "MTTD",
            "unit": "seconds",
        },
    ],
}

# SQL template for scenario metric aggregation.
_METRIC_QUERY = """
SELECT
  '{metric_name}' AS metric_name,
  '{scenario_id}' AS scenario_id,
  AVG(CAST(JSON_VALUE(metrics, '$.{metric_key}') AS FLOAT64)) AS mean_value,
  APPROX_QUANTILES(
    CAST(JSON_VALUE(metrics, '$.{metric_key}') AS FLOAT64), 100
  )[OFFSET(50)] AS p50_value,
  APPROX_QUANTILES(
    CAST(JSON_VALUE(metrics, '$.{metric_key}') AS FLOAT64), 100
  )[OFFSET(95)] AS p95_value,
  COUNT(*) AS sample_count
FROM `{project}.{dataset}.runs`
WHERE scenario_id = '{scenario_id}'
  AND stage = '{stage}'
  AND status = 'success'
  AND t_end >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {window_days} DAY)
  AND JSON_VALUE(metrics, '$.{metric_key}') IS NOT NULL
  {variant_clause}
"""

# SQL for runtime decisions summary.
_DECISIONS_QUERY = """
SELECT
  COUNT(*) AS total_decisions,
  COUNTIF(decision_executed = TRUE) AS executed_count,
  decision,
  COALESCE(JSON_VALUE(context, '$.scenario_id'), 'unknown') AS scenario_id
FROM `{project}.{dataset}.runtime_decisions`
WHERE processed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {window_days} DAY)
GROUP BY decision, scenario_id
"""

# SQL for trend analysis (compare last 2 weeks vs prior 2 weeks).
_TREND_QUERY = """
WITH recent AS (
  SELECT CAST(JSON_VALUE(metrics, '$.{metric_key}') AS FLOAT64) AS val
  FROM `{project}.{dataset}.runs`
  WHERE scenario_id = '{scenario_id}' AND stage = '{stage}'
    AND status = 'success'
    AND t_end >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
    AND JSON_VALUE(metrics, '$.{metric_key}') IS NOT NULL
    {variant_clause}
),
prior AS (
  SELECT CAST(JSON_VALUE(metrics, '$.{metric_key}') AS FLOAT64) AS val
  FROM `{project}.{dataset}.runs`
  WHERE scenario_id = '{scenario_id}' AND stage = '{stage}'
    AND status = 'success'
    AND t_end >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {window_days} DAY)
    AND t_end < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
    AND JSON_VALUE(metrics, '$.{metric_key}') IS NOT NULL
    {variant_clause}
)
SELECT
  (SELECT AVG(val) FROM recent) AS recent_avg,
  (SELECT AVG(val) FROM prior)  AS prior_avg
"""


def _classify_trend(recent_avg: float | None, prior_avg: float | None) -> str:
    """Classify metric trend: improving, degrading, or stable."""
    if recent_avg is None or prior_avg is None:
        return "stable"
    if prior_avg == 0:
        return "stable"
    pct_change = (recent_avg - prior_avg) / abs(prior_avg)
    if pct_change < -0.10:
        return "improving"  # lower is better for latency/time metrics
    if pct_change > 0.10:
        return "degrading"
    return "stable"


# ── BQ query execution ───────────────────────────────────────────────


def _query_bq(query: str) -> list[dict]:
    """Execute a BigQuery SQL query and return rows as dicts.

    Returns empty list on any failure (import error, BQ error, etc.).
    """
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=GCP_PROJECT_ID)
        result = client.query(query).result()
        return [dict(row) for row in result]
    except Exception:
        logger.warning("BQ query failed", exc_info=True)
        return []


# ── GCS config reader ────────────────────────────────────────────────


def _read_gcs_json(path: str) -> dict | None:
    """Read and parse JSON from GCS. Returns None on failure."""
    if not CONFIG_BUCKET:
        return None
    try:
        from google.cloud import storage

        client = storage.Client(project=GCP_PROJECT_ID)
        bucket = client.bucket(CONFIG_BUCKET)
        blob = bucket.blob(path)
        return json.loads(blob.download_as_text())
    except Exception:
        logger.warning("GCS read failed for %s", path, exc_info=True)
        return None


def _read_gcs_yaml(path: str) -> dict | None:
    """Read and parse YAML from GCS. Returns None on failure."""
    if not CONFIG_BUCKET:
        return None
    try:
        import yaml
        from google.cloud import storage

        client = storage.Client(project=GCP_PROJECT_ID)
        bucket = client.bucket(path.split("/")[0] if "/" in path else CONFIG_BUCKET)
        blob = bucket.blob(path)
        return yaml.safe_load(blob.download_as_text())
    except Exception:
        logger.warning("GCS YAML read failed for %s", path, exc_info=True)
        return None


# ── Public API (ADK tool function) ───────────────────────────────────


def build_context(
    window_days: int = 0,
    scenarios: list[str] | None = None,
    variant_filter: str | None = None,
) -> dict:
    """Build structured analysis context from BQ metrics and GCS config.

    Args:
        window_days: Override for the analysis lookback window (0 = use default).
        scenarios: Optional list of scenario IDs to focus on.
            If empty/None, all tracked scenarios are included.
        variant_filter: Optional variant label to filter runs.
            Use 'baseline' for original runs, 'design_only', 'runtime_only',
            'full' for treatment runs, or 'none' for runs without a variant label.
            If empty/None, all runs are included (no filter).

    Returns:
        Serialized AnalysisContext dict ready for LLM consumption.
    """
    window = window_days if window_days > 0 else WINDOW_DAYS
    target_scenarios = scenarios or list(SCENARIO_METRIC_MAP.keys())

    # Build variant SQL clause
    if variant_filter == "none":
        variant_clause = "AND JSON_VALUE(labels, '$.variant') IS NULL"
    elif variant_filter:
        variant_clause = f"AND JSON_VALUE(labels, '$.variant') = '{variant_filter}'"
    else:
        variant_clause = ""

    # ── 1. Scenario metrics ──
    metric_summaries: list[dict] = []
    for scenario_id in target_scenarios:
        metric_defs = SCENARIO_METRIC_MAP.get(scenario_id, [])
        for mdef in metric_defs:
            query = _METRIC_QUERY.format(
                metric_name=mdef["name"],
                scenario_id=scenario_id,
                stage=mdef["stage"],
                metric_key=mdef["metric_key"],
                project=GCP_PROJECT_ID,
                dataset=BIGQUERY_DATASET,
                window_days=window,
                variant_clause=variant_clause,
            )
            rows = _query_bq(query)
            if rows and rows[0].get("sample_count", 0) > 0:
                row = rows[0]
                # Get trend
                trend_query = _TREND_QUERY.format(
                    metric_key=mdef["metric_key"],
                    scenario_id=scenario_id,
                    stage=mdef["stage"],
                    project=GCP_PROJECT_ID,
                    dataset=BIGQUERY_DATASET,
                    window_days=window,
                    variant_clause=variant_clause,
                )
                trend_rows = _query_bq(trend_query)
                trend = "stable"
                if trend_rows:
                    trend = _classify_trend(
                        trend_rows[0].get("recent_avg"),
                        trend_rows[0].get("prior_avg"),
                    )
                metric_summaries.append(
                    {
                        "scenario_id": scenario_id,
                        "metric_name": mdef["name"],
                        "mean_value": row.get("mean_value", 0.0),
                        "p50_value": row.get("p50_value"),
                        "p95_value": row.get("p95_value"),
                        "sample_count": row.get("sample_count", 0),
                        "trend_direction": trend,
                        "unit": mdef["unit"],
                    }
                )

    # ── 2. Runtime decisions ──
    decisions_query = _DECISIONS_QUERY.format(
        project=GCP_PROJECT_ID,
        dataset=BIGQUERY_DATASET,
        window_days=window,
    )
    decision_rows = _query_bq(decisions_query)
    by_action: dict[str, int] = {}
    by_scenario: dict[str, int] = {}
    total = 0
    executed = 0
    for row in decision_rows:
        count = row.get("total_decisions", 0)
        total += count
        executed += row.get("executed_count", 0)
        action = row.get("decision", "UNKNOWN")
        by_action[action] = by_action.get(action, 0) + count
        scen = row.get("scenario_id", "unknown")
        by_scenario[scen] = by_scenario.get(scen, 0) + count

    runtime_summary = {
        "total_decisions": total,
        "by_action": by_action,
        "by_scenario": by_scenario,
        "execution_rate": (executed / total) if total > 0 else 0.0,
    }

    # ── 3. Current thresholds (from GCS) ──
    thresholds: dict[str, float] = {}
    thresh_data = _read_gcs_json("thresholds/v1.json")
    if thresh_data and isinstance(thresh_data, dict):
        for k, v in thresh_data.items():
            if isinstance(v, (int, float)):
                thresholds[k] = float(v)

    # ── 4. Assemble context ──
    context = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "window_days": window,
        "variant_filter": variant_filter,
        "scenario_metrics": metric_summaries,
        "runtime_decisions": runtime_summary,
        "current_thresholds": thresholds,
        "active_policies": [],
        "workflow_summaries": [],
    }

    return {"status": "context_ready", "context": context}

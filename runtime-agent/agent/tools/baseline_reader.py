"""
BigQuery baseline reader — queries rolling averages for anomaly detection.

DETERMINISTIC — no LLM. Graceful degradation: returns None on failure.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from agent.tools.anomaly_detection import BaselineStats

logger = logging.getLogger("runtime-agent.perception")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "agent_metrics")

# Metrics stored inside the JSON `metrics` column per scenario
_SCENARIO_METRIC_KEYS: dict[str, list[str]] = {
    "S1": ["ttd_sec"],
    "S2": ["tdl_sec", "dsr"],
    "S3": ["mttd_sec", "mttr_sec"],
    "S4": ["fdr"],
}

_BASELINE_QUERY = """
SELECT
    scenario_id,
    AVG(duration_sec)    AS avg_duration,
    STDDEV(duration_sec) AS stddev_duration,
    COUNT(*)             AS sample_count,
    {metric_aggs}
FROM `{project}.{dataset}.runs`
WHERE t_end > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND scenario_id = @scenario
  AND status = 'success'
GROUP BY scenario_id
"""


def _build_metric_aggs(scenario_id: str) -> str:
    """Build AVG/STDDEV SQL fragments for scenario-specific JSON metrics."""
    keys = _SCENARIO_METRIC_KEYS.get(scenario_id, [])
    if not keys:
        return "NULL AS _placeholder"
    parts: list[str] = []
    for key in keys:
        safe = key.replace("'", "")
        parts.append(
            f"AVG(SAFE_CAST(JSON_VALUE(metrics, '$.{safe}') AS FLOAT64)) AS avg_{safe}"
        )
        parts.append(
            f"STDDEV(SAFE_CAST(JSON_VALUE(metrics, '$.{safe}') AS FLOAT64)) AS stddev_{safe}"
        )
    return ",\n    ".join(parts)


def query_baseline(scenario_id: str) -> Optional[BaselineStats]:
    """Query BQ for 7-day rolling baselines for the given scenario.

    Returns None on any failure (network, auth, empty results).
    Caller must handle graceful degradation.
    """
    try:
        from google.cloud import bigquery  # lazy import — unavailable in tests

        client = bigquery.Client(project=GCP_PROJECT_ID)
        metric_aggs = _build_metric_aggs(scenario_id)
        query = _BASELINE_QUERY.format(
            project=GCP_PROJECT_ID,
            dataset=BIGQUERY_DATASET,
            metric_aggs=metric_aggs,
        )

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("scenario", "STRING", scenario_id),
            ]
        )

        rows = list(client.query(query, job_config=job_config).result())
        if not rows:
            logger.info("No baseline data for scenario %s", scenario_id)
            return None

        row = rows[0]
        metric_keys = _SCENARIO_METRIC_KEYS.get(scenario_id, [])

        metric_averages: dict[str, float] = {}
        metric_stddevs: dict[str, float] = {}
        for key in metric_keys:
            avg_val = getattr(row, f"avg_{key}", None) or row.get(f"avg_{key}")
            std_val = getattr(row, f"stddev_{key}", None) or row.get(f"stddev_{key}")
            if avg_val is not None:
                metric_averages[key] = float(avg_val)
            if std_val is not None:
                metric_stddevs[key] = float(std_val)

        return BaselineStats(
            scenario_id=scenario_id,
            avg_duration=float(row.avg_duration or 0),
            stddev_duration=float(row.stddev_duration or 0),
            sample_count=int(row.sample_count or 0),
            metric_averages=metric_averages,
            metric_stddevs=metric_stddevs,
        )

    except Exception as exc:
        logger.warning("Baseline query failed for %s: %s", scenario_id, exc)
        return None

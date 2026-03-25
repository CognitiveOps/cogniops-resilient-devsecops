"""ADK tool for querying recent agent decisions (episodic memory).

Step 3: Real BQ query with graceful degradation.
Returns empty results when BQ is unavailable (test environments, network errors).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("runtime-agent.memory")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "agent_metrics")

_RECENT_DECISIONS_QUERY = """
SELECT
    event_type,
    decision,
    rationale,
    mode,
    processed_at
FROM `{project}.{dataset}.runtime_decisions`
WHERE (@scenario = '' OR JSON_VALUE(context, '$.scenario_id') = @scenario)
ORDER BY processed_at DESC
LIMIT @limit
"""


def query_recent_decisions(scenario_id: str = "", limit: int = 5) -> dict:
    """Query recent agent decisions from BigQuery for context.

    Use this to check if similar events have been seen before and what
    actions were taken. Helps avoid repeated escalations and supports
    pattern-based reasoning.

    Args:
        scenario_id: Filter by scenario (S1-S5, SS1-SS2). Empty means all.
        limit: Maximum number of recent decisions to return (1-20).

    Returns:
        dict with list of recent decisions and count.
    """
    limit = max(1, min(limit, 20))

    if not GCP_PROJECT_ID:
        logger.debug("GCP_PROJECT_ID not set — returning empty decisions")
        return {"decisions": [], "count": 0, "note": "BQ not configured"}

    try:
        from google.cloud import bigquery  # lazy import — unavailable in tests

        client = bigquery.Client(project=GCP_PROJECT_ID)
        query = _RECENT_DECISIONS_QUERY.format(
            project=GCP_PROJECT_ID,
            dataset=BIGQUERY_DATASET,
        )

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("scenario", "STRING", scenario_id),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )

        rows = list(client.query(query, job_config=job_config).result())
        decisions = [
            {
                "event_type": row.event_type,
                "decision": row.decision,
                "rationale": row.rationale,
                "mode": row.mode,
                "processed_at": (
                    row.processed_at.isoformat() if row.processed_at else None
                ),
            }
            for row in rows
        ]

        return {"decisions": decisions, "count": len(decisions)}

    except Exception:
        logger.warning(
            "Failed to query recent decisions for %s — returning empty",
            scenario_id or "all",
            exc_info=True,
        )
        return {
            "decisions": [],
            "count": 0,
            "note": "BQ query failed — graceful degradation",
        }

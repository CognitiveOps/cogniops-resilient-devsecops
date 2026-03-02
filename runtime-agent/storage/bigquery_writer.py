"""
BigQuery writer – writes decision rows to agent_metrics.runtime_decisions.

Phase 0: writes one row per processed runtime event.
Schema mirrors infra/runtime.tf § BigQuery: runtime_decisions.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from models.schemas import DecisionRow

logger = logging.getLogger(__name__)

# ── Configuration from environment ───────────────────────────────────

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "agent_metrics")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "runtime_decisions")


def _get_table_id() -> str:
    """Fully-qualified BigQuery table ID."""
    return f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"


def write_decision(row: DecisionRow) -> bool:
    """
    Write a single decision row to BigQuery.

    Returns True on success, False on failure.
    Failures are logged but do NOT cause the endpoint to return non-200
    (the Pub/Sub message is already acknowledged; BQ write is best-effort
    in Phase 0 to avoid infinite retry loops).
    """
    try:
        from google.cloud import bigquery  # lazy import — not available in tests

        client = bigquery.Client(project=GCP_PROJECT_ID)
        table_id = _get_table_id()

        # Convert Pydantic model to a dict suitable for BQ insert
        row_dict = _to_bq_row(row)

        errors = client.insert_rows_json(table_id, [row_dict])

        if errors:
            logger.error("BigQuery insert errors: %s", errors)
            return False

        logger.info(
            "BigQuery: wrote decision row event_id=%s to %s",
            row.event_id,
            table_id,
        )
        return True

    except Exception as exc:
        logger.error("BigQuery write failed: %s", exc, exc_info=True)
        return False


def _to_bq_row(row: DecisionRow) -> dict:
    """
    Convert a DecisionRow Pydantic model to a dict matching the BQ JSON schema.

    - datetime → ISO 8601 string
    - policy_refs list → JSON string (BQ JSON column)
    - context dict → JSON string (BQ JSON column)
    """
    return {
        "event_id": row.event_id,
        "event_type": row.event_type,
        "occurred_at": row.occurred_at.isoformat(),
        "source": row.source,
        "context": json.dumps(row.context) if row.context else None,
        "decision": row.decision,
        "decision_executed": row.decision_executed,
        "rationale": row.rationale,
        "policy_refs": json.dumps(row.policy_refs) if row.policy_refs else None,
        "mode": row.mode,
        "agentops_trace_id": row.agentops_trace_id,
        "processed_at": row.processed_at.isoformat(),
    }


def build_decision_row(
    *,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    source: str,
    context: dict | None,
    decision: str,
    decision_executed: bool,
    rationale: str | None,
    policy_refs: list[str] | None,
    agentops_trace_id: str | None = None,
) -> DecisionRow:
    """
    Convenience factory that stamps processed_at and mode automatically.
    """
    return DecisionRow(
        event_id=event_id,
        event_type=event_type,
        occurred_at=occurred_at,
        source=source,
        context=context,
        decision=decision,
        decision_executed=decision_executed,
        rationale=rationale,
        policy_refs=policy_refs,
        mode="shadow",
        agentops_trace_id=agentops_trace_id,
        processed_at=datetime.now(timezone.utc),
    )

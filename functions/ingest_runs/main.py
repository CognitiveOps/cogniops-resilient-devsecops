import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from google.cloud import bigquery
from flask import Request, make_response


# These come from Terraform environment variables:
#   BQ_DATASET  = "agent_metrics"
#   BQ_TABLE    = "runs"
#   GCP_PROJECT = "<your-project-id>"
PROJECT_ID = (
    os.environ.get("GCP_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or os.environ.get("GCLOUD_PROJECT")
)

BQ_DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
BQ_TABLE = os.environ.get("BQ_TABLE", "runs")

bq_client = bigquery.Client()


def _epoch_to_datetime(value: Any) -> datetime:
    """
    Converts t_start / t_end fields into timezone-aware datetime objects.

    Accepts:
      - int / float (epoch seconds)
      - string representing epoch seconds
      - string ISO8601 format (e.g. 2025-11-09T10:12:00Z)
    """
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        # Try to parse as epoch seconds
        try:
            v = float(value)
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except ValueError:
            # Then try ISO8601
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception as e:
                raise ValueError(f"Invalid t_start/t_end string format: {value}") from e

    raise ValueError(f"Unsupported t_start/t_end type: {type(value)}")


def ingest_runs(request: Request):
    """
    HTTP Cloud Function (Gen2) for generic scenario metric ingestion.

    Expected JSON payload (from GitHub Actions):
    {
      "run_id": "19198654726-1",
      "scenario_id": "s2",
      "stage": "s2_activate",
      "mode": "baseline",
      "status": "success",
      "commit_sha": "b88ad87720bcbb7c6b470b1f4c4ce621d7312e25",
      "t_start": 1762636493,
      "t_end": 1762636510,
      "metrics": { "tdl_sec": 25 },
      "labels": { "service": "edge_cv_app", "edge_device": "gh-runner" }
    }
    """

    if request.method != "POST":
        return make_response(("Method not allowed", 405))

    # Basic project check (defensive)
    if not PROJECT_ID:
        return make_response(("GCP project ID is not set in environment", 500))

    try:
        payload = request.get_json(force=True, silent=False)
    except Exception as e:
        return make_response((f"Invalid JSON body: {e}", 400))

    if not isinstance(payload, dict):
        return make_response(("Expected JSON object", 400))

    # Required fields based on the BigQuery schema
    required_fields = [
        "run_id",
        "scenario_id",
        "stage",
        "status",
        "commit_sha",
        "t_start",
        "t_end",
    ]
    missing = [f for f in required_fields if f not in payload]
    if missing:
        return make_response((f"Missing required fields: {', '.join(missing)}", 400))

    run_id = str(payload["run_id"])
    scenario_id = str(payload["scenario_id"])
    stage = str(payload["stage"])
    status = str(payload["status"])
    commit_sha = str(payload["commit_sha"])
    mode = str(payload.get("mode", "")) or None

    # Convert timestamps
    try:
        t_start_dt = _epoch_to_datetime(payload["t_start"])
        t_end_dt = _epoch_to_datetime(payload["t_end"])
    except ValueError as e:
        return make_response((f"Invalid t_start/t_end: {e}", 400))

    # Compute duration if not provided
    duration_sec = payload.get("duration_sec")
    if duration_sec is None:
        duration_sec = (t_end_dt - t_start_dt).total_seconds()

    # Flexible JSON fields
    labels = payload.get("labels") or {}
    metrics = payload.get("metrics") or {}

    if not isinstance(labels, dict):
        return make_response(("labels must be a JSON object", 400))
    if not isinstance(metrics, dict):
        return make_response(("metrics must be a JSON object", 400))

    # BigQuery JSON type expects JSON-encoded string values.
    labels_json = json.dumps(labels) if labels else None
    metrics_json = json.dumps(metrics) if metrics else None

    # Construct BigQuery row
    row: Dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "stage": stage,
        "mode": mode,
        "status": status,
        "commit_sha": commit_sha,
        "t_start": t_start_dt.isoformat(),
        "t_end": t_end_dt.isoformat(),
        "duration_sec": float(duration_sec),
        "labels": labels_json,
        "metrics": metrics_json,
        "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    table_id = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"

    try:
        errors = bq_client.insert_rows_json(table_id, [row])
    except Exception as e:
        # Logged to Cloud Logging
        return make_response((f"BigQuery insert failed: {e}", 500))

    if errors:
        # Also logged as 500 to see the full structured errors
        return make_response((f"BigQuery insert errors: {errors}", 500))

    return make_response(("OK", 200))

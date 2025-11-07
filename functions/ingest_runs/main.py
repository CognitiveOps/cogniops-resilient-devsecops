import json
import os
from datetime import datetime, timezone

import functions_framework
from google.cloud import bigquery

# Configure BigQuery destination via env vars
BQ_DATASET = os.getenv("BQ_DATASET", "agent_metrics")
BQ_TABLE = os.getenv("BQ_TABLE", "runs")

_client = bigquery.Client()


def _parse_ts(value):
    """Accepts epoch seconds (int/str) or ISO8601 string and returns aware datetime."""
    if value is None:
        return None

    # Already datetime?
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # Epoch seconds (int / float / digit string)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        v = value.strip()
        # plain integer seconds
        if v.isdigit():
            return datetime.fromtimestamp(int(v), tz=timezone.utc)
        # ISO 8601 (e.g., 2025-11-07T20:01:05Z)
        try:
            # normalize trailing Z
            if v.endswith("Z"):
                v = v[:-1] + "+00:00"
            return datetime.fromisoformat(v)
        except Exception as e:
            raise ValueError(f"Cannot parse timestamp: {value!r} ({e})")

    raise ValueError(f"Unsupported timestamp type: {type(value)}")


@functions_framework.http
def ingest_runs(request):
    """HTTP endpoint to ingest generic scenario metrics into BigQuery.

    Expected JSON body:
    {
      "run_id": "12345-1",
      "scenario_id": "s2",
      "stage": "s2_activate",
      "mode": "baseline",
      "status": "success",
      "commit_sha": "abc123",
      "t_start": 1731009600,            # epoch seconds OR ISO8601 string
      "t_end":   1731009625,
      "duration_sec": 25.0,            # optional; computed if missing
      "labels":  { ... },              # optional
      "metrics": { "tdl_sec": 25.0 }   # required for useful data
    }
    """
    if request.method != "POST":
        return ("Only POST is allowed", 405)

    try:
        payload = request.get_json(force=True, silent=False)
    except Exception as e:
        return (f"Invalid JSON: {e}", 400)

    if not isinstance(payload, dict):
        return ("JSON body must be an object", 400)

    required_fields = [
        "run_id",
        "scenario_id",
        "stage",
        "mode",
        "status",
        "commit_sha",
        "t_start",
        "t_end",
        "metrics",
    ]
    missing = [f for f in required_fields if f not in payload]
    if missing:
        return (f"Missing required fields: {', '.join(missing)}", 400)

    try:
        t_start = _parse_ts(payload["t_start"])
        t_end = _parse_ts(payload["t_end"])
    except ValueError as e:
        return (f"Invalid timestamp: {e}", 400)

    if t_start is None or t_end is None:
        return ("t_start and t_end must be non-null", 400)

    duration_sec = payload.get("duration_sec")
    if duration_sec is None:
        duration_sec = (t_end - t_start).total_seconds()

    labels = payload.get("labels") or {}
    metrics = payload.get("metrics") or {}

    # Build BQ row
    row = {
        "run_id": str(payload["run_id"]),
        "scenario_id": str(payload["scenario_id"]),
        "stage": str(payload["stage"]),
        "mode": str(payload["mode"]),
        "status": str(payload["status"]),
        "commit_sha": str(payload["commit_sha"]),
        "t_start": t_start,
        "t_end": t_end,
        "duration_sec": float(duration_sec),
        "labels": labels,
        "metrics": metrics,
        # ingested_at handled by DEFAULT in table
    }

    table_id = f"{_client.project}.{BQ_DATASET}.{BQ_TABLE}"
    errors = _client.insert_rows_json(table_id, [row])
    if errors:
        # errors is a list of error dicts
        return (f"BigQuery insert errors: {errors}", 500)

    return ("OK", 200)

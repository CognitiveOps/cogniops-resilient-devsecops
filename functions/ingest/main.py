import json
import os
import datetime as dt

from google.cloud import bigquery
from werkzeug.exceptions import BadRequest
from google.api_core.exceptions import GoogleAPICallError, RetryError

# Environment variables for flexibility
DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
TABLE = os.environ.get("BQ_TABLE", "s1_pipeline_runs")
bq = bigquery.Client()

EXPECTED_FIELDS = [
    "run_id",
    "workflow",
    "scenario_id",
    "branch",
    "env",
    "service",
    "status",
    "failure_stage",
    "commit_sha",
    "image",
    "tests_total",
    "tests_failed",
    "commit_ts",
    "test_ts",
    "push_ts",
    "deploy_ts",
    "ended_ts",
    "ttd_sec",
]

def ingest(request):
    """
    HTTP POST → insert one row into BigQuery (full stage-level schema).
    Missing fields are filled with NULL.
    """

    if request.method != "POST":
        return ("Only POST allowed", 405)

    try:
        payload = request.get_json(force=True)
        if not payload:
            return (json.dumps({"ok": False, "error": "empty payload"}), 400)

        # Ensure required minimum fields
        if not payload.get("run_id") or not payload.get("commit_sha"):
            return (json.dumps({"ok": False, "error": "missing run_id or commit_sha"}), 400)

        # Normalize all fields
        row = {field: payload.get(field, None) for field in EXPECTED_FIELDS}

        # Add ingestion timestamp
        row["ingested_at"] = dt.datetime.utcnow().isoformat() + "Z"

        # Convert numeric fields if needed
        for k in ("tests_total", "tests_failed"):
            if row[k] in ("", None):
                row[k] = None
            else:
                try:
                    row[k] = int(row[k])
                except Exception:
                    row[k] = None
        if row["ttd_sec"] not in ("", None):
            try:
                row["ttd_sec"] = float(row["ttd_sec"])
            except Exception:
                row["ttd_sec"] = None

        # Insert into BigQuery
        table_id = f"{bq.project}.{DATASET}.{TABLE}"
        errors = bq.insert_rows_json(table_id, [row])

        if errors:
            return (json.dumps({"ok": False, "errors": errors}), 500)
        return (json.dumps({"ok": True, "inserted": 1}), 200)

    except (BadRequest, ValueError, TypeError) as e:
        return (json.dumps({"ok": False, "error": str(e)}), 400)
    except (GoogleAPICallError, RetryError) as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)
    except Exception as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)

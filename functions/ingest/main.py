import json
import os
import datetime as dt

from google.cloud import bigquery
from werkzeug.exceptions import BadRequest
from google.api_core.exceptions import GoogleAPICallError, RetryError

# --- Configuration ------------------------------------------------------------
DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
TABLE = os.environ.get("BQ_TABLE", "s1_pipeline_runs")
bq = bigquery.Client()


def ingest(request):
    """
    HTTP POST endpoint — receives a single pipeline run record and inserts it into BigQuery.
    """

    if request.method != "POST":
        return ("Only POST allowed", 405)

    try:
        payload = request.get_json(force=True)
        if not payload:
            return (json.dumps({"ok": False, "error": "empty payload"}), 400)

        # --- Required fields --------------------------------------------------
        required = [
            "run_id",
            "commit_sha",
            "started_at",
            "ended_at",
            "duration_sec",
            "status",
        ]
        missing = [k for k in required if k not in payload]
        if missing:
            return (
                json.dumps({"ok": False, "error": f"missing fields: {missing}"}),
                400,
            )

        # --- Normalize optional values ----------------------------------------
        inserted_at = dt.datetime.utcnow().isoformat() + "Z"

        row = [
            {
                "run_id": payload["run_id"],
                "workflow": payload.get("workflow"),
                "scenario_id": payload.get("scenario_id"),
                "branch": payload.get("branch"),
                "env": payload.get("env", "prod"),
                "service": payload.get("service", "baseline-app"),
                "status": payload["status"],
                "failure_stage": payload.get("failure_stage"),
                "commit_sha": payload["commit_sha"],
                "image": payload.get("image"),
                "tests_total": int(payload.get("tests_total", 1)),
                "tests_failed": int(payload.get("tests_failed", 0)),
                "started_at": payload["started_at"],
                "ended_at": payload["ended_at"],
                "duration_sec": float(payload.get("duration_sec", 0)),
                "inserted_at": inserted_at,
            }
        ]

        # --- Insert into BigQuery ---------------------------------------------
        table_id = f"{bq.project}.{DATASET}.{TABLE}"
        errors = bq.insert_rows_json(table_id, row)

        if errors:
            return (json.dumps({"ok": False, "errors": errors}), 500)

        return (
            json.dumps({
                "ok": True,
                "inserted": 1,
                "dataset": DATASET,
                "table": TABLE,
                "run_id": payload["run_id"],
                "status": payload["status"],
            }),
            200,
        )

    except (BadRequest, ValueError, TypeError) as e:
        # JSON parsing / validation errors
        return (json.dumps({"ok": False, "error": str(e)}), 400)
    except (GoogleAPICallError, RetryError) as e:
        # BigQuery API/network issues
        return (json.dumps({"ok": False, "error": str(e)}), 500)
    except Exception as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)

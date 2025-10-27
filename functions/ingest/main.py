import json
import os

from google.cloud import bigquery
from werkzeug.exceptions import BadRequest
from google.api_core.exceptions import GoogleAPICallError, RetryError

DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
TABLE = os.environ.get("BQ_TABLE", "s1_pipeline_runs")
bq = bigquery.Client()


def ingest(request):
    """
    Handle a POST HTTP request containing pipeline/run metadata and insert a single row into BigQuery.

    This function is intended to be used as a Cloud Function / Flask route handler. It validates
    the incoming JSON payload, maps fields to the expected BigQuery row schema, and inserts the row
    into the table identified by the module-level variables `bq`, `DATASET`, and `TABLE`.

    Behavior summary:
    - Only accepts HTTP POST requests. Any other method returns (message, 405).
    - Parses request body as JSON (force=True). An empty or invalid JSON payload returns (json_error, 400).
    - Requires the following top-level fields in the JSON payload:
        - run_id (str): unique identifier for the run
        - commit_sha (str): commit SHA associated with the run
        - started_at (str): ISO timestamp or string for start time
        - ended_at (str): ISO timestamp or string for end time
        - duration_sec (number): duration in seconds (will be converted to float)
        - status (str): run status (e.g., "success", "failure")
    - Optional fields (with defaults used if absent):
        - tests_total (int) -> defaults to 1
        - tests_failed (int) -> defaults to 0
        - service (str) -> defaults to "baseline-app"
        - env (str) -> defaults to "prod"

    BigQuery interaction:
    - Builds a single-row list of dicts and calls bq.insert_rows_json(table_id, row).
    - table_id is constructed as f"{bq.project}.{DATASET}.{TABLE}".
    - If BigQuery returns errors, the function returns (json_error_with_errors, 500).
    - On success returns (json_ok_with_inserted_count, 200).

    Return value:
    - A tuple (body, status_code):
        - body is a JSON-formatted string (via json.dumps) with keys "ok" and either
          "inserted" on success or "error"/"errors" on failure.
        - status_code is the HTTP status integer (200/400/405/500).

    Error handling:
    - Validation errors (missing fields, empty payload) return 400.
    - Non-POST methods return 405.
    - BigQuery insertion errors return 500 with the errors payload.
    - Unexpected exceptions are caught and returned as a 500 with the exception string.

    Example payload:
      "run_id": "abc123",
      "commit_sha": "deadbeef",
      "started_at": "2025-01-01T12:00:00Z",
      "ended_at": "2025-01-01T12:05:00Z",
      "duration_sec": 300,
      "status": "success",
      "tests_total": 10,         # optional
      "tests_failed": 0,         # optional
      "service": "my-service",   # optional
      "env": "staging"           # optional

    Notes:
    - The function returns JSON strings (not dicts). Callers expecting JSON responses should set
      appropriate Content-Type headers at the HTTP layer if required.
    - It relies on module-level variables `bq`, `DATASET`, and `TABLE` being defined and configured.
    """
    if request.method != "POST":
        return ("Only POST allowed", 405)
    try:
        payload = request.get_json(force=True)
        if not payload:
            return (json.dumps({"ok": False, "error": "empty payload"}), 400)
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
        row = [
            {
                "run_id": payload["run_id"],
                "commit_sha": payload["commit_sha"],
                "started_at": payload["started_at"],
                "ended_at": payload["ended_at"],
                "duration_sec": float(payload["duration_sec"]),
                "status": payload["status"],
                "tests_total": payload.get("tests_total", 1),
                "tests_failed": payload.get("tests_failed", 0),
                "service": payload.get("service", "baseline-app"),
                "env": payload.get("env", "prod"),
            }
        ]
        table_id = f"{bq.project}.{DATASET}.{TABLE}"
        errors = bq.insert_rows_json(table_id, row)
        if errors:
            return (json.dumps({"ok": False, "errors": errors}), 500)
        return (json.dumps({"ok": True, "inserted": 1}), 200)
    except (BadRequest, ValueError, TypeError) as e:
        # JSON parsing errors or invalid types -> bad request
        return (json.dumps({"ok": False, "error": str(e)}), 400)
    except (GoogleAPICallError, RetryError) as e:
        # BigQuery / API errors -> server error
        return (json.dumps({"ok": False, "error": str(e)}), 500)
    except Exception as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)

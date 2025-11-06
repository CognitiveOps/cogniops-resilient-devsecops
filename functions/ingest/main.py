import json
import os
import datetime as dt

from google.cloud import bigquery
from werkzeug.exceptions import BadRequest
from google.api_core.exceptions import GoogleAPICallError, RetryError

DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
TABLE = os.environ.get("BQ_TABLE", "s1_pipeline_runs")
bq = bigquery.Client()


def ingest(request):
    """
    HTTP POST endpoint that accepts a single S1 run record and inserts
    it into BigQuery. The schema matches the CSV written by
    s1_write_metrics.py.

    Expected JSON fields (all strings unless noted):

      run_id         (required)
      commit_sha     (required)
      workflow
      scenario_id
      branch
      env
      service
      status
      failure_stage
      image
      tests_total    (int, optional)
      tests_failed   (int, optional)
      commit_ts      (timestamp string, optional)
      test_ts        (timestamp string, optional)
      push_ts        (timestamp string, optional)
      deploy_ts      (timestamp string, optional)
      ended_ts       (timestamp string, optional)
      ttd_sec        (float, optional)

    BigQuery table schema (columns in order):

      run_id, workflow, scenario_id, branch, env, service,
      status, failure_stage, commit_sha, image,
      tests_total, tests_failed,
      commit_ts, test_ts, push_ts, deploy_ts, ended_ts,
      ttd_sec, inserted_at
    """
    if request.method != "POST":
        return ("Only POST allowed", 405)

    try:
        payload = request.get_json(force=True)
        if not payload:
            return (json.dumps({"ok": False, "error": "empty payload"}), 400)

        required = ["run_id", "commit_sha"]
        missing = [k for k in required if k not in payload or payload[k] in (None, "")]
        if missing:
            return (
                json.dumps({"ok": False, "error": f"missing fields: {missing}"}),
                400,
            )

        def cast_int(key):
            v = payload.get(key)
            if v is None or v == "":
                return None
            try:
                return int(v)
            except Exception:
                return None

        def cast_float(key):
            v = payload.get(key)
            if v is None or v == "":
                return None
            try:
                return float(v)
            except Exception:
                return None

        row = [{
            "run_id":        payload["run_id"],
            "workflow":      payload.get("workflow"),
            "scenario_id":   payload.get("scenario_id"),
            "branch":        payload.get("branch"),
            "env":           payload.get("env"),
            "service":       payload.get("service"),
            "status":        payload.get("status"),
            "failure_stage": payload.get("failure_stage"),
            "commit_sha":    payload["commit_sha"],
            "image":         payload.get("image"),
            "tests_total":   cast_int("tests_total"),
            "tests_failed":  cast_int("tests_failed"),
            "commit_ts":     payload.get("commit_ts"),
            "test_ts":       payload.get("test_ts"),
            "push_ts":       payload.get("push_ts"),
            "deploy_ts":     payload.get("deploy_ts"),
            "ended_ts":      payload.get("ended_ts"),
            "ttd_sec":       cast_float("ttd_sec"),
            "inserted_at":   dt.datetime.utcnow().isoformat() + "Z",
        }]

        table_id = f"{bq.project}.{DATASET}.{TABLE}"
        # Use run_id as insertId to avoid duplicates if we re-send the same run
        errors = bq.insert_rows_json(table_id, row, row_ids=[payload["run_id"]])
        if errors:
            return (json.dumps({"ok": False, "errors": errors}), 500)

        return (json.dumps({"ok": True, "inserted": 1}), 200)

    except (BadRequest, ValueError, TypeError) as e:
        return (json.dumps({"ok": False, "error": str(e)}), 400)
    except (GoogleAPICallError, RetryError) as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)
    except Exception as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)

import json
import os
import datetime as dt

from google.cloud import bigquery
from werkzeug.exceptions import BadRequest
from google.api_core.exceptions import GoogleAPICallError, RetryError

DATASET = os.environ.get("BQ_DATASET", "agent_metrics")
TABLE = os.environ.get("BQ_TABLE", "s1_pipeline_runs")
bq = bigquery.Client()


def _parse_ts(value):
    """Accept ISO string or epoch; return RFC3339 string or None."""
    if not value:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        float(s)
        return dt.datetime.utcfromtimestamp(float(s)).isoformat() + "Z"
    except Exception:
        return s + "Z" if not s.endswith("Z") else s


def ingest(request):
    if request.method != "POST":
        return ("Only POST allowed", 405)

    try:
        payload = request.get_json(force=True)
        if not payload:
            return (json.dumps({"ok": False, "error": "empty payload"}), 400)

        required = ["run_id", "commit_sha", "status"]
        missing = [k for k in required if k not in payload]
        if missing:
            return (json.dumps({"ok": False, "error": f"missing fields: {missing}"}), 400)

        # normalize timestamps
        commit_ts  = _parse_ts(payload.get("commit_ts"))
        test_ts    = _parse_ts(payload.get("test_ts"))
        push_ts    = _parse_ts(payload.get("push_ts"))
        deploy_ts  = _parse_ts(payload.get("deploy_ts"))
        healthy_ts = _parse_ts(payload.get("healthy_ts"))

        # derive ttd_sec
        ttd_sec = payload.get("ttd_sec")
        if not ttd_sec and commit_ts and healthy_ts:
            try:
                s = dt.datetime.fromisoformat(commit_ts.replace("Z", ""))
                e = dt.datetime.fromisoformat(healthy_ts.replace("Z", ""))
                ttd_sec = (e - s).total_seconds()
            except Exception:
                ttd_sec = None

        row = [{
            "run_id":        str(payload["run_id"]),
            "commit_sha":    str(payload["commit_sha"]),
            "workflow":      payload.get("workflow"),
            "scenario_id":   payload.get("scenario_id"),
            "branch":        payload.get("branch"),
            "env":           payload.get("env"),
            "service":       payload.get("service"),
            "commit_ts":     commit_ts,
            "test_ts":       test_ts,
            "push_ts":       push_ts,
            "deploy_ts":     deploy_ts,
            "healthy_ts":    healthy_ts,
            "status":        payload.get("status"),
            "failure_stage": payload.get("failure_stage"),
            "tests_total":   payload.get("tests_total"),
            "tests_failed":  payload.get("tests_failed"),
            "ttd_sec":       float(ttd_sec) if ttd_sec else None,
            "inserted_at":   dt.datetime.utcnow().isoformat() + "Z"
        }]

        table_id = f"{bq.project}.{DATASET}.{TABLE}"
        errors = bq.insert_rows_json(table_id, row)
        if errors:
            return (json.dumps({"ok": False, "errors": errors}), 500)
        return (json.dumps({"ok": True, "inserted": 1}), 200)

    except (BadRequest, ValueError, TypeError) as e:
        return (json.dumps({"ok": False, "error": str(e)}), 400)
    except (GoogleAPICallError, RetryError) as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)
    except Exception as e:
        return (json.dumps({"ok": False, "error": str(e)}), 500)

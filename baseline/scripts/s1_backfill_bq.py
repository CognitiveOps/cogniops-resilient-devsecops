#!/usr/bin/env python3
"""
s1_backfill_bq.py

One-time (or occasional) backfill script to push existing S1 CSV runs
into BigQuery via the ingest HTTP endpoint.

Expected CSV columns (canonical, aligned with BigQuery):

  run_id, workflow, scenario_id, branch, env, service,
  status, failure_stage, commit_sha, image,
  tests_total, tests_failed,
  commit_ts, test_ts, push_ts, deploy_ts, ended_ts, ttd_sec

We DO NOT send `ingested_at` from here — the ingest function / BigQuery
should set it on insert.

Usage (example):

  export METRICS_INGEST_URL="https://<your-fn-url>"
  export AUTH_TOKEN="$(gcloud auth print-identity-token \
      --audiences=${METRICS_INGEST_URL} \
      --format='value(token)')"

  python baseline/scripts/s1_backfill_bq.py \
    --csv baseline/metrics/s1_pipeline_runs.csv \
    --url "${METRICS_INGEST_URL}" \
    --auth-token "${AUTH_TOKEN}"
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Optional

import requests


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        required=True,
        help="Path to merged per-run CSV (e.g. baseline/metrics/s1_pipeline_runs.csv)",
    )
    ap.add_argument(
        "--url",
        required=True,
        help="Metrics ingest URL (Cloud Function / Cloud Run HTTPS endpoint).",
    )
    ap.add_argument(
        "--auth-token",
        default="",
        help="Optional bearer token for Authorization header.",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit of rows to send (0 = all).",
    )
    return ap.parse_args()


def cast_int(val: str, default: Optional[int] = None) -> Optional[int]:
    if val is None or val == "":
        return default
    try:
        return int(val)
    except Exception:
        return default


def cast_float(val: str, default: Optional[float] = None) -> Optional[float]:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except Exception:
        return default


def build_payload(row: Dict[str, str]) -> Dict:
    """
    Map CSV row -> JSON payload expected by ingest().

    CSV columns (canonical):

      run_id, workflow, scenario_id, branch, env, service,
      status, failure_stage, commit_sha, image,
      tests_total, tests_failed,
      commit_ts, test_ts, push_ts, deploy_ts, ended_ts, ttd_sec
    """
    return {
        "run_id":        row.get("run_id"),
        "workflow":      (row.get("workflow") or None),
        "scenario_id":   (row.get("scenario_id") or None),
        "branch":        (row.get("branch") or None),
        "env":           (row.get("env") or None),
        "service":       (row.get("service") or None),
        "status":        (row.get("status") or None),
        "failure_stage": (row.get("failure_stage") or None),
        "commit_sha":    row.get("commit_sha"),

        "image":         (row.get("image") or None),

        "tests_total":   cast_int(row.get("tests_total", ""), default=None),
        "tests_failed":  cast_int(row.get("tests_failed", ""), default=None),

        # timestamps – pass through as strings (ISO) or None
        "commit_ts":     (row.get("commit_ts") or None),
        "test_ts":       (row.get("test_ts") or None),
        "push_ts":       (row.get("push_ts") or None),
        "deploy_ts":     (row.get("deploy_ts") or None),
        "ended_ts":      (row.get("ended_ts") or None),

        # numeric duration – let BQ see NULL if missing
        "ttd_sec":       cast_float(row.get("ttd_sec", ""), default=None),

        # NOTE: ingested_at is intentionally NOT sent;
        # the ingest function / BQ should set it automatically.
    }


def post_row(url: str, token: str, payload: Dict) -> bool:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        if resp.status_code != 200:
            print(f"[backfill] run_id={payload.get('run_id')} -> HTTP {resp.status_code}: {resp.text}")
            return False
        print(f"[backfill] run_id={payload.get('run_id')} -> OK")
        return True
    except Exception as e:
        print(f"[backfill] run_id={payload.get('run_id')} -> ERROR: {e}")
        return False


def main():
    args = parse_args()
    csv_path = Path(args.csv)

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    if args.limit > 0:
        rows = rows[: args.limit]

    print(f"[backfill] Loaded {total} rows from {csv_path}, sending {len(rows)} rows to {args.url}")

    ok = 0
    fail = 0
    for row in rows:
        payload = build_payload(row)

        # simple guard: must have run_id + commit_sha
        if not payload.get("run_id") or not payload.get("commit_sha"):
            print(f"[backfill] SKIP row with missing run_id/commit_sha: {row}")
            fail += 1
            continue

        if post_row(args.url, args.auth_token, payload):
            ok += 1
        else:
            fail += 1

    print(f"[backfill] Done. Success: {ok}, Failed: {fail}")


if __name__ == "__main__":
    main()

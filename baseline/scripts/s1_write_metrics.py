#!/usr/bin/env python3
"""
s1_write_metrics.py

Single-row CSV ledger per GitHub Actions run + optional BigQuery ingest.

CSV columns (one row per run_id):

  run_id, workflow, scenario_id, branch, env, service,
  status, failure_stage, commit_sha, image,
  tests_total, tests_failed,
  commit_ts, test_ts, push_ts, deploy_ts, ended_ts, ttd_sec

Stages (argument --stage):
  - commit : pipeline started (commit_ts)
  - test   : unit tests finished (test_ts, tests_* updated)
  - push   : image pushed (push_ts)
  - deploy : Cloud Run deploy finished (deploy_ts)
  - final  : whole workflow finished (ended_ts, final status)

IMPORTANT:
- The CSV is updated *incrementally* per stage, but there is
  always **exactly one row per run_id** – later stages update fields.
- When called with --stage final and --post-to URL, the script
  will POST the final CSV row for this run to the ingest endpoint
  (Cloud Function) so BigQuery remains in sync with the CSV.
"""

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional

import requests  # make sure this is installed in the workflow


FIELDS = [
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


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfile", required=True)
    ap.add_argument("--run_id", required=True)
    ap.add_argument("--commit_sha", required=True)

    ap.add_argument(
        "--stage",
        required=True,
        choices=["commit", "test", "push", "deploy", "final"],
    )

    ap.add_argument("--status", default="")
    ap.add_argument("--workflow", default="")
    ap.add_argument("--scenario_id", default="")
    ap.add_argument("--branch", default="")
    ap.add_argument("--env", default="")
    ap.add_argument("--service", default="")
    ap.add_argument("--image", default="")

    # Optional overrides of timestamps from CI (epoch seconds or ISO8601)
    ap.add_argument("--commit_ts", default="")
    ap.add_argument("--ended_ts", default="")

    # Optional override for tests (usually we just set in the test stage)
    ap.add_argument("--tests_total", default="")
    ap.add_argument("--tests_failed", default="")

    # Optional BigQuery ingest (final stage only)
    ap.add_argument("--post-to", dest="post_to", default="")
    ap.add_argument("--auth-token", dest="auth_token", default="")

    return ap.parse_args()


def iso_from_epoch_or_iso(s: str) -> str:
    """Support either epoch seconds or ISO string; return ISO8601+Z or ''."""
    if not s:
        return ""
    s = s.strip()
    if not s:
        return ""
    if s.isdigit():
        return dt.datetime.utcfromtimestamp(int(s)).isoformat() + "Z"
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "")).isoformat() + "Z"
    except Exception:
        # If it's some RFC3339-like string, just trust downstream to parse it.
        return s


def now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


def load_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def ensure_row_defaults(row: Dict[str, str], args) -> Dict[str, str]:
    # Ensure all fields exist
    for f in FIELDS:
        row.setdefault(f, "")

    # Core identifiers
    row["run_id"] = args.run_id
    row["commit_sha"] = args.commit_sha

    # Context
    if args.workflow:
        row["workflow"] = args.workflow
    if args.scenario_id:
        row["scenario_id"] = args.scenario_id
    if args.branch:
        row["branch"] = args.branch
    if args.env:
        row["env"] = args.env
    if args.service:
        row["service"] = args.service
    if args.image:
        row["image"] = args.image

    # Default test stats: assume 1 check, 0 failed, until test stage says otherwise
    if not row["tests_total"]:
        row["tests_total"] = "1"
    if not row["tests_failed"]:
        row["tests_failed"] = "0"

    # CLI overrides for tests if provided
    if args.tests_total:
        row["tests_total"] = str(args.tests_total)
    if args.tests_failed:
        row["tests_failed"] = str(args.tests_failed)

    return row


def apply_stage_updates(row: Dict[str, str], args) -> Dict[str, str]:
    stage = args.stage
    status = (args.status or "").lower()

    # Stage-specific timestamps
    if stage == "commit":
        # Use CI-provided start if present, else "now"
        row["commit_ts"] = iso_from_epoch_or_iso(args.commit_ts) or now_iso()
        if not row["status"]:
            row["status"] = "running"

    elif stage == "test":
        row["test_ts"] = now_iso()
        # One logical test: pass/fail based on status
        row["tests_total"] = "1"
        if status and status != "success":
            row["tests_failed"] = "1"
        else:
            row["tests_failed"] = "0"

    elif stage == "push":
        row["push_ts"] = now_iso()

    elif stage == "deploy":
        row["deploy_ts"] = now_iso()

    elif stage == "final":
        # Overall job.status from GitHub Actions (success / failure / cancelled)
        if status:
            row["status"] = status
        row["ended_ts"] = iso_from_epoch_or_iso(args.ended_ts) or now_iso()

    # First failing stage wins
    if status and status != "success" and not row.get("failure_stage"):
        row["failure_stage"] = stage

    # Recompute TTD if we know both ends
    if row.get("commit_ts") and row.get("ended_ts"):
        try:
            start = dt.datetime.fromisoformat(row["commit_ts"].replace("Z", ""))
            end = dt.datetime.fromisoformat(row["ended_ts"].replace("Z", ""))
            ttd = (end - start).total_seconds()
            row["ttd_sec"] = str(ttd)
        except Exception:
            # If parsing fails, leave old ttd_sec as-is
            pass

    return row


def write_rows(path: Path, rows: List[Dict[str, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def build_bq_payload(row: Dict[str, str]) -> Dict:
    """Map CSV row -> JSON payload for the ingest Cloud Function."""
    def to_float(x: str) -> Optional[float]:
        if not x:
            return None
        try:
            return float(x)
        except Exception:
            return None

    def to_int(x: str) -> Optional[int]:
        if not x:
            return None
        try:
            return int(x)
        except Exception:
            return None

    return {
        "run_id": row.get("run_id"),
        "workflow": row.get("workflow") or None,
        "scenario_id": row.get("scenario_id") or None,
        "branch": row.get("branch") or None,
        "env": row.get("env") or None,
        "service": row.get("service") or None,
        "status": row.get("status") or None,
        "failure_stage": row.get("failure_stage") or None,
        "commit_sha": row.get("commit_sha"),
        "image": row.get("image") or None,
        "tests_total": to_int(row.get("tests_total", "")),
        "tests_failed": to_int(row.get("tests_failed", "")),
        "commit_ts": row.get("commit_ts") or None,
        "test_ts": row.get("test_ts") or None,
        "push_ts": row.get("push_ts") or None,
        "deploy_ts": row.get("deploy_ts") or None,
        "ended_ts": row.get("ended_ts") or None,
        "ttd_sec": to_float(row.get("ttd_sec", "")),
    }


def post_to_ingest(url: str, token: str, payload: Dict):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        if resp.status_code != 200:
            print(f"[s1_write_metrics] ingest failed: {resp.status_code} {resp.text}")
        else:
            print("[s1_write_metrics] ingest OK")
    except Exception as e:
        print(f"[s1_write_metrics] ingest error: {e}")


def main():
    args = parse_args()
    out = Path(args.outfile)
    rows = load_rows(out)

    # One row per run_id
    row = None
    for r in rows:
        if r.get("run_id") == args.run_id:
            row = r
            break
    if row is None:
        row = {}
        rows.append(row)

    row = ensure_row_defaults(row, args)
    row = apply_stage_updates(row, args)
    write_rows(out, rows)

    # For the final stage, optionally sync this row to BigQuery via Cloud Function
    if args.stage == "final" and args.post_to:
        # Re-read the canonical row (after write) to be sure we have the latest state
        final_rows = load_rows(out)
        final_row = next((r for r in final_rows if r.get("run_id") == args.run_id), row)
        payload = build_bq_payload(final_row)
        post_to_ingest(args.post_to, args.auth_token, payload)


if __name__ == "__main__":
    main()

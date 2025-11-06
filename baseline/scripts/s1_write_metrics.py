#!/usr/bin/env python3
"""
s1_write_metrics.py

Append/update a single CSV ledger row per GitHub Actions run.

Columns (header):
  run_id, workflow, scenario_id, branch, env, service,
  status, failure_stage, commit_sha,
  tests_total, tests_failed,
  commit_ts, test_ts, push_ts, deploy_ts, ended_ts, ttd_sec

Usage from GitHub Actions (examples):

  # commit stage – use t0 as canonical start timestamp
  python baseline/scripts/s1_write_metrics.py \
    --outfile baseline/metrics/s1_pipeline_runs.csv \
    --run_id "${{ github.run_id }}" \
    --commit_sha "${{ github.sha }}" \
    --stage commit \
    --workflow "s1_ci" \
    --scenario_id "${{ env.SCENARIO_ID }}" \
    --branch "${{ env.BRANCH }}" \
    --env "${{ env.RUN_ENV }}" \
    --service "${{ env.SERVICE }}" \
    --commit_ts "${{ steps.t0.outputs.ts }}"

  # test stage
  python ... --stage test --status "$STATUS" ...

  # push stage
  python ... --stage push ...

  # deploy stage
  python ... --stage deploy ...

  # health stage – use t1 as canonical end timestamp and job.status
  python ... --stage health --status "${{ job.status }}" \
               --ended_ts "${{ steps.t1.outputs.ts }}"
"""

import argparse
import csv
import datetime as dt
from pathlib import Path
from typing import Dict, List

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
        choices=["commit", "test", "push", "deploy", "health"],
    )
    ap.add_argument("--status", default="")
    ap.add_argument("--workflow", default="")
    ap.add_argument("--scenario_id", default="")
    ap.add_argument("--branch", default="")
    ap.add_argument("--env", default="")
    ap.add_argument("--service", default="")

    # Optionally override timestamps from CI (epoch seconds or ISO8601)
    ap.add_argument("--commit_ts", default="")
    ap.add_argument("--ended_ts", default="")
    return ap.parse_args()


def iso_from_epoch_or_iso(s: str) -> str:
    """Support either epoch seconds or ISO string; return ISO8601+Z or ''."""
    if not s:
        return ""
    s = s.strip()
    if not s:
        return ""
    # pure integer -> epoch seconds
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

    row["run_id"] = args.run_id
    row["commit_sha"] = args.commit_sha

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

    # Default test stats: 1 test, 0 failed, until test stage says otherwise
    if not row["tests_total"]:
        row["tests_total"] = "1"
    if not row["tests_failed"]:
        row["tests_failed"] = "0"

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
        # Mark that tests ran *now* and capture basic test stats.
        row["test_ts"] = now_iso()
        row["tests_total"] = "1"
        if status and status != "success":
            row["tests_failed"] = "1"
        else:
            row["tests_failed"] = "0"

    elif stage == "push":
        row["push_ts"] = now_iso()

    elif stage == "deploy":
        row["deploy_ts"] = now_iso()

    elif stage == "health":
        # job.status from GA is success / failure / cancelled
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


if __name__ == "__main__":
    main()

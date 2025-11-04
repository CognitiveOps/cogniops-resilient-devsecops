#!/usr/bin/env python3
"""
s1_write_metrics.py — resilient version for full pipeline CFR/DF tracking.

✅ Records *all* pipeline runs (success & failure)
✅ Marks the failure stage (test/build/deploy/health)
✅ Always upserts one row per run_id into the CSV
✅ Optionally POSTs summary JSON to a metrics ingest endpoint (BigQuery function)
"""

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
import urllib.error


# ---------- CLI parsing ------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfile", required=True, help="CSV ledger path")
    ap.add_argument("--run_id", required=True)
    ap.add_argument("--commit_sha", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--status", default="")
    ap.add_argument("--scenario_id", default="S1")
    ap.add_argument("--branch", default="")
    ap.add_argument("--env", default="")
    ap.add_argument("--service", default="")
    ap.add_argument("--workflow", default="s1_ci.yml")
    ap.add_argument("--image", default="")
    ap.add_argument("--tests_total", type=int, default=0)
    ap.add_argument("--tests_failed", type=int, default=0)
    ap.add_argument("--post-to", dest="post_to", default="")
    ap.add_argument("--auth-token", dest="auth_token", default="")
    return ap.parse_args()


# ---------- Helpers ----------------------------------------------------------

def utc_now_iso():
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    s = s.strip().replace("Z", "")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def load_csv(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def save_csv(path: Path, rows: List[Dict]):
    if not rows:
        return
    fieldnames = sorted({k for r in rows for k in r.keys()})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = {k: r.get(k, "") for k in fieldnames}
            w.writerow(row)


# ---------- Core logic -------------------------------------------------------

def upsert_run(rows: List[Dict], args, now_iso: str) -> Dict:
    run = next((r for r in rows if r.get("run_id") == args.run_id), None)
    if not run:
        run = {
            "run_id": args.run_id,
            "workflow": args.workflow,
            "commit_sha": args.commit_sha,
            "scenario_id": args.scenario_id,
            "branch": args.branch,
            "env": args.env,
            "service": args.service,
            "started_at": now_iso,
        }
        rows.append(run)

    # Always update core info
    run["commit_sha"] = args.commit_sha
    run["workflow"] = args.workflow
    run["branch"] = args.branch
    run["env"] = args.env
    run["service"] = args.service
    run["scenario_id"] = args.scenario_id

    # Stage-specific logic
    if args.stage == "commit":
        run["started_at"] = now_iso

    elif args.stage == "test":
        run["tests_total"] = max(args.tests_total, run.get("tests_total", 0))
        run["tests_failed"] = args.tests_failed
        if args.status != "success":
            run["failure_stage"] = "test"

    elif args.stage == "push" and args.image:
        run["image"] = args.image

    elif args.stage in {"deploy", "health", "finalize"}:
        if args.status != "success":
            run["failure_stage"] = args.stage

    # Finalization: mark pipeline result and duration
    if args.stage in {"health", "finalize"} or args.status == "failure":
        run["status"] = args.status or "failure"
        run["ended_at"] = now_iso

        start_dt = parse_ts(run.get("started_at"))
        end_dt = parse_ts(run.get("ended_at"))
        if start_dt and end_dt:
            run["duration_sec"] = (end_dt - start_dt).total_seconds()
        else:
            run["duration_sec"] = 0.0
        run["inserted_at"] = utc_now_iso()

    return run


def build_summary(row: Dict) -> Dict:
    """Prepare payload for BigQuery ingest"""
    return {
        "run_id": row.get("run_id"),
        "workflow": row.get("workflow"),
        "scenario_id": row.get("scenario_id"),
        "branch": row.get("branch"),
        "env": row.get("env"),
        "service": row.get("service"),
        "status": row.get("status"),
        "failure_stage": row.get("failure_stage", ""),
        "commit_sha": row.get("commit_sha"),
        "image": row.get("image", ""),
        "tests_total": int(row.get("tests_total", 0)),
        "tests_failed": int(row.get("tests_failed", 0)),
        "started_at": row.get("started_at"),
        "ended_at": row.get("ended_at"),
        "duration_sec": float(row.get("duration_sec", 0)),
        "inserted_at": utc_now_iso(),
    }


def post_summary(url: str, token: str, payload: Dict):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"[s1_write_metrics] POST -> {r.status}")
    except urllib.error.HTTPError as e:
        print(f"[s1_write_metrics] HTTP {e.code}: {e.read().decode()}")
    except Exception as e:
        print(f"[s1_write_metrics] POST error: {e}")


# ---------- main -------------------------------------------------------------

def main():
    args = parse_args()
    path = Path(args.outfile)
    now_iso = utc_now_iso()

    rows = load_csv(path)
    run = upsert_run(rows, args, now_iso)
    save_csv(path, rows)
    print(f"[s1_write_metrics] Updated {args.stage} -> {args.status}")

    if args.stage in {"health", "finalize"}:
        if args.post_to:
            payload = build_summary(run)
            print("[s1_write_metrics] Posting run summary...")
            post_summary(args.post_to, args.auth_token, payload)


if __name__ == "__main__":
    main()

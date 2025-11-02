#!/usr/bin/env python3
# S1 metrics writer (per-scenario helper)
# - Exactly ONE row per GitHub run_id for S1 (CI/CD baseline)
# - Updates fields incrementally per stage: commit|build|test|push|deploy|health
# - Computes TTD (sec) when commit_ts & healthy_ts are present
# - Stores scenario/branch/env for per-scenario analysis (no epochs)

import csv, argparse, os
from pathlib import Path
from datetime import datetime

FIELDS = [
    "run_id","commit_sha","commit_ts","build_ts","test_status",
    "image","push_ts","deploy_ts","healthy_ts","status",
    "ttd_sec","window","notes","scenario_id","branch","env",
]

def iso_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def read_rows(p: Path):
    if not p.exists():
        return []
    with p.open("r", newline="") as f:
        r = csv.DictReader(f)
        # Normalize any missing columns to keep schema stable
        return [{**{k: "" for k in FIELDS}, **row} for row in r]

def write_rows(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outfile", required=True)
    ap.add_argument("--run_id", required=True)
    ap.add_argument("--commit_sha", required=True)
    ap.add_argument("--stage", required=True, choices=["commit","build","test","push","deploy","health"])
    ap.add_argument("--status", default="")        # success|failure|unknown
    ap.add_argument("--image", default="")         # full image ref tag@digest
    ap.add_argument("--notes", default="")
    ap.add_argument("--scenario_id", default=os.getenv("SCENARIO_ID","S1"))
    ap.add_argument("--branch",      default=os.getenv("BRANCH","main"))
    ap.add_argument("--env",         default=os.getenv("RUN_ENV","cloud-run"))
    return ap.parse_args()

def compute_ttd(row: dict) -> None:
    try:
        if row.get("commit_ts") and row.get("healthy_ts"):
            t1 = datetime.fromisoformat(row["commit_ts"].replace("Z",""))
            t2 = datetime.fromisoformat(row["healthy_ts"].replace("Z",""))
            row["ttd_sec"] = f"{(t2 - t1).total_seconds():.1f}"
    except Exception:
        # keep silent; leave ttd_sec as-is on parse errors
        pass

def main():
    args = parse()
    p = Path(args.outfile)
    rows = read_rows(p)

    row = next((r for r in rows if r.get("run_id") == args.run_id), None)
    if not row:
        row = {k: "" for k in FIELDS}
        row["run_id"] = args.run_id
        row["commit_sha"] = args.commit_sha
        # We now use lifetime statistics; keep a friendly marker in CSV
        row["window"] = "lifetime"
        rows.append(row)

    # static context (scenario-first; no epochs)
    row["scenario_id"] = args.scenario_id or row.get("scenario_id","S1")
    row["branch"]      = args.branch      or row.get("branch","main")
    row["env"]         = args.env         or row.get("env","cloud-run")

    # stage-wise updates (timestamps recorded in UTC)
    now = iso_now()
    if args.stage == "commit":
        row["commit_ts"] = now
    elif args.stage == "build":
        row["build_ts"] = now
    elif args.stage == "test":
        row["test_status"] = args.status or "unknown"
    elif args.stage == "push":
        row["push_ts"] = now
        if args.image:
            row["image"] = args.image
    elif args.stage == "deploy":
        row["deploy_ts"] = now
    elif args.stage == "health":
        row["healthy_ts"] = now
        row["status"] = args.status or row.get("status","")

    if args.notes:
        row["notes"] = args.notes

    compute_ttd(row)
    write_rows(p, rows)
    print(f"[S1] metrics updated: run_id={args.run_id}, stage={args.stage}, scenario={row['scenario_id']}")

if __name__ == "__main__":
    main()

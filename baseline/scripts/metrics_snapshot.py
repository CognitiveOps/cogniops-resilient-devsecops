#!/usr/bin/env python3
"""
metrics_snapshot.py

Builds a *per-run* snapshot for S1 metrics and keeps CSV/BQ fields aligned.

- Reads the current run's CSV (which may contain per-stage rows).
- Optionally merges in history from restored artifact CSVs.
- Groups by run_id and produces ONE canonical row per run, with fields:

    run_id, commit_sha, scenario_id, branch, env, service,
    started_at, ended_at, duration_sec, status, tests_total, tests_failed

  This matches the BigQuery table schema, so BQ and CSV stay consistent.

- Writes the merged per-run ledger back to CSV (if --write-merged-to is set).
- Computes lifetime + per-scenario CFR/DF from the per-run ledger.
"""

import argparse
import csv
import glob
import json
import collections
import datetime as dt
from pathlib import Path
from typing import Optional, Dict, List

# Canonical per-run schema, aligned with BigQuery
LEDGER_FIELDS = [
    "run_id",
    "commit_sha",
    "scenario_id",
    "branch",
    "env",
    "service",
    "started_at",
    "ended_at",
    "duration_sec",
    "status",
    "tests_total",
    "tests_failed",
]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in", dest="infile",
        default="baseline/metrics/s1_pipeline_runs.csv",
        help="Primary CSV for this run (may contain stage rows or per-run rows).",
    )
    ap.add_argument(
        "--merge-from",
        dest="merge_from",
        default="",
        help="Glob pattern for additional CSVs to merge (e.g. restored artifacts).",
    )
    ap.add_argument(
        "--write-merged-to",
        dest="write_merged_to",
        default="",
        help="If set, write the merged PER-RUN ledger CSV to this path.",
    )
    ap.add_argument(
        "--out", dest="outfile",
        default="baseline/metrics/s1_baseline_snapshot.json",
        help="Snapshot JSON output path.",
    )
    ap.add_argument(
        "--group-by",
        choices=["scenario", "none"],
        default="scenario",
        help="Aggregate per scenario_id (default) or only lifetime.",
    )
    ap.add_argument(
        "--scenario-default",
        default="S1",
        help="Fallback scenario_id if missing in rows.",
    )
    ap.add_argument(
        "--min-days",
        type=float,
        default=0.0,
        help="If >0, clamp duration days to at least this when computing DF/day.",
    )
    return ap.parse_args()


def parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    """Parse ISO-8601 with optional trailing Z. Return None if invalid/empty."""
    if not s:
        return None
    s = s.strip().replace("Z", "")
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def iso_or_none(t: Optional[dt.datetime]) -> Optional[str]:
    return t.isoformat() + "Z" if t else None


def load_csv_rows(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def merge_stage_rows(primary: Path, merge_glob: str) -> List[Dict]:
    """
    Merge rows from:
      - all CSVs matching merge_glob
      - primary CSV

    We don't dedup here by run+stage; we just concatenate.
    Dedup / per-run aggregation happens later.
    """
    rows: List[Dict] = []

    if merge_glob:
        for f in glob.glob(merge_glob, recursive=True):
            try:
                rows.extend(load_csv_rows(Path(f)))
            except Exception:
                # ignore bad files; this is best-effort history
                pass

    rows.extend(load_csv_rows(primary))
    return rows


def build_per_run_rows(stage_rows: List[Dict]) -> List[Dict]:
    """
    Take stage-level rows (commit/test/push/deploy/health) and produce exactly
    one canonical row per run_id with the LEDGER_FIELDS schema.

    For each run_id:
      - started_at: earliest of any known timestamps
      - ended_at  : latest of any known timestamps
      - duration_sec: (ended_at - started_at) in seconds, if both present
      - status: status from health stage if present, else last non-empty
      - scenario_id/branch/env/service/commit_sha: taken from latest row
      - tests_total: 1
      - tests_failed: 0 if status == "success" else 1

    If the incoming rows are already per-run (i.e. they already have started_at /
    ended_at / duration_sec and not stage-specific timestamps), this function
    just normalizes them into the same schema.
    """
    by_run: Dict[str, List[Dict]] = collections.defaultdict(list)
    for r in stage_rows:
        rid = r.get("run_id")
        if not rid:
            continue
        by_run[rid].append(r)

    per_run_rows: List[Dict] = []

    for run_id, rows in by_run.items():
        # Sort rows by any timestamp we can find, to have a stable order
        def row_any_ts(rr: Dict) -> dt.datetime:
            candidates = [
                parse_ts(rr.get("commit_ts")),
                parse_ts(rr.get("test_ts")),
                parse_ts(rr.get("deploy_ts")),
                parse_ts(rr.get("healthy_ts")),
                parse_ts(rr.get("started_at")),
                parse_ts(rr.get("ended_at")),
            ]
            for c in candidates:
                if c:
                    return c
            # fallback: "very old"
            return dt.datetime.utcfromtimestamp(0)

        rows_sorted = sorted(rows, key=row_any_ts)

        # Base info from the latest row
        latest = rows_sorted[-1]
        commit_sha = latest.get("commit_sha")
        scenario_id = latest.get("scenario_id")
        branch = latest.get("branch")
        env = latest.get("env")
        service = latest.get("service")

        # Collect all timestamps we know
        ts_candidates_start: List[dt.datetime] = []
        ts_candidates_end: List[dt.datetime] = []

        for rr in rows_sorted:
            for key in ("commit_ts", "started_at"):
                t = parse_ts(rr.get(key))
                if t:
                    ts_candidates_start.append(t)
            for key in ("healthy_ts", "deploy_ts", "ended_at", "test_ts"):
                t = parse_ts(rr.get(key))
                if t:
                    ts_candidates_end.append(t)

        start_ts = min(ts_candidates_start) if ts_candidates_start else None
        end_ts = max(ts_candidates_end) if ts_candidates_end else None

        duration_sec: Optional[float] = None
        if start_ts and end_ts and end_ts >= start_ts:
            duration_sec = (end_ts - start_ts).total_seconds()

        # Status: prefer health stage, then any explicit status on latest rows
        status = None
        for rr in rows_sorted:
            if rr.get("stage") == "health" and rr.get("status"):
                status = rr["status"]
        if not status:
            # fallback: use last non-empty status
            for rr in rows_sorted:
                if rr.get("status"):
                    status = rr["status"]
        if not status:
            status = "unknown"

        # Tests: for S1 baseline we treat 1 logical "check" per run based on final status
        tests_total = 1
        tests_failed = 0 if str(status).lower() == "success" else 1

        per_run_rows.append({
            "run_id": run_id,
            "commit_sha": commit_sha,
            "scenario_id": scenario_id,
            "branch": branch,
            "env": env,
            "service": service,
            "started_at": iso_or_none(start_ts),
            "ended_at": iso_or_none(end_ts),
            "duration_sec": duration_sec,
            "status": status,
            "tests_total": tests_total,
            "tests_failed": tests_failed,
        })

    # Sort by started_at descending for nicer CSV / queries
    per_run_rows.sort(
        key=lambda r: parse_ts(r.get("started_at")) or dt.datetime.utcfromtimestamp(0),
        reverse=True,
    )
    return per_run_rows

def row_ts_start(r: Dict) -> Optional[dt.datetime]:
    """Prefer commit_ts as run start; fallback to healthy_ts."""
    return parse_ts(r.get("commit_ts")) or parse_ts(r.get("healthy_ts"))


def row_ts_end(r: Dict) -> Optional[dt.datetime]:
    """Prefer healthy_ts as run end; fallback to commit_ts."""
    return parse_ts(r.get("healthy_ts")) or parse_ts(r.get("commit_ts"))


def duration_days(start: Optional[dt.datetime],
                  end: Optional[dt.datetime],
                  min_days: float = 0.0) -> float:
    if not start or not end:
        return 0.0
    days = (end - start).total_seconds() / 86400.0
    if min_days > 0:
        return max(days, min_days)
    return max(days, 1e-9)


def aggregate(per_run_rows: List[Dict], min_days: float) -> Dict:
    """Return dict with totals, CFR, DF/day, and time bounds for given runs."""
    tot = len(per_run_rows)
    succ = sum(1 for r in per_run_rows if (str(r.get("status", "")).lower() == "success"))
    fail = tot - succ
    cfr = (fail / tot) * 100 if tot else 0.0

    starts = [parse_ts(r.get("started_at")) for r in per_run_rows if parse_ts(r.get("started_at"))]
    ends = [parse_ts(r.get("ended_at")) for r in per_run_rows if parse_ts(r.get("ended_at"))]

    if starts and ends:
        start = min(starts)
        end = max(ends)
        days = duration_days(start, end, min_days=min_days)
    else:
        start = end = None
        days = 0.0

    df_per_day = (succ / days) if days > 0 else 0.0

    return {
        "total_runs": tot,
        "success": succ,
        "fail": fail,
        "cfr": round(cfr, 2),
        "df_per_day": round(df_per_day, 2),
        "start": iso_or_none(start),
        "end": iso_or_none(end),
        "days": round(days, 2),
    }


def build_snapshot(per_run_rows: List[Dict],
                   group_by: str,
                   scenario_default: str,
                   min_days: float) -> Dict:
    lifetime = aggregate(per_run_rows, min_days=min_days)

    snap: Dict = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "lifetime": lifetime,
    }

    if group_by == "scenario":
        by_scn = collections.defaultdict(list)
        for r in per_run_rows:
            scn = r.get("scenario_id") or scenario_default
            by_scn[scn].append(r)

        per_scenario = {}
        for scn, rs in by_scn.items():
            per_scenario[scn] = aggregate(rs, min_days=min_days)

        snap["per_scenario"] = per_scenario

    return snap


def main():
    args = parse_args()
    csv_path = Path(args.infile)
    out_path = Path(args.outfile)

    # If absolutely nothing exists, emit an empty skeleton
    if not csv_path.exists() and not args.merge_from:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "generated_at": dt.datetime.utcnow().isoformat() + "Z",
            "lifetime": {
                "total_runs": 0,
                "success": 0,
                "fail": 0,
                "cfr": 0.0,
                "df_per_day": 0.0,
                "start": None,
                "end": None,
                "days": 0.0,
            },
            "per_scenario": {} if args.group_by == "scenario" else None,
        }, indent=2))
        print(f"[metrics_snapshot] Snapshot written (empty): {out_path}")
        return

    # 1) Merge stage rows from local + restored CSVs
    stage_rows = merge_stage_rows(csv_path, args.merge_from)

    # 2) Convert to canonical per-run rows, aligned with BigQuery schema
    per_run_rows = build_per_run_rows(stage_rows)

    # 3) Optionally write the per-run ledger CSV
    if args.write_merged_to:
        dest = Path(args.write_merged_to)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if per_run_rows:
            with dest.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
                w.writeheader()
                for r in per_run_rows:
                    # ensure all fields exist
                    row = {k: r.get(k) for k in LEDGER_FIELDS}
                    w.writerow(row)
        print(f"[metrics_snapshot] Per-run ledger written to: {dest}")

    # 4) Build snapshot from the same per-run ledger
    snap = build_snapshot(
        per_run_rows,
        group_by=args.group_by,
        scenario_default=args.scenario_default,
        min_days=args.min_days,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")


if __name__ == "__main__":
    main()

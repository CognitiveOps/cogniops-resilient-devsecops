#!/usr/bin/env python3
"""
metrics_snapshot.py
Generic snapshot builder for baseline & secure pipeline metrics.

Computes lifetime CFR/DF and optional GROUPED rollups (time-normalized)
from any pipeline CSV.

Extra features:
- Can merge historical CSVs from artifacts (via --merge-from glob)
- Can write the merged ledger back to a CSV (via --write-merged-to)
- Can enforce a minimum time window in days for DF (via --min-days)

Usage (as in s1_ci.yml):

  python metrics_snapshot.py \
      --in baseline/metrics/s1_pipeline_runs.csv \
      --merge-from "baseline/metrics/_restore/**/s1_pipeline_runs.csv" \
      --write-merged-to baseline/metrics/s1_pipeline_runs.csv \
      --out baseline/metrics/s1_baseline_snapshot.json \
      --group-by scenario \
      --scenario-default S1 \
      --min-days 1.0
"""

import argparse
import collections
import csv
import datetime as dt
import glob
import json
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="infile",
        default="baseline/metrics/s1_pipeline_runs.csv",
        help="Primary metrics CSV (current run writes here).",
    )
    ap.add_argument(
        "--out",
        dest="outfile",
        default="baseline/metrics/s1_baseline_snapshot.json",
        help="Snapshot JSON output.",
    )

    # Historical merge controls
    ap.add_argument(
        "--merge-from",
        dest="merge_from",
        default="",
        help="Glob pattern for historical CSVs (e.g. restored artifacts).",
    )
    ap.add_argument(
        "--write-merged-to",
        dest="write_merged_to",
        default="",
        help="Optional path to write the merged ledger CSV.",
    )

    # Grouping (epochs removed – scenarios only or none)
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
        dest="min_days",
        type=float,
        default=0.0,
        help="Minimum number of days for DF normalization (e.g. 1.0).",
    )

    return ap.parse_args()


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

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


def row_ts_start(r: Dict) -> Optional[dt.datetime]:
    """Prefer commit_ts as run start; fallback to healthy_ts."""
    return parse_ts(r.get("commit_ts")) or parse_ts(r.get("healthy_ts"))


def row_ts_end(r: Dict) -> Optional[dt.datetime]:
    """Prefer healthy_ts as run end; fallback to commit_ts."""
    return parse_ts(r.get("healthy_ts")) or parse_ts(r.get("commit_ts"))


def duration_days(start: Optional[dt.datetime],
                  end: Optional[dt.datetime],
                  min_days: float) -> float:
    if not start or not end:
        return 0.0
    days = (end - start).total_seconds() / 86400.0
    # avoid division by zero and optionally enforce minimum window
    days = max(days, 1e-9)
    if min_days > 0:
        days = max(days, min_days)
    return days


# ---------------------------------------------------------------------------
# CSV merging
# ---------------------------------------------------------------------------

def merge_rows(main_csv: Path, merge_glob: str) -> List[Dict]:
    """
    Merge rows from:
      1) any CSVs matching merge_glob (historical artifacts)
      2) the main_csv (current run)
    De-duplicate by run_id when available.
    """
    rows: List[Dict] = []
    seen_keys = set()

    def add_rows_from_file(path: Path):
        if not path.exists():
            return
        try:
            with path.open(newline="") as fp:
                reader = csv.DictReader(fp)
                for r in reader:
                    key = r.get("run_id") or f"{r.get('commit_sha','')}::{r.get('started_at','')}"
                    if key and key not in seen_keys:
                        rows.append(r)
                        seen_keys.add(key)
        except Exception:
            # Best-effort; ignore corrupt files
            return

    # 1) historical CSVs
    if merge_glob:
        for fname in glob.glob(merge_glob, recursive=True):
            add_rows_from_file(Path(fname))

    # 2) primary CSV
    add_rows_from_file(main_csv)

    return rows


def write_merged_csv(path: Path, rows: List[Dict]) -> None:
    if not rows:
        return
    # Union of all keys to avoid losing columns
    fields = sorted({k for r in rows for k in r.keys()})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Aggregation logic
# ---------------------------------------------------------------------------

def aggregate(rows: List[Dict], min_days: float) -> Dict:
    """Return dict with totals, CFR, DF/day, and time bounds for given rows."""
    tot = len(rows)
    succ = sum(1 for r in rows if (r.get("status", "").lower() == "success"))
    fail = tot - succ
    cfr = (fail / tot) * 100 if tot else 0.0

    starts = [row_ts_start(r) for r in rows if row_ts_start(r)]
    ends = [row_ts_end(r) for r in rows if row_ts_end(r)]
    if starts and ends:
        start = min(starts)
        end = max(ends)
        days = duration_days(start, end, min_days)
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
        "start": start.isoformat() + "Z" if start else None,
        "end": end.isoformat() + "Z" if end else None,
        "days": round(days, 2),
    }


def build_snapshot(rows: List[Dict],
                   group_by: str,
                   scenario_default: str,
                   min_days: float) -> Dict:
    # Lifetime over all history
    lifetime = aggregate(rows, min_days)

    snap: Dict[str, object] = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "lifetime": lifetime,
    }

    if group_by == "scenario":
        by_scn = collections.defaultdict(list)
        for r in rows:
            scn = r.get("scenario_id") or scenario_default
            by_scn[scn].append(r)

        per_scenario: Dict[str, Dict] = {}
        for scn, rs in by_scn.items():
            per_scenario[scn] = aggregate(rs, min_days)

        snap["per_scenario"] = per_scenario

    return snap


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    csv_path = Path(args.infile)
    out_path = Path(args.outfile)

    # Merge history (artifacts + current CSV)
    rows = merge_rows(csv_path, args.merge_from)

    # If nothing at all, emit empty skeleton
    if not rows:
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

    # Optionally write merged ledger CSVback
    if args.write_merged_to:
        write_merged_csv(Path(args.write_merged_to), rows)

    snap = build_snapshot(rows, args.group_by, args.scenario_default, args.min_days)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")


if __name__ == "__main__":
    main()

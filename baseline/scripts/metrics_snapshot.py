#!/usr/bin/env python3
"""
metrics_snapshot.py
Generic snapshot builder for baseline & secure pipeline metrics.

- Can merge historical CSVs (e.g., restored artifacts) + the current CSV.
- De-duplicates by run_id.
- Computes lifetime CFR/DF and optional per-scenario rollups (time-normalized).

Usage examples:
  python metrics_snapshot.py \
      --in baseline/metrics/s1_pipeline_runs.csv \
      --merge-from "baseline/metrics/_restore/**/s1_pipeline_runs.csv" \
      --write-merged-to baseline/metrics/s1_pipeline_runs.csv \
      --out baseline/metrics/s1_baseline_snapshot.json \
      --group-by scenario \
      --scenario-default S1
"""

import argparse, csv, json, glob, collections, datetime as dt
from pathlib import Path
from typing import Optional, Dict, List


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="infile",  default="baseline/metrics/s1_pipeline_runs.csv")
    ap.add_argument("--out", dest="outfile", default="baseline/metrics/s1_baseline_snapshot.json")

    # Merging controls
    ap.add_argument("--merge-from", nargs="*", default=[],
                    help="Glob(s) of extra CSVs to merge (e.g., restored artifacts).")
    ap.add_argument("--write-merged-to", default="",
                    help="If set, write the merged, de-duplicated ledger to this CSV path.")

    # Grouping controls (epochs removed)
    ap.add_argument("--group-by", choices=["scenario", "none"], default="scenario",
                    help="Aggregate per scenario_id (default) or only lifetime.")
    ap.add_argument("--scenario-default", default="S1",
                    help="Fallback scenario_id if missing in rows.")

    # Normalization guard (avoid DF/day explosion when time window ~0)
    ap.add_argument("--min-days", type=float, default=0.0,
                    help="Clamp normalization window to at least this many days when computing DF/day (default 0.0).")
    return ap.parse_args()


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


def row_ts_start(r: Dict) -> Optional[dt.datetime]:
    # Prefer commit_ts as run start; fallback to healthy_ts.
    return parse_ts(r.get("commit_ts")) or parse_ts(r.get("healthy_ts"))


def row_ts_end(r: Dict) -> Optional[dt.datetime]:
    # Prefer healthy_ts as run end; fallback to commit_ts.
    return parse_ts(r.get("healthy_ts")) or parse_ts(r.get("commit_ts"))


def duration_days(start: Optional[dt.datetime], end: Optional[dt.datetime]) -> float:
    if not start or not end:
        return 0.0
    # Tiny epsilon to avoid division-by-zero
    return max((end - start).total_seconds() / 86400.0, 1e-9)


def aggregate(rows: List[Dict], min_days: float) -> Dict:
    """Return dict with totals, CFR, DF/day, and time bounds for given rows."""
    tot = len(rows)
    succ = sum(1 for r in rows if (r.get("status", "").lower() == "success"))
    fail = tot - succ
    cfr = (fail / tot) * 100 if tot else 0.0

    starts = [row_ts_start(r) for r in rows if row_ts_start(r)]
    ends   = [row_ts_end(r)   for r in rows if row_ts_end(r)]
    if starts and ends:
        start = min(starts)
        end   = max(ends)
        days  = duration_days(start, end)
    else:
        start = end = None
        days = 0.0

    # Normalize DF over at least min_days if requested
    norm_days = max(days, float(min_days)) if succ else max(days, 0.0)
    df_per_day = (succ / norm_days) if norm_days > 0 else 0.0

    return {
        "total_runs": tot,
        "success": succ,
        "fail": fail,
        "cfr": round(cfr, 2),
        "df_per_day": round(df_per_day, 2),
        "start": start.isoformat() + "Z" if start else None,
        "end":   end.isoformat() + "Z" if end else None,
        "days": round(days, 2),
    }


def read_csv_rows(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open(newline="") as fp:
        return list(csv.DictReader(fp))


def merge_rows(primary: List[Dict], extras: List[List[Dict]]) -> List[Dict]:
    """Merge multiple row lists, de-duplicate by run_id (first wins)."""
    out, seen = [], set()
    def add_rows(rows):
        for r in rows:
            rid = (r.get("run_id") or "").strip()
            if not rid:
                continue
            if rid in seen:
                continue
            out.append(r)
            seen.add(rid)

    # Merge extras first (historical), then primary (current file),
    # so current run won't be accidentally shadowed by stale duplicates.
    for rows in extras:
        add_rows(rows)
    add_rows(primary)
    return out


def write_csv_rows(path: Path, rows: List[Dict]):
    if not rows:
        # Write an empty CSV with a minimal header for consistency
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=["run_id"])
            w.writeheader()
        return

    # Use the union of all keys as header to avoid losing columns
    fieldset = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                fieldset.append(k)
                seen.add(k)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldset)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def build_snapshot(rows: List[Dict], group_by: str, scenario_default: str, min_days: float) -> Dict:
    # Lifetime over all history
    lifetime = aggregate(rows, min_days)

    snap = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "lifetime": lifetime,
    }

    if group_by == "scenario":
        by_scn = collections.defaultdict(list)
        for r in rows:
            scn = r.get("scenario_id") or scenario_default
            by_scn[scn].append(r)

        per_scenario = {}
        for scn, rs in by_scn.items():
            per_scenario[scn] = aggregate(rs, min_days)

        snap["per_scenario"] = per_scenario

    return snap


def main():
    args = parse_args()
    csv_path = Path(args.infile)
    out_path = Path(args.outfile)

    # Collect rows: extras (merge-from globs) + current CSV
    extras: List[List[Dict]] = []
    for g in args.merge_from:
        for f in glob.glob(g, recursive=True):
            extras.append(read_csv_rows(Path(f)))

    primary = read_csv_rows(csv_path)
    merged = merge_rows(primary, extras)

    # Optionally write back the merged ledger (so next run starts with history)
    if args.write_merged_to:
        write_csv_rows(Path(args.write_merged_to), merged)

    # If nothing to aggregate, write an empty skeleton
    if not merged:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "generated_at": dt.datetime.utcnow().isoformat() + "Z",
            "lifetime": {
                "total_runs": 0, "success": 0, "fail": 0, "cfr": 0.0,
                "df_per_day": 0.0, "start": None, "end": None, "days": 0.0
            },
            "per_scenario": {} if args.group_by == "scenario" else None
        }, indent=2))
        print(f"[metrics_snapshot] Snapshot written (empty): {out_path}")
        return

    snap = build_snapshot(merged, args.group_by, args.scenario_default, args.min_days)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")


if __name__ == "__main__":
    main()

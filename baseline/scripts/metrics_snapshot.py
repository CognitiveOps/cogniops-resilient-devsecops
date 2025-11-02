#!/usr/bin/env python3
"""
metrics_snapshot.py
Generic snapshot builder for baseline & secure pipeline metrics.

Computes lifetime CFR/DF and optional GROUPED rollups (time-normalized) from any
pipeline CSV. Grouping is scenario-first (e.g., S1, SS1, S2...), no epochs.

Usage:
  python metrics_snapshot.py \
      --in baseline/metrics/s1_pipeline_runs.csv \
      --out baseline/metrics/s1_snapshot.json \
      --group-by scenario \
      --scenario-default S1
"""

import argparse, csv, json, collections, datetime as dt
from pathlib import Path
from typing import Optional, Dict, List


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="infile",  default="baseline/metrics/s1_pipeline_runs.csv")
    ap.add_argument("--out", dest="outfile", default="baseline/metrics/s1_baseline_snapshot.json")
    # grouping controls (epochs removed)
    ap.add_argument("--group-by",
                    choices=["scenario", "none"],
                    default="scenario",
                    help="Aggregate per scenario_id (default) or produce only lifetime metrics.")
    ap.add_argument("--scenario-default",
                    default="S1",
                    help="Fallback scenario_id if missing in rows.")
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


def row_ts_start(r: Dict) -> Optional[dt.datetime]:
    """Prefer commit_ts as run start; fallback to healthy_ts."""
    return parse_ts(r.get("commit_ts")) or parse_ts(r.get("healthy_ts"))


def row_ts_end(r: Dict) -> Optional[dt.datetime]:
    """Prefer healthy_ts as run end; fallback to commit_ts."""
    return parse_ts(r.get("healthy_ts")) or parse_ts(r.get("commit_ts"))


def duration_days(start: Optional[dt.datetime], end: Optional[dt.datetime]) -> float:
    if not start or not end:
        return 0.0
    # Avoid division by zero; keep tiny epsilon for normalization
    return max((end - start).total_seconds() / 86400.0, 1e-9)


def aggregate(rows: List[Dict]) -> Dict:
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

    df_per_day = (succ / days) if days > 0 else 0.0

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


def build_snapshot(rows: List[Dict], group_by: str, scenario_default: str) -> Dict:
    # Lifetime over all history
    lifetime = aggregate(rows)

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
            per_scenario[scn] = aggregate(rs)

        snap["per_scenario"] = per_scenario

    return snap


def main():
    args = parse_args()
    csv_path = Path(args.infile)
    out_path = Path(args.outfile)

    if not csv_path.exists():
        # Create empty snapshot skeleton to avoid failing the workflow late
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

    rows = list(csv.DictReader(csv_path.open()))
    snap = build_snapshot(rows, args.group_by, args.scenario_default)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")


if __name__ == "__main__":
    main()

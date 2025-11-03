#!/usr/bin/env python3
"""
metrics_snapshot.py — enhanced version with GitHub Actions failed-runs backfill

- Merges CSVs (current + restored artifacts)
- Optionally pulls failed runs via GitHub API (if GITHUB_TOKEN is available)
- Writes merged ledger to CSV
- Computes lifetime + per-scenario CFR/DF
"""

import argparse, csv, glob, json, collections, datetime as dt, os, requests
from pathlib import Path
from typing import Optional, Dict, List

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="baseline/metrics/s1_pipeline_runs.csv")
    ap.add_argument("--merge-from", dest="merge_from", default="")
    ap.add_argument("--write-merged-to", dest="write_merged_to", default="")
    ap.add_argument("--out", dest="outfile", default="baseline/metrics/s1_baseline_snapshot.json")
    ap.add_argument("--group-by", choices=["scenario", "none"], default="scenario")
    ap.add_argument("--scenario-default", default="S1")
    ap.add_argument("--min-days", type=float, default=0.0)
    return ap.parse_args()

# --- GitHub API helper ---------------------------------------------------------
def fetch_failed_runs(repo: str, token: str, limit=100):
    """Fetch failed workflow runs from GitHub Actions API"""
    url = f"https://api.github.com/repos/{repo}/actions/runs?per_page={limit}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            print(f"[metrics_snapshot] ⚠️ Failed to fetch runs: {r.status_code} {r.text}")
            return []
        data = r.json().get("workflow_runs", [])
    except Exception as e:
        print(f"[metrics_snapshot] ⚠️ API error: {e}")
        return []

    failed = []
    for run in data:
        if run.get("conclusion") == "failure":
            failed.append({
                "run_id": str(run["id"]),
                "commit_sha": run.get("head_sha", ""),
                "scenario_id": "S1",
                "branch": run.get("head_branch", ""),
                "env": "cloud-run",
                "status": "failure",
                "commit_ts": run.get("created_at", ""),
                "healthy_ts": run.get("updated_at", ""),
            })
    print(f"[metrics_snapshot] Pulled {len(failed)} failed runs from GitHub API")
    return failed

# --- Timestamp helpers --------------------------------------------------------
def parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    if not s: return None
    s = s.strip().replace("Z","")
    try: return dt.datetime.fromisoformat(s)
    except: return None

def row_ts_start(r: Dict) -> Optional[dt.datetime]:
    return parse_ts(r.get("commit_ts")) or parse_ts(r.get("healthy_ts"))

def row_ts_end(r: Dict) -> Optional[dt.datetime]:
    return parse_ts(r.get("healthy_ts")) or parse_ts(r.get("commit_ts"))

def duration_days(start, end, min_days=0.0) -> float:
    if not start or not end: return 0.0
    d = (end - start).total_seconds() / 86400.0
    return max(d, min_days if min_days>0 else 1e-9)

# --- CSV loading and merging ---------------------------------------------------
def load_csv_rows(path: Path) -> List[Dict]:
    if not path.exists(): return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))

def merge_ledgers(primary: Path, merge_glob: str) -> List[Dict]:
    rows, seen = [], set()
    if merge_glob:
        for f in glob.glob(merge_glob, recursive=True):
            try:
                for r in load_csv_rows(Path(f)):
                    rid = r.get("run_id")
                    if rid and rid not in seen:
                        rows.append(r); seen.add(rid)
            except: pass
    for r in load_csv_rows(primary):
        rid = r.get("run_id")
        if rid and rid not in seen:
            rows.append(r); seen.add(rid)
    return rows

# --- Aggregation logic ---------------------------------------------------------
def aggregate(rows: List[Dict], min_days: float) -> Dict:
    tot = len(rows)
    succ = sum(1 for r in rows if r.get("status","").lower()=="success")
    fail = tot - succ
    cfr = (fail/tot)*100 if tot else 0.0
    starts = [row_ts_start(r) for r in rows if row_ts_start(r)]
    ends   = [row_ts_end(r)   for r in rows if row_ts_end(r)]
    if starts and ends:
        start, end = min(starts), max(ends)
        days = duration_days(start,end,min_days)
    else:
        start=end=None; days=0.0
    df_day = succ/days if days>0 else 0.0
    return {
        "total_runs": tot, "success": succ, "fail": fail,
        "cfr": round(cfr,2), "df_per_day": round(df_day,2),
        "start": start.isoformat()+"Z" if start else None,
        "end": end.isoformat()+"Z" if end else None,
        "days": round(days,2)
    }

def build_snapshot(rows, group_by, scenario_default, min_days):
    lifetime = aggregate(rows, min_days)
    snap = {"generated_at": dt.datetime.utcnow().isoformat()+"Z", "lifetime": lifetime}
    if group_by=="scenario":
        by_scn=collections.defaultdict(list)
        for r in rows:
            by_scn[r.get("scenario_id") or scenario_default].append(r)
        snap["per_scenario"]={k:aggregate(v,min_days) for k,v in by_scn.items()}
    return snap

# --- Main ---------------------------------------------------------------------
def main():
    args = parse_args()
    csv_path, out_path = Path(args.infile), Path(args.outfile)

    merged = merge_ledgers(csv_path, args.merge_from)

    # backfill failed runs directly from GitHub
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if token and repo:
        failed = fetch_failed_runs(repo, token)
        existing_ids = {r["run_id"] for r in merged}
        for r in failed:
            if r["run_id"] not in existing_ids:
                merged.append(r)
        print(f"[metrics_snapshot] Total rows after GitHub backfill: {len(merged)}")

    # write merged ledger
    if args.write_merged_to and merged:
        dest=Path(args.write_merged_to); dest.parent.mkdir(parents=True,exist_ok=True)
        all_fields=set().union(*(r.keys() for r in merged))
        with dest.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=sorted(all_fields))
            w.writeheader(); w.writerows(merged)
        print(f"[metrics_snapshot] Merged ledger written to {dest}")

    snap=build_snapshot(merged,args.group_by,args.scenario_default,args.min_days)
    out_path.parent.mkdir(parents=True,exist_ok=True)
    out_path.write_text(json.dumps(snap,indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")

if __name__=="__main__":
    main()

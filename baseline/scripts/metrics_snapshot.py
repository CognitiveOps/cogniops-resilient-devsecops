#!/usr/bin/env python3
"""
metrics_snapshot.py

Builds a *per-run* snapshot for S1 metrics and keeps CSV/BQ fields aligned.

Data sources:
1) Local + restored CSV history (stage-level or per-run)
2) (Optional) GitHub Actions API for runs missing from CSV

Outputs:
- A canonical *per-run ledger* (CSV) aligned with BigQuery schema:
    run_id, commit_sha, scenario_id, branch, env, service,
    started_at, ended_at, duration_sec, status, tests_total, tests_failed,
    cfr, df_per_day

- A snapshot JSON file (lifetime + per-scenario aggregates):
    lifetime.cfr / lifetime.df_per_day / total_runs, etc.

Usage from GitHub Actions:

  python baseline/scripts/metrics_snapshot.py \
      --in baseline/metrics/s1_pipeline_runs.csv \
      --merge-from "baseline/metrics/_restore/**/s1_pipeline_runs.csv" \
      --write-merged-to baseline/metrics/s1_pipeline_runs.csv \
      --out baseline/metrics/s1_baseline_snapshot.json \
      --group-by scenario \
      --scenario-default S1 \
      --min-days 1.0 \
      --github-repo "${GITHUB_REPOSITORY}" \
      --github-token "${GITHUB_TOKEN}" \
      --github-workflow "s1_ci.yml"
"""

import argparse
import csv
import glob
import json
import collections
import datetime as dt
from pathlib import Path
from typing import Optional, Dict, List

try:
    import requests  # for GitHub API integration
except Exception:
    requests = None


# --- Canonical per-run schema ---
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
    "cfr",
    "df_per_day",
]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default="baseline/metrics/s1_pipeline_runs.csv")
    ap.add_argument("--merge-from", dest="merge_from", default="")
    ap.add_argument("--write-merged-to", dest="write_merged_to", default="")
    ap.add_argument("--out", dest="outfile", default="baseline/metrics/s1_baseline_snapshot.json")
    ap.add_argument("--group-by", choices=["scenario", "none"], default="scenario")
    ap.add_argument("--scenario-default", default="S1")
    ap.add_argument("--min-days", type=float, default=0.0)

    # GitHub API options
    ap.add_argument("--github-repo", default="")
    ap.add_argument("--github-token", default="")
    ap.add_argument("--github-workflow", default="")
    ap.add_argument("--github-max-pages", type=int, default=5)
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


def iso_or_none(t: Optional[dt.datetime]) -> Optional[str]:
    return t.isoformat() + "Z" if t else None


def load_csv_rows(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def merge_stage_rows(primary: Path, merge_glob: str) -> List[Dict]:
    """
    Merge rows from local and restored CSVs (stage-level or per-run).
    """
    rows: List[Dict] = []
    if merge_glob:
        for f in glob.glob(merge_glob, recursive=True):
            try:
                rows.extend(load_csv_rows(Path(f)))
            except Exception:
                pass
    rows.extend(load_csv_rows(primary))
    return rows


def build_per_run_rows(stage_rows: List[Dict]) -> List[Dict]:
    """
    Converts stage-level rows (commit/test/push/deploy/health)
    into one canonical per-run row with LEDGER_FIELDS.
    """
    by_run: Dict[str, List[Dict]] = collections.defaultdict(list)
    for r in stage_rows:
        rid = r.get("run_id")
        if rid:
            by_run[rid].append(r)

    per_run_rows: List[Dict] = []

    for run_id, rows in by_run.items():
        def row_any_ts(rr: Dict) -> dt.datetime:
            for key in ("commit_ts", "test_ts", "deploy_ts", "ended_ts", "started_at", "ended_at"):
                t = parse_ts(rr.get(key))
                if t:
                    return t
            return dt.datetime.utcfromtimestamp(0)

        rows_sorted = sorted(rows, key=row_any_ts)
        latest = rows_sorted[-1]

        # Core metadata
        commit_sha = latest.get("commit_sha")
        scenario_id = latest.get("scenario_id")
        branch = latest.get("branch")
        env = latest.get("env")
        service = latest.get("service")

        # Compute timestamps
        ts_start = [parse_ts(r.get("commit_ts") or r.get("started_at")) for r in rows_sorted if parse_ts(r.get("commit_ts") or r.get("started_at"))]
        ts_end = [parse_ts(r.get("ended_ts") or r.get("ended_at") or r.get("deploy_ts")) for r in rows_sorted if parse_ts(r.get("ended_ts") or r.get("ended_at") or r.get("deploy_ts"))]
        start = min(ts_start) if ts_start else None
        end = max(ts_end) if ts_end else None

        duration_sec = (end - start).total_seconds() if start and end and end >= start else None

        # Status logic
        status = None
        for rr in rows_sorted:
            if rr.get("stage") == "health" and rr.get("status"):
                status = rr["status"]
        if not status:
            for rr in rows_sorted:
                if rr.get("status"):
                    status = rr["status"]
        if not status:
            status = "unknown"

        per_run_rows.append({
            "run_id": run_id,
            "commit_sha": commit_sha,
            "scenario_id": scenario_id,
            "branch": branch,
            "env": env,
            "service": service,
            "started_at": iso_or_none(start),
            "ended_at": iso_or_none(end),
            "duration_sec": duration_sec,
            "status": status,
            "tests_total": 1,
            "tests_failed": 0 if str(status).lower() == "success" else 1,
        })

    per_run_rows.sort(
        key=lambda r: parse_ts(r.get("started_at")) or dt.datetime.utcfromtimestamp(0),
        reverse=True,
    )
    return per_run_rows


def duration_days(start: Optional[dt.datetime], end: Optional[dt.datetime], min_days: float = 0.0) -> float:
    if not start or not end:
        return 0.0
    days = (end - start).total_seconds() / 86400.0
    return max(days, min_days) if min_days > 0 else max(days, 1e-9)


def aggregate(per_run_rows: List[Dict], min_days: float) -> Dict:
    """
    Compute lifetime or per-scenario aggregates:
    total_runs, success, fail, CFR (%), DF/day, start/end bounds.
    """
    tot = len(per_run_rows)
    succ = sum(1 for r in per_run_rows if str(r.get("status", "")).lower() == "success")
    fail = tot - succ
    cfr = (fail / tot) * 100 if tot else 0.0

    starts = [parse_ts(r.get("started_at")) for r in per_run_rows if parse_ts(r.get("started_at"))]
    ends = [parse_ts(r.get("ended_at")) for r in per_run_rows if parse_ts(r.get("ended_at"))]
    start, end = (min(starts), max(ends)) if starts and ends else (None, None)
    days = duration_days(start, end, min_days)
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


def github_fetch_runs(repo: str, token: str, workflow: str = "", max_pages: int = 5) -> List[Dict]:
    """
    Fetch workflow runs from the GitHub Actions API.
    """
    if not requests:
        print("[metrics_snapshot] requests not available, skipping GitHub sync")
        return []

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    runs: List[Dict] = []

    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs" if workflow else f"https://api.github.com/repos/{repo}/actions/runs"
        params = {"per_page": 100, "page": page}

        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"[metrics_snapshot] GitHub API status {resp.status_code}: {resp.text}")
            break

        data = resp.json()
        page_runs = data.get("workflow_runs") or data.get("runs") or []
        if not page_runs:
            break
        runs.extend(page_runs)
        if len(page_runs) < 100:
            break

    print(f"[metrics_snapshot] GitHub API fetched {len(runs)} runs")
    return runs


def github_runs_to_per_run_rows(gh_runs: List[Dict], existing_ids: set, scenario_default: str) -> List[Dict]:
    """
    Convert GitHub workflow_runs into canonical per-run rows.
    """
    extra_rows: List[Dict] = []
    for run in gh_runs:
        rid = str(run.get("id"))
        if not rid or rid in existing_ids:
            continue

        created_at, updated_at = run.get("created_at"), run.get("updated_at")
        start_ts, end_ts = parse_ts(created_at), parse_ts(updated_at)
        duration = (end_ts - start_ts).total_seconds() if start_ts and end_ts else None
        status = (run.get("conclusion") or run.get("status") or "unknown").lower()

        extra_rows.append({
            "run_id": rid,
            "commit_sha": run.get("head_sha"),
            "scenario_id": scenario_default,
            "branch": run.get("head_branch"),
            "env": None,
            "service": None,
            "started_at": created_at,
            "ended_at": updated_at,
            "duration_sec": duration,
            "status": status,
            "tests_total": 1,
            "tests_failed": 0 if status == "success" else 1,
        })
    print(f"[metrics_snapshot] Added {len(extra_rows)} runs from GitHub API")
    return extra_rows


def build_snapshot(per_run_rows: List[Dict], group_by: str, scenario_default: str, min_days: float) -> Dict:
    lifetime = aggregate(per_run_rows, min_days)
    snap: Dict = {"generated_at": dt.datetime.utcnow().isoformat() + "Z", "lifetime": lifetime}

    if group_by == "scenario":
        by_scn = collections.defaultdict(list)
        for r in per_run_rows:
            scn = r.get("scenario_id") or scenario_default
            by_scn[scn].append(r)
        snap["per_scenario"] = {scn: aggregate(rs, min_days) for scn, rs in by_scn.items()}
    return snap


def main():
    args = parse_args()
    csv_path, out_path = Path(args.infile), Path(args.outfile)

    # Empty skeleton if no data exists
    if not csv_path.exists() and not args.merge_from:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "generated_at": dt.datetime.utcnow().isoformat() + "Z",
            "lifetime": {"total_runs": 0, "success": 0, "fail": 0, "cfr": 0.0, "df_per_day": 0.0, "start": None, "end": None, "days": 0.0},
            "per_scenario": {} if args.group_by == "scenario" else None,
        }, indent=2))
        print(f"[metrics_snapshot] Snapshot written (empty): {out_path}")
        return

    # Merge and aggregate runs
    stage_rows = merge_stage_rows(csv_path, args.merge_from)
    per_run_rows = build_per_run_rows(stage_rows)
    existing_ids = {r["run_id"] for r in per_run_rows if r.get("run_id")}

    # GitHub sync for missing runs
    if args.github_repo and args.github_token:
        gh_runs = github_fetch_runs(args.github_repo, args.github_token, args.github_workflow, args.github_max_pages)
        per_run_rows.extend(github_runs_to_per_run_rows(gh_runs, existing_ids, args.scenario_default))
        per_run_rows.sort(key=lambda r: parse_ts(r.get("started_at")) or dt.datetime.utcfromtimestamp(0), reverse=True)

    # Compute global CFR/DF and add as fields to each row
    global_metrics = aggregate(per_run_rows, args.min_days)
    cfr, df_per_day = global_metrics["cfr"], global_metrics["df_per_day"]
    for r in per_run_rows:
        r["cfr"], r["df_per_day"] = cfr, df_per_day

    # Write merged CSV
    if args.write_merged_to:
        dest = Path(args.write_merged_to)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
            writer.writeheader()
            writer.writerows(per_run_rows)
        print(f"[metrics_snapshot] Per-run ledger written to: {dest}")

    # Build and write snapshot JSON
    snap = build_snapshot(per_run_rows, args.group_by, args.scenario_default, args.min_days)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")


if __name__ == "__main__":
    main()

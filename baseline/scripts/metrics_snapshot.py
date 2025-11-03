#!/usr/bin/env python3
"""
metrics_snapshot.py
Generic snapshot builder for baseline & secure pipeline metrics.

Features:
- Optionally MERGE CSV history from GitHub artifact restores (glob pattern).
- Produce lifetime CFR/DF (time-normalized).
- Optionally group by scenario_id (S1, SS1, S2, ...).
- Optional minimum time window (min_days) for DF/day to avoid "exploding" rates.
- Optional upload of ALL runs to an HTTP ingest endpoint (e.g. Cloud Function
  that writes to BigQuery), so history goes to BQ, not only the last run.

Typical usage from S1 CI workflow:

  python baseline/scripts/metrics_snapshot.py \
      --in baseline/metrics/s1_pipeline_runs.csv \
      --merge-from "baseline/metrics/_restore/**/s1_pipeline_runs.csv" \
      --write-merged-to baseline/metrics/s1_pipeline_runs.csv \
      --out baseline/metrics/s1_baseline_snapshot.json \
      --group-by scenario \
      --scenario-default S1 \
      --min-days 1.0 \
      --upload-to "$METRICS_INGEST_URL" \
      --service "baseline-app"
"""

import argparse
import collections
import csv
import datetime as dt
import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


# Expected CSV fields from s1_write_metrics.py (order is cosmetic)
FIELDS = [
    "run_id",
    "commit_sha",
    "commit_ts",
    "build_ts",
    "test_status",
    "image",
    "push_ts",
    "deploy_ts",
    "healthy_ts",
    "status",
    "ttd_sec",
    "cfr_window",
    "notes",
    "scenario_id",
    "branch",
    "env",
]


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in",
        dest="infile",
        default="baseline/metrics/s1_pipeline_runs.csv",
        help="Input CSV ledger with per-run metrics (from s1_write_metrics.py)",
    )
    ap.add_argument(
        "--merge-from",
        dest="merge_from",
        default=None,
        help=(
            "Optional glob pattern for additional CSVs to merge into a unified "
            "ledger (e.g. restored artifacts). Example: "
            "'baseline/metrics/_restore/**/s1_pipeline_runs.csv'"
        ),
    )
    ap.add_argument(
        "--write-merged-to",
        dest="merged_out",
        default=None,
        help=(
            "If set, write the merged ledger to this CSV and use it for "
            "snapshot calculations. If omitted, the infile path is used."
        ),
    )
    ap.add_argument(
        "--out",
        dest="outfile",
        default="baseline/metrics/s1_baseline_snapshot.json",
        help="Output JSON snapshot file.",
    )

    # Grouping controls (epochs removed – grouping is by scenario_id)
    ap.add_argument(
        "--group-by",
        choices=["scenario", "none"],
        default="scenario",
        help="Aggregate per scenario_id (default) or only lifetime metrics.",
    )
    ap.add_argument(
        "--scenario-default",
        default="S1",
        help="Fallback scenario_id if missing in rows.",
    )

    # DF/day normalization
    ap.add_argument(
        "--min-days",
        dest="min_days",
        type=float,
        default=0.0,
        help=(
            "Minimum time window in days used to normalize DF/day. "
            "Example: 1.0 → at least one day for DF/day calculation, "
            "so very short histories don't explode."
        ),
    )

    # Optional HTTP ingest upload (e.g. BigQuery via Cloud Function)
    ap.add_argument(
        "--upload-to",
        dest="upload_to",
        default=None,
        help=(
            "If set, POST all runs as JSON payloads to this HTTP endpoint "
            "(e.g. Cloud Function that writes into BigQuery)."
        ),
    )
    ap.add_argument(
        "--service",
        dest="service",
        default=None,
        help=(
            "Service name for upload payloads (e.g. 'baseline-app'). "
            "Used only if --upload-to is provided."
        ),
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
    """Prefer commit_ts as run start; fallback to healthy_ts if needed."""
    return parse_ts(r.get("commit_ts")) or parse_ts(r.get("healthy_ts"))


def row_ts_end(r: Dict) -> Optional[dt.datetime]:
    """Prefer healthy_ts as run end; fallback to commit_ts."""
    return parse_ts(r.get("healthy_ts")) or parse_ts(r.get("commit_ts"))


def duration_days(start: Optional[dt.datetime], end: Optional[dt.datetime]) -> float:
    """Return duration in days between start and end, or 0.0 if invalid."""
    if not start or not end:
        return 0.0
    return max((end - start).total_seconds() / 86400.0, 0.0)


# ---------------------------------------------------------------------------
# Merge helpers (artifact history + local CSV)
# ---------------------------------------------------------------------------

def merge_history(
    infile: Path,
    merge_glob: Optional[str],
    merged_out: Optional[Path],
) -> Path:
    """
    Merge:
      - any CSV files matching merge_glob (e.g. artifacts restore),
      - and the local infile (if it exists),
    into a single CSV with unique run_id rows.

    The merged CSV is written to merged_out (if provided) else infile.
    Returns the path of the merged CSV to be used for snapshot.
    """
    dest = merged_out or infile
    rows_by_run: Dict[str, Dict] = {}
    sources = []

    # 1) Merge from restored artifact CSVs
    if merge_glob:
        for f in glob.glob(merge_glob, recursive=True):
            try:
                with open(f, newline="") as fp:
                    reader = csv.DictReader(fp)
                    for r in reader:
                        rid = r.get("run_id")
                        if not rid:
                            continue
                        # Artifact row for this run_id
                        rows_by_run[rid] = r
                sources.append(f)
            except Exception as e:
                print(f"[metrics_snapshot] Warning: failed to read {f}: {e}", file=sys.stderr)

    # 2) Merge local infile (current run) – overwrite artifacts for same run_id
    if infile.exists():
        try:
            with infile.open(newline="") as fp:
                reader = csv.DictReader(fp)
                for r in reader:
                    rid = r.get("run_id")
                    if not rid:
                        continue
                    # Local entry wins over artifact for same run_id
                    rows_by_run[rid] = r
            sources.append(str(infile))
        except Exception as e:
            print(f"[metrics_snapshot] Warning: failed to read {infile}: {e}", file=sys.stderr)

    # 3) Write merged ledger (if any rows collected)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows_by_run.values())
    if not rows:
        # Nothing to merge; ensure file exists but is empty with header
        with dest.open("w", newline="") as fp:
            writer = csv.DictWriter(fp, fieldnames=FIELDS)
            writer.writeheader()
        print("[metrics_snapshot] Merge completed: 0 rows (no sources found).")
        return dest

    # Normalize each row to expected FIELDS
    normalized_rows = []
    for r in rows:
        nr = {k: r.get(k, "") for k in FIELDS}
        normalized_rows.append(nr)

    with dest.open("w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(normalized_rows)

    print(
        f"[metrics_snapshot] Merge completed: {len(normalized_rows)} unique runs "
        f"from {len(sources)} CSV sources → {dest}"
    )
    return dest


# ---------------------------------------------------------------------------
# Aggregation (CFR/DF)
# ---------------------------------------------------------------------------

def aggregate(rows: List[Dict], min_days: float) -> Dict:
    """
    Compute totals, CFR (%), DF/day, and time bounds for the given rows.
    min_days: minimal normalization window for DF/day (e.g. 1.0).
    """
    tot = len(rows)
    succ = sum(1 for r in rows if (r.get("status", "").lower() == "success"))
    fail = tot - succ
    cfr = (fail / tot) * 100.0 if tot else 0.0

    starts = [row_ts_start(r) for r in rows if row_ts_start(r)]
    ends = [row_ts_end(r) for r in rows if row_ts_end(r)]
    if starts and ends:
        start = min(starts)
        end = max(ends)
        days_actual = duration_days(start, end)
    else:
        start = end = None
        days_actual = 0.0

    # Effective window for DF/day normalization (avoid exploding DF for tiny windows)
    if days_actual > 0.0 and min_days > 0.0:
        norm_days = max(days_actual, min_days)
    else:
        norm_days = days_actual

    df_per_day = (succ / norm_days) if norm_days > 0.0 else 0.0

    return {
        "total_runs": tot,
        "success": succ,
        "fail": fail,
        "cfr": round(cfr, 2),
        "df_per_day": round(df_per_day, 2),
        "start": start.isoformat() + "Z" if start else None,
        "end": end.isoformat() + "Z" if end else None,
        "days": round(days_actual, 2),  # actual elapsed time, not the normalized window
    }


def build_snapshot(
    rows: List[Dict],
    group_by: str,
    scenario_default: str,
    min_days: float,
) -> Dict:
    """Build the final snapshot dict with lifetime + optional per-scenario rollups."""
    # Lifetime over all history
    lifetime = aggregate(rows, min_days=min_days)

    snap: Dict[str, object] = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "lifetime": lifetime,
    }

    if group_by == "scenario":
        by_scn: Dict[str, List[Dict]] = collections.defaultdict(list)
        for r in rows:
            scn = r.get("scenario_id") or scenario_default
            by_scn[scn].append(r)

        per_scenario: Dict[str, Dict] = {}
        for scn, rs in by_scn.items():
            per_scenario[scn] = aggregate(rs, min_days=min_days)

        snap["per_scenario"] = per_scenario

    return snap


# ---------------------------------------------------------------------------
# Optional upload: send all runs to HTTP ingest (e.g. BigQuery CF)
# ---------------------------------------------------------------------------

def get_id_token_for_audience(audience: str) -> Optional[str]:
    """
    Use gcloud to mint an ID token for the given audience.
    Assumes the GitHub Actions job has already authenticated via
    google-github-actions/auth and setup-gcloud.
    """
    try:
        token = subprocess.check_output(
            [
                "gcloud",
                "auth",
                "print-identity-token",
                f"--audiences={audience}",
                "--format=get(token)",
            ],
            text=True,
        ).strip()
        if not token:
            print("[metrics_snapshot] Warning: gcloud returned an empty ID token.", file=sys.stderr)
            return None
        return token
    except Exception as e:
        print(f"[metrics_snapshot] Warning: failed to obtain ID token via gcloud: {e}", file=sys.stderr)
        return None


def upload_rows_to_ingest(
    rows: List[Dict],
    endpoint: str,
    service: str,
    scenario_default: str,
):
    """
    Upload each run as a JSON payload to the given HTTP endpoint.
    This is intended for a Cloud Function that writes into BigQuery.

    NOTE: It is assumed that the ingest layer (CF/BigQuery) handles
    idempotency / MERGE by run_id to avoid duplicates.
    """
    import urllib.request
    import urllib.error
    import time

    if not endpoint:
        print("[metrics_snapshot] upload_to_ingest: no endpoint provided, skipping.")
        return

    if not service:
        print(
            "[metrics_snapshot] upload_to_ingest: --service is required when "
            "--upload-to is used (BigQuery schema requires a service name).",
            file=sys.stderr,
        )
        return

    token = get_id_token_for_audience(endpoint)
    if not token:
        print("[metrics_snapshot] upload_to_ingest: could not get ID token, skipping upload.", file=sys.stderr)
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    now_iso = dt.datetime.utcnow().isoformat() + "Z"
    total = len(rows)
    print(f"[metrics_snapshot] Uploading {total} runs to ingest endpoint: {endpoint}")

    for r in rows:
        rid = r.get("run_id") or "<unknown>"
        commit_sha = r.get("commit_sha") or ""
        scenario_id = r.get("scenario_id") or scenario_default
        branch = r.get("branch") or ""
        env = r.get("env") or ""

        start_ts = row_ts_start(r)
        end_ts = row_ts_end(r)

        # If timestamps are missing, fallback so that BQ REQUIRED fields can be populated.
        if not start_ts and end_ts:
            start_ts = end_ts
        if not end_ts and start_ts:
            end_ts = start_ts

        if start_ts and end_ts:
            dur_sec = (end_ts - start_ts).total_seconds()
        else:
            # Last resort: try ttd_sec, else 0
            try:
                dur_sec = float(r.get("ttd_sec") or 0.0)
            except Exception:
                dur_sec = 0.0

        status = (r.get("status") or "unknown").lower()
        tests_total = 1
        tests_failed = 0 if status == "success" else 1

        payload = {
            "run_id": rid,
            "commit_sha": commit_sha,
            "scenario_id": scenario_id,
            "branch": branch,
            "env": env,
            "service": service,
            "started_at": start_ts.isoformat() + "Z" if start_ts else None,
            "ended_at": end_ts.isoformat() + "Z" if end_ts else None,
            "duration_sec": float(dur_sec),
            "status": status,
            "tests_total": tests_total,
            "tests_failed": tests_failed,
            "inserted_at": now_iso,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if 200 <= resp.status < 300:
                    print(f"[metrics_snapshot] upload ✅ run_id={rid} status={status} ({resp.status})")
                else:
                    print(
                        f"[metrics_snapshot] upload ❌ run_id={rid} HTTP {resp.status}",
                        file=sys.stderr,
                    )
        except urllib.error.HTTPError as e:
            print(
                f"[metrics_snapshot] upload ❌ run_id={rid} HTTPError {e.code}: {e.reason}",
                file=sys.stderr,
            )
        except urllib.error.URLError as e:
            print(
                f"[metrics_snapshot] upload ❌ run_id={rid} URLError: {e.reason}",
                file=sys.stderr,
            )

        # Small delay to avoid hammering the endpoint
        time.sleep(0.2)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    infile = Path(args.infile)

    # 1) Merge history from artifacts + local CSV, if requested
    if args.merge_from:
        merged_path = merge_history(
            infile=infile,
            merge_glob=args.merge_from,
            merged_out=Path(args.merged_out) if args.merged_out else None,
        )
        csv_path = merged_path
    else:
        csv_path = infile

    # 2) If no CSV exists (even after merge) → write empty snapshot and exit
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        empty_snapshot = {
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
        }
        if args.group_by == "scenario":
            empty_snapshot["per_scenario"] = {}
        out_path = Path(args.outfile)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(empty_snapshot, indent=2))
        print(f"[metrics_snapshot] Snapshot written (empty): {out_path}")
        return

    # 3) Load rows from CSV (after merge)
    with csv_path.open(newline="") as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)

    if not rows:
        # CSV exists but has only header
        print(f"[metrics_snapshot] No rows in CSV: {csv_path}, writing empty snapshot.")
        empty_snapshot = {
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
        }
        if args.group_by == "scenario":
            empty_snapshot["per_scenario"] = {}
        out_path = Path(args.outfile)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(empty_snapshot, indent=2))
        print(f"[metrics_snapshot] Snapshot written (empty): {out_path}")
        return

    # 4) Build snapshot (lifetime + per-scenario)
    snap = build_snapshot(
        rows=rows,
        group_by=args.group_by,
        scenario_default=args.scenario_default,
        min_days=args.min_days,
    )

    out_path = Path(args.outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snap, indent=2))
    print(f"[metrics_snapshot] Snapshot written: {out_path}")

    # 5) Optional: upload all runs to HTTP ingest (BigQuery function)
    if args.upload_to:
        upload_rows_to_ingest(
            rows=rows,
            endpoint=args.upload_to,
            service=args.service or "",
            scenario_default=args.scenario_default,
        )


if __name__ == "__main__":
    main()

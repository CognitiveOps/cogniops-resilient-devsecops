"""
collect_metrics.py

Collect a single pipeline run record and append it to a CSV file.

This script is intended to be called from CI/CD pipelines or other automation
to record the outcome of a pipeline stage (commit, stage name, status, start
and end times). It writes a row to a CSV file with fixed columns:

    commit, stage, status, t_start, t_end, duration_sec, ts

Example usage:
    python collect_metrics.py --commit abc123 --stage build --status success \
        --tstart 1690000000.0 --tend 1690000030.5 --outfile baseline/metrics/s1_pipeline_runs.csv

Timestamps (--tstart, --tend) are epoch seconds (floats). The script will
write ISO 8601 formatted UTC datetimes into the CSV.
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

# Ordered CSV columns produced by this script
COLUMNS = ["commit", "stage", "status", "t_start", "t_end", "duration_sec", "ts"]


def write_row_csv(out_file, data_row):
    """
    Append a single row (dictionary) to a CSV file, creating parent directories
    and the file itself if necessary.

    - out_file: path to CSV file (string or Path).
    - data_row: mapping whose keys match the COLUMNS list.

    The function opens the file in append mode and writes a header only when
    creating a new file to keep CSVs consistent.
    """
    out_path = Path(out_file)
    # Ensure parent directory exists (mkdir -p behavior)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Check existence before opening so we know whether to write the header
    exists = out_path.exists()

    # Use newline="" to ensure CSV writer handles newlines correctly across platforms
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            # Write header only when the file is first created
            w.writeheader()
        w.writerow(data_row)


if __name__ == "__main__":
    # Parse command line arguments with helpful descriptions
    p = argparse.ArgumentParser(
        description="Append a pipeline run record to a CSV file."
    )
    p.add_argument("--commit", required=True, help="Commit SHA or identifier")
    p.add_argument("--stage", required=True, help="Pipeline stage name (e.g. build, test)")
    p.add_argument("--status", required=True, help="Status string (e.g. success, failure)")
    p.add_argument(
        "--tstart",
        required=True,
        help="Start time as epoch seconds (float). Example: 1690000000.0",
    )
    p.add_argument(
        "--tend",
        required=True,
        help="End time as epoch seconds (float). Example: 1690000030.5",
    )
    p.add_argument(
        "--outfile",
        default="baseline/metrics/s1_pipeline_runs.csv",
        help="Output CSV file path (default: baseline/metrics/s1_pipeline_runs.csv)",
    )
    args = p.parse_args()

    # Convert timestamp arguments from strings to floats (epoch seconds)
    t_start = float(args.tstart)
    t_end = float(args.tend)

    # Build the row dictionary. Convert epoch seconds to ISO 8601 UTC strings.
    # duration_sec is non-negative and rounded to millisecond precision.
    row = {
        "commit": args.commit,
        "stage": args.stage,
        "status": args.status,
        "t_start": datetime.fromtimestamp(t_start, tz=timezone.utc).isoformat(
            timespec="seconds"
        ),
        "t_end": datetime.fromtimestamp(t_end, tz=timezone.utc).isoformat(
            timespec="seconds"
        ),
        "duration_sec": round(max(0.0, t_end - t_start), 3),
        "ts": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }

    # Append to CSV and print the JSON representation to stdout for callers to consume
    write_row_csv(args.outfile, row)
    print(json.dumps(row))

import argparse, csv, os, time
from datetime import datetime, timezone

# Columns: commit, stage, status, t_start, t_end, duration_sec, ts
COLUMNS = ["commit", "stage", "status", "t_start", "t_end", "duration_sec", "ts"]


def write_row(outfile, data_row):
    """
    Appends a row of data to a CSV file, creating the header if the file does not exist.

    Args:
        outfile (str): Path to the output CSV file.
        data_row (dict): Dictionary containing the row data to write.

    Notes:
        - Uses the global COLUMNS variable for CSV fieldnames.
        - Appends to the file if it exists; otherwise, creates a new file with headers.
    """
    exists = os.path.exists(outfile)
    with open(outfile, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            w.writeheader()
        w.writerow(data_row)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True, help="s1 or s2 etc.")
    p.add_argument(
        "--status",
        required=True,
        choices=["success", "failed", "fail_detected", "recovered"],
    )
    p.add_argument("--commit", required=False, default=os.getenv("GITHUB_SHA", "local"))
    p.add_argument("--start", required=False, help="epoch seconds")
    p.add_argument("--outfile", required=True)
    args = p.parse_args()

    t_end = time.time()
    t_start = float(args.start) if args.start else (t_end - 1.0)
    row = {
        "commit": args.commit,
        "stage": args.stage,
        "status": args.status,
        "t_start": datetime.fromtimestamp(t_start, timezone.utc).isoformat().replace("+00:00", "Z"),
        "t_end": datetime.fromtimestamp(t_end, timezone.utc).isoformat().replace("+00:00", "Z"),
        "duration_sec": round(t_end - t_start, 3),
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    os.makedirs(os.path.dirname(args.outfile), exist_ok=True)
    write_row(args.outfile, row)
    print(row)

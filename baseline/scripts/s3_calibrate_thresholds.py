"""
Simple calibration against a healthy edge service to set detection thresholds dynamically.
Calls /status multiple times, measures latency and parses fps/detection_rate,
then emits recommended thresholds via stdout so the workflow can capture them.
Intended to run in GitHub Actions before S3 fault injection.
"""

import json
import os
import sys
import time
import urllib.request
from statistics import quantiles


def fetch_status(url: str, timeout: float = 2.0) -> tuple[float, dict]:
    start = time.time()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read()
    latency = time.time() - start
    data = json.loads(body)
    return latency, data


def percentile(values, p):
    if not values:
        return None
    # statistics.quantiles uses inclusive on n<100 with nprob
    q = quantiles(values, n=100, method="inclusive")
    idx = min(len(q) - 1, max(0, p - 1))
    return q[idx]


def main():
    url = os.environ.get("SERVICE_URL")
    samples = int(os.environ.get("CALIBRATION_SAMPLES", "30"))
    if not url:
        print("SERVICE_URL is required", file=sys.stderr)
        return 1

    latencies = []
    fps_vals = []
    dr_vals = []

    for _ in range(samples):
        try:
            lat, data = fetch_status(url)
            latencies.append(lat)
            fps_vals.append(float(data.get("fps", 0)))
            dr_vals.append(float(data.get("detection_rate", 0)))
        except Exception:
            # if health fails during calibration, skip sample
            continue
        time.sleep(0.1)

    p95_lat = percentile(latencies, 95) or 1.0
    p5_fps = percentile(fps_vals, 5) or 10.0
    p5_dr = percentile(dr_vals, 5) or 0.01

    # Recommend conservative thresholds based on baseline noise
    latency_budget = round(p95_lat * 3, 2)  # allow bursts above baseline jitter
    fps_min = round(p5_fps * 0.7, 2)        # allow 30% drop before trigger
    detection_rate_min = round(p5_dr * 0.5, 4)  # allow 50% drop before trigger

    print(f"latency_budget_sec={latency_budget}")
    print(f"fps_min={fps_min}")
    print(f"detection_rate_min={detection_rate_min}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

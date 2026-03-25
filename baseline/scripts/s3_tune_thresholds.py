"""
Lightweight threshold tuner for S3 detection.

Given two samples of /status metrics (healthy and faulted), it grid-searches
latency/FPS/detection_rate multipliers to maximize recall on the fault set
while keeping false positives on the healthy set below a small target.

Input format: newline-delimited JSON objects with keys:
  - latency: float (seconds)
  - fps: float
  - detection_rate: float

Usage:
  python s3_tune_thresholds.py --healthy healthy.jsonl --fault fault.jsonl

Outputs recommended thresholds to stdout as "latency_budget_sec=..., fps_min=..., detection_rate_min=..."
"""

import argparse
import json
import sys
from typing import List, Tuple


def load_samples(path: str) -> List[dict]:
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return samples


def evaluate(
    healthy: List[dict],
    fault: List[dict],
    lat_multiplier: float,
    fps_factor: float,
    dr_factor: float,
) -> Tuple[float, float]:
    """Return (false_positive_rate, recall) for a given set of multipliers."""
    if not healthy or not fault:
        return 1.0, 0.0

    # Compute thresholds from healthy baselines
    latencies = [s.get("latency", 0.0) for s in healthy]
    fps = [s.get("fps", 0.0) for s in healthy]
    dr = [s.get("detection_rate", 0.0) for s in healthy]

    # Use percentiles via sorted lists
    def percentile(vals, p):
        vals = sorted(vals)
        if not vals:
            return 0.0
        k = int(round((p / 100.0) * (len(vals) - 1)))
        return vals[k]

    lat_p95 = percentile(latencies, 95)
    fps_p5 = percentile(fps, 5)
    dr_p5 = percentile(dr, 5)

    latency_budget = lat_p95 * lat_multiplier
    fps_min = fps_p5 * fps_factor
    dr_min = dr_p5 * dr_factor

    def triggered(sample):
        if sample.get("latency", 0.0) > latency_budget:
            return True
        if sample.get("fps", 0.0) < fps_min:
            return True
        if sample.get("detection_rate", 1.0) <= dr_min:
            return True
        return False

    fp = sum(1 for s in healthy if triggered(s))
    fn = sum(1 for s in fault if not triggered(s))
    fp_rate = fp / len(healthy)
    recall = 1.0 - (fn / len(fault))
    return fp_rate, recall


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--healthy", required=True, help="JSONL file with healthy /status samples")
    parser.add_argument("--fault", required=True, help="JSONL file with faulted /status samples")
    parser.add_argument("--fp_target", type=float, default=0.05, help="max false positive rate")
    args = parser.parse_args()

    healthy = load_samples(args.healthy)
    fault = load_samples(args.fault)

    lat_multipliers = [2.0, 2.5, 3.0, 3.5]
    fps_factors = [0.5, 0.6, 0.7, 0.8]
    dr_factors = [0.3, 0.4, 0.5, 0.6]

    best = None
    for lm in lat_multipliers:
        for ff in fps_factors:
            for df in dr_factors:
                fp_rate, recall = evaluate(healthy, fault, lm, ff, df)
                if fp_rate > args.fp_target:
                    continue
                score = recall  # prioritize recall under FP constraint
                if best is None or score > best["score"]:
                    best = {
                        "latency_multiplier": lm,
                        "fps_factor": ff,
                        "dr_factor": df,
                        "fp_rate": fp_rate,
                        "recall": recall,
                    }

    if not best:
        print("No combination met the FP target; consider relaxing fp_target or providing more samples.", file=sys.stderr)
        return 1

    print(
        f"latency_multiplier={best['latency_multiplier']}, "
        f"fps_factor={best['fps_factor']}, "
        f"detection_rate_factor={best['dr_factor']}"
    )
    print(f"fp_rate={best['fp_rate']:.3f}, recall={best['recall']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Inline fault detection for S3 agent-managed workflows.

Replaces the baseline's simple curl-poll-sleep loop with anomaly scoring
that detects degradation trends BEFORE full failure, reducing MTTD.

Key differences from baseline detection:
- 1s polling (vs 5s baseline) — faster observation cycle
- Continuous anomaly score (0-1) instead of binary pass/fail
- Trend detection: rising latency across 3+ samples → early warning
- Multi-signal fusion: HTTP, latency, fps, detection_rate combined

Deterministic — no LLM. Runs as CLI in GitHub Actions step.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error


def _fetch_status(service_url: str) -> tuple[int, float, dict]:
    """Fetch /status and return (http_code, latency_sec, body_dict).

    Uses stdlib urllib — no subprocess spawn overhead.
    """
    url = f"{service_url}/status"
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            latency = time.monotonic() - t0
            body_bytes = resp.read()
            http_code = resp.status
        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            body = {}
        return http_code, latency, body
    except urllib.error.HTTPError as e:
        latency = time.monotonic() - t0
        return e.code, latency, {}
    except Exception:
        latency = time.monotonic() - t0
        return 0, latency, {}


def _compute_anomaly_score(
    http_code: int,
    latency: float,
    body: dict,
    latency_budget: float,
    fps_min: float,
    detection_rate_min: float,
    history: list[dict],
) -> float:
    """Compute 0-1 anomaly score from current observation + recent history."""
    # Hard failure: non-200
    if http_code != 200:
        return 1.0

    score = 0.0

    # Latency anomaly
    if latency_budget > 0 and latency > latency_budget:
        score += 0.4

    # Metric anomalies from /status body
    fps = body.get("fps", 999)
    detection_rate = body.get("detection_rate", 1.0)
    healthy = body.get("healthy", True)

    if not healthy:
        score += 0.5
    if fps < fps_min:
        score += 0.3
    if detection_rate < detection_rate_min:
        score += 0.3

    # Trend detection: last 3 observations
    if len(history) >= 3:
        recent_latencies = [h["latency"] for h in history[-3:]]
        recent_codes = [h["http_code"] for h in history[-3:]]

        # Rising latency trend
        if all(
            recent_latencies[i] < recent_latencies[i + 1]
            for i in range(len(recent_latencies) - 1)
        ):
            score += 0.2

        # Any intermittent non-200 in window
        if any(c != 200 for c in recent_codes):
            score += 0.3

    return min(score, 1.0)


def detect(
    service_url: str,
    poll_interval: float = 1.0,
    anomaly_threshold: float = 0.7,
    timeout_sec: int = 300,
    latency_budget: float = 2.0,
    fps_min: float = 10.0,
    detection_rate_min: float = 0.01,
) -> dict:
    """Poll service and detect anomalies.

    Returns dict with detected, t_detect, ttd_sample, anomaly_score,
    detection_method, detect_metrics_raw.
    """
    t_start = time.time()
    deadline = t_start + timeout_sec
    history: list[dict] = []

    while time.time() < deadline:
        now = time.time()
        http_code, latency, body = _fetch_status(service_url)

        observation = {
            "ts": now,
            "http_code": http_code,
            "latency": latency,
            "body": body,
        }
        history.append(observation)

        score = _compute_anomaly_score(
            http_code, latency, body,
            latency_budget, fps_min, detection_rate_min,
            history,
        )

        print(f"[{int(now)}] /status -> {http_code} ({latency:.2f}s) score={score:.2f}")

        if score >= anomaly_threshold:
            t_detect = now
            ttd = t_detect - t_start
            method = "anomaly_score" if http_code == 200 else "http_failure"
            print(
                f"Anomaly detected at {int(t_detect)} "
                f"(score={score:.2f}, method={method})"
            )
            return {
                "detected": True,
                "t_detect": int(t_detect),
                "ttd_sample": int(ttd),
                "anomaly_score": round(score, 3),
                "detection_method": method,
                "detect_metrics_raw": json.dumps(body),
            }

        time.sleep(poll_interval)

    return {
        "detected": False,
        "t_detect": int(time.time()),
        "ttd_sample": timeout_sec,
        "anomaly_score": 0.0,
        "detection_method": "timeout",
        "detect_metrics_raw": "{}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inline S3 fault detection")
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--anomaly-threshold", type=float, default=0.7)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--latency-budget", type=float, default=2.0)
    parser.add_argument("--fps-min", type=float, default=10.0)
    parser.add_argument("--detection-rate-min", type=float, default=0.01)
    args = parser.parse_args()

    result = detect(
        service_url=args.service_url,
        poll_interval=args.poll_interval,
        anomaly_threshold=args.anomaly_threshold,
        timeout_sec=args.timeout,
        latency_budget=args.latency_budget,
        fps_min=args.fps_min,
        detection_rate_min=args.detection_rate_min,
    )

    # Write outputs for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            for k, v in result.items():
                f.write(f"{k}={v}\n")
    else:
        print(json.dumps(result, indent=2))

    if not result["detected"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Inline sensor for S3/SS2 agent-managed workflows.

Polls service /status, collects raw metrics, and uses the agent's
own scoring model (perception/scoring.py) to detect anomalies.

The scoring logic is defined ONCE in the agent's perception module
and imported here. This means:
  - The agent's cognitive model drives detection (not a separate heuristic)
  - The same model runs on Cloud Run during /decide assessment
  - Causal attribution: ALL cognitive work belongs to the agent

Architecture:
  detect.py imports agent scoring → polls → scores locally → triggers
  → sends raw_metrics to agent /decide → agent confirms + responds

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

# Import agent's scoring model (zero-dep module, works in any Python 3.10+)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from perception.scoring import ANOMALY_THRESHOLD, score_raw_metrics


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


def detect(
    service_url: str,
    poll_interval: float = 1.0,
    anomaly_threshold: float = ANOMALY_THRESHOLD,
    timeout_sec: int = 300,
    latency_budget: float = 2.0,
    fps_min: float = 10.0,
    detection_rate_min: float = 0.01,
) -> dict:
    """Poll service and detect anomalies using the agent's scoring model.

    Uses score_raw_metrics() from the agent's perception module —
    the same model that runs on Cloud Run during /decide.

    Returns dict with detected flag, timing info, anomaly_score,
    and raw_metrics for the agent to re-assess during /decide.
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
            "latency_ms": round(latency * 1000, 1),
            "fps": body.get("fps"),
            "detection_rate": body.get("detection_rate"),
            "healthy": body.get("healthy"),
        }
        history.append(observation)

        # Build raw_metrics for agent's scoring model
        recent = history[-5:] if len(history) >= 5 else history
        raw_metrics = {
            "current": observation,
            "recent_history": recent,
            "latency_budget_sec": latency_budget,
            "fps_min": fps_min,
            "detection_rate_min": detection_rate_min,
        }

        # Score using agent's model (same code as Cloud Run perception)
        score = score_raw_metrics(raw_metrics)

        print(f"[{int(now)}] /status -> {http_code} ({latency:.2f}s) score={score:.2f}")

        if score >= anomaly_threshold:
            t_detect = now
            ttd = t_detect - t_start
            raw_metrics["trigger"] = "anomaly_score"
            print(
                f"Anomaly detected at {int(t_detect)} "
                f"(score={score:.2f} >= {anomaly_threshold})"
            )
            return {
                "detected": True,
                "t_detect": int(t_detect),
                "ttd_sample": int(ttd),
                "anomaly_score": round(score, 3),
                "raw_metrics": json.dumps(raw_metrics),
            }

        time.sleep(poll_interval)

    return {
        "detected": False,
        "t_detect": int(time.time()),
        "ttd_sample": timeout_sec,
        "anomaly_score": 0.0,
        "raw_metrics": json.dumps({"trigger": "timeout", "history_len": len(history)}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inline sensor (agent scoring model)")
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--anomaly-threshold", type=float, default=ANOMALY_THRESHOLD)
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

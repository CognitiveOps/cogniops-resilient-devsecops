"""
Inline metric collector for S3/SS2 agent-managed workflows.

Pure sensor: polls service /status, collects raw metrics, and stops
when a basic degradation signal is observed (HTTP non-200 or healthy=false).

NO anomaly scoring — that is the agent's job (perception module).
The agent receives raw metrics and interprets them cognitively.

Architecture:
  detect.py (sensor, local)  →  raw metrics  →  agent /decide (Cloud Run)
  collect & trigger               transport        interpret & decide

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


def _is_degraded(http_code: int, body: dict) -> bool:
    """Simple binary check: is the service showing ANY sign of degradation?

    This is intentionally simple — the agent does the real analysis.
    We just need to know when to stop polling and ship metrics.
    """
    if http_code != 200:
        return True
    if not body.get("healthy", True):
        return True
    return False


def detect(
    service_url: str,
    poll_interval: float = 1.0,
    timeout_sec: int = 300,
    latency_budget: float = 2.0,
    fps_min: float = 10.0,
    detection_rate_min: float = 0.01,
) -> dict:
    """Poll service and collect raw metrics until degradation.

    Returns dict with detected flag, timing info, and raw_metrics
    (the actual sensor readings for the agent to interpret).
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

        degraded = _is_degraded(http_code, body)

        print(f"[{int(now)}] /status -> {http_code} ({latency:.2f}s) degraded={degraded}")

        if degraded:
            t_detect = now
            ttd = t_detect - t_start
            # Collect the last few observations as raw metrics for the agent
            recent = history[-5:] if len(history) >= 5 else history
            raw_metrics = {
                "trigger": "http_failure" if http_code != 200 else "health_false",
                "current": observation,
                "recent_history": recent,
                "latency_budget_sec": latency_budget,
                "fps_min": fps_min,
                "detection_rate_min": detection_rate_min,
            }
            print(
                f"Degradation detected at {int(t_detect)} "
                f"(trigger={raw_metrics['trigger']})"
            )
            return {
                "detected": True,
                "t_detect": int(t_detect),
                "ttd_sample": int(ttd),
                "raw_metrics": json.dumps(raw_metrics),
            }

        time.sleep(poll_interval)

    return {
        "detected": False,
        "t_detect": int(time.time()),
        "ttd_sample": timeout_sec,
        "raw_metrics": json.dumps({"trigger": "timeout", "history_len": len(history)}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inline metric collector")
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--latency-budget", type=float, default=2.0)
    parser.add_argument("--fps-min", type=float, default=10.0)
    parser.add_argument("--detection-rate-min", type=float, default=0.01)
    args = parser.parse_args()

    result = detect(
        service_url=args.service_url,
        poll_interval=args.poll_interval,
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

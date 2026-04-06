"""
Agent anomaly scoring model — shared between sensor and agent.

Pure Python, zero external dependencies. This module defines the
agent's cognitive model for interpreting raw sensor metrics.

Used by:
  - detect.py (locally on GitHub Actions runner, for real-time detection)
  - perception/handler.py (on Cloud Run, during /decide processing)

The scoring logic is defined ONCE here. Both sensor and agent
use the same model — the sensor just runs it locally for speed.
"""
from __future__ import annotations

# Default anomaly threshold — score above this triggers detection
ANOMALY_THRESHOLD: float = 0.7


def score_raw_metrics(raw_metrics: dict) -> float:
    """Compute anomaly score from raw sensor metrics.

    Multi-signal fusion: HTTP code, latency, fps, detection_rate,
    health status, plus trend detection across recent history.

    Args:
        raw_metrics: Dict with 'current' (observation), 'recent_history'
                     (list of observations), and budget parameters.

    Returns: float 0.0-1.0 anomaly score.
    """
    current = raw_metrics.get("current", {})
    history = raw_metrics.get("recent_history", [])
    latency_budget_sec = raw_metrics.get("latency_budget_sec", 2.0)
    fps_min = raw_metrics.get("fps_min", 10.0)
    detection_rate_min = raw_metrics.get("detection_rate_min", 0.01)

    http_code = current.get("http_code", 200)

    # Hard failure: non-200
    if http_code != 200:
        return 1.0

    score = 0.0

    # ── Primary signals (any one sufficient to exceed threshold) ──

    latency_ms = current.get("latency_ms", 0)
    latency_sec = latency_ms / 1000.0 if latency_ms else 0
    if latency_budget_sec > 0 and latency_sec > latency_budget_sec:
        score += 0.8

    fps = current.get("fps")
    if fps is not None and fps < fps_min:
        score += 0.8

    detection_rate = current.get("detection_rate")
    if detection_rate is not None and detection_rate < detection_rate_min:
        score += 0.8

    healthy = current.get("healthy")
    if healthy is not None and not healthy:
        score += 0.9

    # ── Trend signals (early warning, additive) ──
    if len(history) >= 3:
        recent_latencies = [h.get("latency_ms", 0) for h in history[-3:]]
        recent_codes = [h.get("http_code", 200) for h in history[-3:]]

        # Rising latency trend across 3 consecutive samples
        if all(
            recent_latencies[i] < recent_latencies[i + 1]
            for i in range(len(recent_latencies) - 1)
        ):
            score += 0.4

        # Any intermittent non-200 in recent window
        if any(c != 200 for c in recent_codes):
            score += 0.4

    return min(score, 1.0)

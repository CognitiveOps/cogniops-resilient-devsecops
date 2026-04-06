"""
Perception module – interprets raw sensor data and extracts severity.

Performs multi-signal anomaly scoring when raw_metrics are present
(from detect.py metric collector), or falls back to event-level
severity labels. This is where the cognitive analysis happens —
the sensor only collects, the agent interprets.
"""

from __future__ import annotations

import json
import logging

from models.schemas import AnomalyOutput, RuntimeEvent

logger = logging.getLogger("runtime-agent.perception")

# ── Severity mapping from string labels ──────────────────────────────

_SEVERITY_MAP: dict[str, float] = {
    "critical": 0.9,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.3,
    "none": 0.1,
}


def _score_raw_metrics(raw_metrics: dict) -> float:
    """Compute anomaly score from raw sensor metrics.

    This is the cognitive interpretation that was previously in detect.py.
    Multi-signal fusion: HTTP, latency, fps, detection_rate, health,
    plus trend detection across recent history.

    Returns: float 0-1 anomaly score.
    """
    current = raw_metrics.get("current", {})
    history = raw_metrics.get("recent_history", [])
    budgets = {
        "latency_budget_sec": raw_metrics.get("latency_budget_sec", 2.0),
        "fps_min": raw_metrics.get("fps_min", 10.0),
        "detection_rate_min": raw_metrics.get("detection_rate_min", 0.01),
    }

    http_code = current.get("http_code", 200)

    # Hard failure: non-200
    if http_code != 200:
        return 1.0

    score = 0.0

    # ── Primary signals (any one sufficient to trigger high severity) ──

    latency_ms = current.get("latency_ms", 0)
    latency_sec = latency_ms / 1000.0 if latency_ms else 0
    if budgets["latency_budget_sec"] > 0 and latency_sec > budgets["latency_budget_sec"]:
        score += 0.8

    fps = current.get("fps")
    if fps is not None and fps < budgets["fps_min"]:
        score += 0.8

    detection_rate = current.get("detection_rate")
    if detection_rate is not None and detection_rate < budgets["detection_rate_min"]:
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


def _extract_severity(event: RuntimeEvent) -> float:
    """Extract numeric severity from event context.

    Priority:
      1. context.raw_metrics (JSON — multi-signal anomaly scoring by agent)
      2. context.anomaly_score (float 0-1, pre-computed)
      3. context.severity (string label → mapped to float)
      4. Default: 0.5 (neutral)
    """
    ctx = event.context
    extra = ctx.__pydantic_extra__ or {} if hasattr(ctx, "__pydantic_extra__") else {}

    # 1. Raw metrics from sensor → agent computes anomaly score
    raw_metrics_str = extra.get("raw_metrics")
    if raw_metrics_str is not None:
        try:
            if isinstance(raw_metrics_str, str):
                raw_metrics = json.loads(raw_metrics_str)
            else:
                raw_metrics = raw_metrics_str
            score = _score_raw_metrics(raw_metrics)
            logger.info("Scored raw_metrics → anomaly_score=%.3f", score)
            return score
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse raw_metrics: %s", exc)

    # 2. Direct anomaly_score (pre-computed, backwards compat)
    anomaly_score = extra.get("anomaly_score")
    if anomaly_score is not None:
        try:
            score = float(anomaly_score)
            if 0.0 <= score <= 1.0:
                return score
        except (ValueError, TypeError):
            pass

    # 2. String severity label
    if ctx.severity:
        mapped = _SEVERITY_MAP.get(ctx.severity.lower())
        if mapped is not None:
            return mapped

    # 3. Default neutral
    return 0.5


def _compute_risk_score(severity: float, event: RuntimeEvent) -> float:
    """Compute risk score from severity and context signals.

    Uses a weighted approach:
      - Base: severity * 0.7
      - Status modifier: failure/deny adds 0.15, success subtracts 0.2
    """
    ctx = event.context
    base = severity * 0.7

    status = (ctx.status or "").lower()
    if status in ("failure", "deny", "blocked"):
        modifier = 0.15
    elif status == "success":
        modifier = -0.2
    else:
        modifier = 0.0

    return max(0.0, min(1.0, base + modifier))


def perceive(event: RuntimeEvent) -> AnomalyOutput:
    """Extract event fields and produce a scored anomaly object.

    Uses real severity from event context when available
    (anomaly_score, severity label), with neutral fallback.
    """
    scenario = event.context.scenario_id or "unknown"
    anomaly_type = event.event_type

    severity = _extract_severity(event)
    risk_score = _compute_risk_score(severity, event)

    anomaly = AnomalyOutput(
        scenario=scenario,
        anomaly_type=anomaly_type,
        severity=severity,
        risk_score=risk_score,
        source_event_id=event.event_id,
    )

    logger.info(
        "Scoring: scenario=%s severity=%.3f risk_score=%.3f (checks=%d, weight=0.7)",
        scenario, severity, risk_score, 0,
    )
    logger.info(
        "Perception: event_id=%s → severity=%.3f risk=%.3f (baseline=available)",
        event.event_id, severity, risk_score,
    )
    return anomaly

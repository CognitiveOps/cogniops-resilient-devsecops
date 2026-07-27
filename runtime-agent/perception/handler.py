"""
Perception module – interprets raw sensor data and extracts severity.

Performs multi-signal anomaly scoring when raw_metrics are present
(from detect.py sensor), or falls back to event-level severity labels.

The scoring model (score_raw_metrics) is defined in scoring.py and
shared with detect.py — ensuring the same cognitive model drives
both real-time detection and post-detection assessment.
"""

from __future__ import annotations

import json
import logging

from models.schemas import AnomalyOutput, RuntimeEvent
from perception.scoring import score_raw_metrics

logger = logging.getLogger("runtime-agent.perception")

# ── Severity mapping from string labels ──────────────────────────────

_SEVERITY_MAP: dict[str, float] = {
    "critical": 0.9,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.3,
    "none": 0.1,
}


def _extract_severity(event: RuntimeEvent) -> float:
    """Extract numeric severity from event context.

    Priority:
      1. context.raw_metrics (JSON — agent's scoring model)
      2. context.anomaly_score (float 0-1, pre-computed)
      3. context.severity (string label → mapped to float)
      4. Default: 0.5 (neutral)
    """
    ctx = event.context
    extra = ctx.__pydantic_extra__ or {} if hasattr(ctx, "__pydantic_extra__") else {}

    # 1. Raw metrics from sensor → score with agent's model
    raw_metrics_str = extra.get("raw_metrics")
    if raw_metrics_str is not None:
        try:
            if isinstance(raw_metrics_str, str):
                raw_metrics = json.loads(raw_metrics_str)
            else:
                raw_metrics = raw_metrics_str
            score = score_raw_metrics(raw_metrics)
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

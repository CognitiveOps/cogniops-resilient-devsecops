"""ADK tool wrapping the Perception module for anomaly detection.

Step 2: real z-score + threshold scoring against BQ baselines.
DETERMINISTIC — no LLM, no randomness.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from agent.tools.anomaly_detection import compute_severity
from agent.tools.baseline_reader import query_baseline
from models.schemas import AnomalyOutput, EventContext, RuntimeEvent

logger = logging.getLogger("runtime-agent.perception")


def perceive_anomaly(
    event_id: str,
    event_type: str,
    source: str,
    occurred_at: str,
    scenario_id: str = "unknown",
    status: str = "unknown",
    duration_sec: Optional[float] = None,
    metrics_json: Optional[str] = None,
) -> dict:
    """Analyze a runtime event and detect anomalies against baseline metrics.

    Call this FIRST before deciding on an action. Uses z-score analysis
    against 7-day BQ baselines combined with per-scenario threshold checks.

    Args:
        event_id: Unique event identifier (UUID).
        event_type: Type of event (pipeline_failure, policy_violation, etc.).
        source: Event publisher identity.
        occurred_at: RFC 3339 timestamp of when the event occurred.
        scenario_id: Scenario identifier (S1-S5, SS1-SS2).
        status: Event status (fail, degraded, etc.).
        duration_sec: Duration of the pipeline/stage in seconds (if available).
        metrics_json: JSON string of scenario-specific metrics
            (e.g. '{"mttd_sec": 95, "mttr_sec": 250}').

    Returns:
        dict with severity (0-1), risk_score (0-1), anomaly_type, and scenario.
    """
    # Parse metrics from JSON string if provided
    event_metrics: Optional[dict[str, float]] = None
    if metrics_json:
        import json

        try:
            raw = json.loads(metrics_json)
            event_metrics = {k: float(v) for k, v in raw.items() if v is not None}
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Invalid metrics_json for event %s, ignoring", event_id)

    # Query BQ baseline (graceful degradation — returns None on failure)
    baseline = query_baseline(scenario_id) if scenario_id != "unknown" else None

    # Compute severity + risk_score
    severity, risk_score = compute_severity(
        scenario_id=scenario_id,
        duration_sec=duration_sec,
        event_metrics=event_metrics,
        baseline=baseline,
    )

    anomaly = AnomalyOutput(
        scenario=scenario_id,
        anomaly_type=event_type,
        severity=severity,
        risk_score=risk_score,
        source_event_id=event_id,
    )

    logger.info(
        "Perception: event_id=%s → severity=%.3f risk=%.3f (baseline=%s)",
        event_id,
        severity,
        risk_score,
        "available" if baseline else "unavailable",
    )

    return anomaly.model_dump()

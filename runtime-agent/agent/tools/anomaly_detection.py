"""
Anomaly detection — z-score + threshold scoring for runtime events.

DETERMINISTIC — no LLM, no randomness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("runtime-agent.perception")


# ── Per-scenario threshold configuration ─────────────────────────────


@dataclass(frozen=True)
class ThresholdRule:
    """A directional threshold: 'above' means high values are bad, 'below' means low values are bad."""

    metric: str
    warning: float
    critical: float
    direction: str = "above"  # "above" = exceeding is bad, "below" = falling is bad


SCENARIO_THRESHOLDS: dict[str, list[ThresholdRule]] = {
    "S1": [
        ThresholdRule(
            metric="ttd_sec", warning=180.0, critical=300.0, direction="above"
        ),
        ThresholdRule(metric="cfr", warning=0.10, critical=0.25, direction="above"),
    ],
    "S2": [
        ThresholdRule(metric="dsr", warning=0.95, critical=0.85, direction="below"),
    ],
    "S3": [
        ThresholdRule(
            metric="mttd_sec", warning=60.0, critical=120.0, direction="above"
        ),
        ThresholdRule(
            metric="mttr_sec", warning=120.0, critical=300.0, direction="above"
        ),
    ],
    "S4": [
        ThresholdRule(metric="fdr", warning=0.90, critical=0.70, direction="below"),
    ],
}

# Scenario criticality weights for risk_score adjustment
SCENARIO_WEIGHTS: dict[str, float] = {
    "S1": 0.8,
    "S2": 0.9,
    "S3": 1.0,
    "S4": 1.0,
    "S5": 0.6,
    "SS1": 0.7,
    "SS2": 1.0,
}

DEFAULT_WEIGHT = 0.7


# ── Z-score detection ────────────────────────────────────────────────


def z_score_check(value: float, mean: float, stddev: float) -> float:
    """Compute z-score for anomaly detection.

    Returns the absolute z-score (always >= 0). A z-score > 2 is
    typically anomalous; > 3 is highly anomalous.
    """
    if stddev == 0:
        return 0.0
    return abs(value - mean) / stddev


def z_score_to_severity(z: float) -> float:
    """Map z-score to severity (0-1).

    | z-score | severity |
    |---------|----------|
    | < 1.0   | 0.0      |
    | 1.0-2.0 | 0.1-0.4  |
    | 2.0-3.0 | 0.5-0.7  |
    | > 3.0   | 0.8-1.0  |
    """
    if z < 1.0:
        return 0.0
    if z < 2.0:
        return 0.1 + (z - 1.0) * 0.3  # 0.1 → 0.4
    if z < 3.0:
        return 0.5 + (z - 2.0) * 0.2  # 0.5 → 0.7
    return min(0.8 + (z - 3.0) * 0.1, 1.0)  # 0.8 → 1.0


# ── Threshold detection ──────────────────────────────────────────────


def threshold_severity(
    value: float,
    rule: ThresholdRule,
) -> float:
    """Score severity based on a threshold rule.

    Returns 0.0 (normal), 0.5-0.7 (warning), or 0.8-1.0 (critical).
    """
    if rule.direction == "above":
        if value >= rule.critical:
            fraction = min((value - rule.critical) / max(rule.critical, 1.0), 1.0)
            return 0.8 + fraction * 0.2
        if value >= rule.warning:
            fraction = (value - rule.warning) / max(rule.critical - rule.warning, 1.0)
            return 0.5 + fraction * 0.2
        return 0.0
    else:  # "below" — lower values are worse
        if value <= rule.critical:
            fraction = min((rule.critical - value) / max(rule.critical, 0.01), 1.0)
            return 0.8 + fraction * 0.2
        if value <= rule.warning:
            fraction = (rule.warning - value) / max(rule.warning - rule.critical, 0.01)
            return 0.5 + fraction * 0.2
        return 0.0


# ── Baseline data structure ──────────────────────────────────────────


@dataclass
class BaselineStats:
    """Rolling averages from BQ for a scenario."""

    scenario_id: str
    avg_duration: float
    stddev_duration: float
    sample_count: int
    metric_averages: dict[str, float]
    metric_stddevs: dict[str, float]


# ── Combined scoring ─────────────────────────────────────────────────


def compute_severity(
    *,
    scenario_id: str,
    duration_sec: Optional[float] = None,
    event_metrics: Optional[dict[str, float]] = None,
    baseline: Optional[BaselineStats] = None,
) -> tuple[float, float]:
    """Compute (severity, risk_score) for an event.

    Combines z-score analysis (if baseline available) with threshold
    detection. Returns the maximum severity from all checks.

    Graceful degradation: if no baseline → threshold-only detection.
    If no thresholds for scenario → severity 0.5 (neutral).

    Returns:
        (severity, risk_score) each in [0.0, 1.0].
    """
    severities: list[float] = []
    metrics = event_metrics or {}

    # ── Z-score from baseline (if available) ─────────────────────────
    if baseline and baseline.sample_count >= 3:
        # Duration z-score
        if duration_sec is not None and baseline.stddev_duration > 0:
            z = z_score_check(
                duration_sec, baseline.avg_duration, baseline.stddev_duration
            )
            severities.append(z_score_to_severity(z))

        # Per-metric z-scores
        for metric_name, value in metrics.items():
            avg = baseline.metric_averages.get(metric_name)
            std = baseline.metric_stddevs.get(metric_name)
            if avg is not None and std is not None and std > 0:
                z = z_score_check(value, avg, std)
                severities.append(z_score_to_severity(z))

    # ── Threshold detection (always runs) ────────────────────────────
    rules = SCENARIO_THRESHOLDS.get(scenario_id, [])

    # Check duration against TTD threshold (S1-specific)
    if duration_sec is not None:
        for rule in rules:
            if rule.metric == "ttd_sec":
                severities.append(threshold_severity(duration_sec, rule))

    # Check event-specific metrics
    for rule in rules:
        if rule.metric in metrics:
            severities.append(threshold_severity(metrics[rule.metric], rule))

    # ── Combine ──────────────────────────────────────────────────────
    if not severities:
        # No data to score — return neutral
        severity = 0.5
    else:
        severity = max(severities)

    weight = SCENARIO_WEIGHTS.get(scenario_id, DEFAULT_WEIGHT)
    risk_score = round(min(severity * weight, 1.0), 4)
    severity = round(severity, 4)

    logger.info(
        "Scoring: scenario=%s severity=%.3f risk_score=%.3f (checks=%d, weight=%.1f)",
        scenario_id,
        severity,
        risk_score,
        len(severities),
        weight,
    )

    return severity, risk_score

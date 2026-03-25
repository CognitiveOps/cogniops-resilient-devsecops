"""
Perception module – Phase 0 stub.

Receives a validated RuntimeEvent and produces a hardcoded AnomalyOutput.
In Phase 1 this will perform z-score / threshold anomaly detection.
"""

from __future__ import annotations

import logging

from models.schemas import AnomalyOutput, RuntimeEvent

logger = logging.getLogger(__name__)


def perceive(event: RuntimeEvent) -> AnomalyOutput:
    """
    Extract event fields and produce a stub anomaly object.

    Phase 0 defaults (per runtime-event-contract.md):
      - severity: 0.5  (neutral)
      - risk_score: 0.5 (neutral)
      - anomaly_type: copied from event_type
      - scenario: context.scenario_id or "unknown"
    """
    scenario = event.context.scenario_id or "unknown"
    anomaly_type = event.event_type

    anomaly = AnomalyOutput(
        scenario=scenario,
        anomaly_type=anomaly_type,
        severity=0.5,
        risk_score=0.5,
        source_event_id=event.event_id,
    )

    logger.info(
        "Perception: event_id=%s → anomaly scenario=%s type=%s",
        event.event_id,
        anomaly.scenario,
        anomaly.anomaly_type,
    )
    return anomaly

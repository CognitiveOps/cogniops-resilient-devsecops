"""ADK tool wrapping the Perception module for anomaly detection."""

from __future__ import annotations

from datetime import datetime

from models.schemas import EventContext, RuntimeEvent
from perception.handler import perceive


def perceive_anomaly(
    event_id: str,
    event_type: str,
    source: str,
    occurred_at: str,
    scenario_id: str = "unknown",
    status: str = "unknown",
) -> dict:
    """Analyze a runtime event and detect anomalies against baseline metrics.

    Call this FIRST before deciding on an action.

    Args:
        event_id: Unique event identifier (UUID).
        event_type: Type of event (pipeline_failure, policy_violation, etc.).
        source: Event publisher identity.
        occurred_at: RFC 3339 timestamp of when the event occurred.
        scenario_id: Scenario identifier (S1-S5, SS1-SS2).
        status: Event status (fail, degraded, etc.).

    Returns:
        dict with severity (0-1), risk_score (0-1), anomaly_type, and scenario.
    """
    event = RuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        occurred_at=datetime.fromisoformat(occurred_at),
        source=source,
        context=EventContext(
            status=status,
            scenario_id=scenario_id,
        ),
    )
    anomaly = perceive(event)
    return anomaly.model_dump()

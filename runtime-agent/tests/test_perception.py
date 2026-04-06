"""
Unit tests for the Perception module.

Spec: valid event → correct anomaly output
  - scenario from context.scenario_id or "unknown"
  - anomaly_type copied from event_type
  - severity derived from context.severity label
  - risk_score computed from severity + status
  - source_event_id = event.event_id
"""

from __future__ import annotations

from perception.handler import perceive


class TestPerceive:
    """Tests for perceive()."""

    def test_valid_event_produces_anomaly(self, sample_event):
        """Valid event with scenario_id → correct anomaly output."""
        anomaly = perceive(sample_event)

        assert anomaly.scenario == "S3"
        assert anomaly.anomaly_type == "manual_test_event"
        # severity="medium" → 0.5, risk_score = 0.5*0.7 = 0.35
        assert anomaly.severity == 0.5
        assert anomaly.risk_score == 0.35
        assert anomaly.source_event_id == "b3f0a9c1-1234-4567-8901-abcdef123456"

    def test_missing_scenario_defaults_to_unknown(self, sample_event_no_scenario):
        """Event without scenario_id → scenario = 'unknown'."""
        anomaly = perceive(sample_event_no_scenario)

        assert anomaly.scenario == "unknown"
        assert anomaly.anomaly_type == "pipeline_failure"
        assert anomaly.source_event_id == "no-scenario-001"

    def test_severity_from_label(self, sample_event):
        """Severity map: medium → 0.5, risk = severity*0.7."""
        anomaly = perceive(sample_event)
        assert anomaly.severity == 0.5
        assert anomaly.risk_score == 0.35

    def test_high_severity_label(self):
        """severity='high' → 0.75."""
        from models.schemas import EventContext, RuntimeEvent
        from datetime import datetime, timezone

        event = RuntimeEvent(
            event_id="sev-high-001",
            event_type="pipeline_failure",
            occurred_at=datetime.now(timezone.utc),
            source="test",
            context=EventContext(status="failure", severity="high", scenario_id="s1"),
        )
        anomaly = perceive(event)
        assert anomaly.severity == 0.75
        # failure status adds 0.15: 0.75*0.7 + 0.15 = 0.675
        assert abs(anomaly.risk_score - 0.675) < 0.01

    def test_critical_severity_label(self):
        """severity='critical' → 0.9."""
        from models.schemas import EventContext, RuntimeEvent
        from datetime import datetime, timezone

        event = RuntimeEvent(
            event_id="sev-crit-001",
            event_type="policy_violation",
            occurred_at=datetime.now(timezone.utc),
            source="test",
            context=EventContext(status="deny", severity="critical", scenario_id="ss1"),
        )
        anomaly = perceive(event)
        assert anomaly.severity == 0.9

    def test_anomaly_type_matches_event_type(self, sample_event):
        """anomaly_type must be copied from event_type."""
        anomaly = perceive(sample_event)
        assert anomaly.anomaly_type == sample_event.event_type

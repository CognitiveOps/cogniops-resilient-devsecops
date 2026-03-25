"""
Unit tests for the Perception module.

Spec: valid event → correct anomaly output
  - scenario from context.scenario_id or "unknown"
  - anomaly_type copied from event_type
  - severity = 0.5, risk_score = 0.5
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
        assert anomaly.severity == 0.5
        assert anomaly.risk_score == 0.5
        assert anomaly.source_event_id == "b3f0a9c1-1234-4567-8901-abcdef123456"

    def test_missing_scenario_defaults_to_unknown(self, sample_event_no_scenario):
        """Event without scenario_id → scenario = 'unknown'."""
        anomaly = perceive(sample_event_no_scenario)

        assert anomaly.scenario == "unknown"
        assert anomaly.anomaly_type == "pipeline_failure"
        assert anomaly.source_event_id == "no-scenario-001"

    def test_severity_and_risk_are_neutral(self, sample_event):
        """Phase 0 hardcoded neutral values."""
        anomaly = perceive(sample_event)

        assert anomaly.severity == 0.5
        assert anomaly.risk_score == 0.5

    def test_anomaly_type_matches_event_type(self, sample_event):
        """anomaly_type must be copied from event_type."""
        anomaly = perceive(sample_event)
        assert anomaly.anomaly_type == sample_event.event_type

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


class TestScoreRawMetrics:
    """Tests for _score_raw_metrics — agent interprets sensor data."""

    def test_http_failure_scores_1(self):
        from perception.handler import _score_raw_metrics

        raw = {
            "trigger": "http_failure",
            "current": {"http_code": 500, "latency_ms": 100, "fps": 30, "healthy": True},
            "recent_history": [],
        }
        assert _score_raw_metrics(raw) == 1.0

    def test_healthy_false_scores_high(self):
        from perception.handler import _score_raw_metrics

        raw = {
            "trigger": "health_false",
            "current": {"http_code": 200, "latency_ms": 100, "fps": 30, "healthy": False},
            "recent_history": [],
        }
        assert _score_raw_metrics(raw) >= 0.9

    def test_normal_metrics_score_zero(self):
        from perception.handler import _score_raw_metrics

        raw = {
            "trigger": "timeout",
            "current": {"http_code": 200, "latency_ms": 50, "fps": 30, "healthy": True},
            "recent_history": [],
            "latency_budget_sec": 2.0,
            "fps_min": 10.0,
            "detection_rate_min": 0.01,
        }
        assert _score_raw_metrics(raw) == 0.0

    def test_latency_over_budget_scores_high(self):
        from perception.handler import _score_raw_metrics

        raw = {
            "current": {"http_code": 200, "latency_ms": 3000, "fps": 30, "healthy": True},
            "recent_history": [],
            "latency_budget_sec": 2.0,
        }
        assert _score_raw_metrics(raw) >= 0.8

    def test_low_fps_scores_high(self):
        from perception.handler import _score_raw_metrics

        raw = {
            "current": {"http_code": 200, "latency_ms": 50, "fps": 5, "healthy": True},
            "recent_history": [],
            "fps_min": 10.0,
        }
        assert _score_raw_metrics(raw) >= 0.8

    def test_trend_detection_adds_score(self):
        from perception.handler import _score_raw_metrics

        raw = {
            "current": {"http_code": 200, "latency_ms": 500, "fps": 30, "healthy": True},
            "recent_history": [
                {"http_code": 200, "latency_ms": 100},
                {"http_code": 200, "latency_ms": 200},
                {"http_code": 200, "latency_ms": 500},
            ],
            "latency_budget_sec": 2.0,
        }
        # Rising latency trend should add 0.4
        assert _score_raw_metrics(raw) >= 0.4


class TestPerceiveWithRawMetrics:
    """Tests for perceive() when event contains raw_metrics."""

    def test_raw_metrics_used_for_severity(self):
        """When raw_metrics present, agent scores them instead of using labels."""
        import json
        from datetime import datetime, timezone
        from models.schemas import EventContext, RuntimeEvent

        raw = {
            "trigger": "http_failure",
            "current": {"http_code": 500, "latency_ms": 100},
            "recent_history": [],
        }
        event = RuntimeEvent(
            event_id="raw-001",
            event_type="resilience_degradation",
            occurred_at=datetime.now(timezone.utc),
            source="test",
            context=EventContext(
                status="failure",
                scenario_id="s3",
                raw_metrics=json.dumps(raw),
            ),
        )
        anomaly = perceive(event)
        # http_code=500 → score=1.0
        assert anomaly.severity == 1.0

    def test_raw_metrics_override_severity_label(self):
        """raw_metrics takes priority over severity label."""
        import json
        from datetime import datetime, timezone
        from models.schemas import EventContext, RuntimeEvent

        raw = {
            "trigger": "health_false",
            "current": {"http_code": 200, "latency_ms": 50, "healthy": False},
            "recent_history": [],
        }
        event = RuntimeEvent(
            event_id="raw-002",
            event_type="resilience_degradation",
            occurred_at=datetime.now(timezone.utc),
            source="test",
            context=EventContext(
                status="failure",
                severity="low",  # would give 0.3, but raw_metrics wins
                scenario_id="s3",
                raw_metrics=json.dumps(raw),
            ),
        )
        anomaly = perceive(event)
        # healthy=False → 0.9, NOT severity="low" → 0.3
        assert anomaly.severity >= 0.9

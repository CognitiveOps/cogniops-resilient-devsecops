"""
Shared pytest fixtures for runtime-agent tests.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import pytest

# ── Sample data ──────────────────────────────────────────────────────

SAMPLE_EVENT_DICT = {
    "event_id": "b3f0a9c1-1234-4567-8901-abcdef123456",
    "event_type": "manual_test_event",
    "occurred_at": "2026-03-01T12:00:00Z",
    "source": "test-publisher",
    "context": {
        "run_id": "run-001",
        "scenario_id": "S3",
        "stage": "deploy",
        "status": "fail",
        "severity": "medium",
    },
}

SAMPLE_EVENT_NO_SCENARIO = {
    "event_id": "no-scenario-001",
    "event_type": "pipeline_failure",
    "occurred_at": "2026-03-01T13:00:00Z",
    "source": "test-publisher",
    "context": {
        "status": "fail",
    },
}


@pytest.fixture
def sample_event() -> "RuntimeEvent":
    """A valid RuntimeEvent with scenario_id=S3."""
    from models.schemas import RuntimeEvent

    return RuntimeEvent(**SAMPLE_EVENT_DICT)


@pytest.fixture
def sample_event_no_scenario() -> "RuntimeEvent":
    """A valid RuntimeEvent without scenario_id."""
    from models.schemas import RuntimeEvent

    return RuntimeEvent(**SAMPLE_EVENT_NO_SCENARIO)


@pytest.fixture
def sample_anomaly() -> "AnomalyOutput":
    """A stub anomaly matching the default perceive() output for sample_event."""
    from models.schemas import AnomalyOutput

    return AnomalyOutput(
        scenario="S3",
        anomaly_type="manual_test_event",
        severity=0.5,
        risk_score=0.5,
        source_event_id="b3f0a9c1-1234-4567-8901-abcdef123456",
    )


@pytest.fixture
def sample_decision() -> "PlanningDecision":
    """A stub NO_OP decision (Phase 0 default)."""
    from models.schemas import DecisionType, PlanningDecision

    return PlanningDecision(
        decision=DecisionType.NO_OP,
        rationale="Phase 0 shadow mode — no action taken",
        policy_refs=[],
    )


@pytest.fixture
def sample_verdict() -> "GuardVerdict":
    """A stub guard verdict (Phase 0 – always approved)."""
    from models.schemas import GuardVerdict

    return GuardVerdict(
        approved=True,
        reason="Phase 0 — guard bypassed",
    )


@pytest.fixture
def sample_event_dict() -> dict:
    """Raw event dict with scenario_id=S3 (useful where a dict is needed)."""
    return SAMPLE_EVENT_DICT


@pytest.fixture
def sample_event_no_scenario_dict() -> dict:
    """Raw event dict without scenario_id."""
    return SAMPLE_EVENT_NO_SCENARIO


@pytest.fixture
def make_pubsub_body() -> callable:
    """Return a helper that wraps an event dict into a Pub/Sub push envelope."""

    def _make_pubsub_body(event_dict: dict) -> dict:
        encoded = base64.b64encode(json.dumps(event_dict).encode()).decode()
        return {
            "message": {
                "data": encoded,
                "messageId": "msg-test-001",
                "publishTime": "2026-03-01T12:00:01Z",
            },
            "subscription": "projects/test-project/subscriptions/runtime-agent-push",
        }

    return _make_pubsub_body

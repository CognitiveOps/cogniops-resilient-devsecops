"""
Shared pytest fixtures for runtime-agent tests.
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Ensure runtime-agent root is on sys.path so bare imports work (models.schemas, etc.)
_AGENT_ROOT = str(Path(__file__).resolve().parent.parent)
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

# Ensure project root is on sys.path so `baseline.*` imports work (PQC guard tests)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from models.schemas import (  # noqa: E402
    AnomalyOutput,
    DecisionType,
    EventContext,
    GuardVerdict,
    PlanningDecision,
    RuntimeEvent,
)


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
def sample_event() -> RuntimeEvent:
    """A valid RuntimeEvent with scenario_id=S3."""
    return RuntimeEvent(**SAMPLE_EVENT_DICT)


@pytest.fixture
def sample_event_no_scenario() -> RuntimeEvent:
    """A valid RuntimeEvent without scenario_id."""
    return RuntimeEvent(**SAMPLE_EVENT_NO_SCENARIO)


@pytest.fixture
def sample_anomaly() -> AnomalyOutput:
    """A stub anomaly matching the default perceive() output for sample_event."""
    return AnomalyOutput(
        scenario="S3",
        anomaly_type="manual_test_event",
        severity=0.5,
        risk_score=0.5,
        source_event_id="b3f0a9c1-1234-4567-8901-abcdef123456",
    )


@pytest.fixture
def sample_decision() -> PlanningDecision:
    """A stub NO_OP decision (Phase 0 default)."""
    return PlanningDecision(
        decision=DecisionType.NO_OP,
        rationale="Phase 0 shadow mode — no action taken",
        policy_refs=[],
    )


@pytest.fixture
def sample_verdict() -> GuardVerdict:
    """A stub guard verdict (Phase 0 – always approved)."""
    return GuardVerdict(
        approved=True,
        reason="Phase 0 — guard bypassed",
    )


def make_pubsub_body(event_dict: dict) -> dict:
    """Wrap an event dict into a Pub/Sub push envelope (base64 encoded)."""
    encoded = base64.b64encode(json.dumps(event_dict).encode()).decode()
    return {
        "message": {
            "data": encoded,
            "messageId": "msg-test-001",
            "publishTime": "2026-03-01T12:00:01Z",
        },
        "subscription": "projects/test-project/subscriptions/runtime-agent-push",
    }

"""
Pydantic models for the Phase 0 runtime-agent pipeline.

Covers:
  - Pub/Sub push envelope
  - Runtime event envelope (per runtime-event-contract.md)
  - Perception anomaly output
  - Planning decision
  - Guard verdict
  - Execution result
  - BigQuery decision row
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Event Envelope (runtime-event-contract.md) ──────────────────────


class EventContext(BaseModel):
    """Context block inside a runtime event."""

    run_id: Optional[str] = None
    scenario_id: Optional[str] = None
    stage: Optional[str] = None
    status: str
    severity: Optional[str] = None
    commit_sha: Optional[str] = None

    class Config:
        extra = "allow"  # unknown fields are kept but logged


ALLOWED_EVENT_TYPES_PHASE0 = frozenset(
    [
        "pipeline_failure",
        "policy_violation",
        "resilience_degradation",
        "risk_assessment",
        "adaptive_threat",
        "manual_test_event",
    ]
)


class RuntimeEvent(BaseModel):
    """Runtime event envelope – must match runtime-event-contract.md."""

    event_id: str = Field(..., description="UUID from publisher")
    event_type: str = Field(..., description="One of the allowed Phase 0 types")
    occurred_at: datetime = Field(..., description="RFC 3339 timestamp")
    source: str = Field(..., description="Publisher identity")
    context: EventContext

    class Config:
        extra = "allow"  # unknown top-level fields ignored per contract


# ── Pub/Sub Push Wrapper ────────────────────────────────────────────


class PubSubMessage(BaseModel):
    """Inner message from a Pub/Sub push delivery."""

    data: str = Field(..., description="Base64-encoded event payload")
    messageId: Optional[str] = None  # noqa: N815
    publishTime: Optional[str] = None  # noqa: N815


class PubSubPushEnvelope(BaseModel):
    """Top-level wrapper sent by Pub/Sub push subscriptions."""

    message: PubSubMessage
    subscription: Optional[str] = None


# ── Perception Output ───────────────────────────────────────────────


class AnomalyOutput(BaseModel):
    """Structured anomaly produced by the Perception module."""

    scenario: str = Field("unknown", description="Scenario ID from context or 'unknown'")
    anomaly_type: str = Field(..., description="Copied from event_type")
    severity: float = Field(0.5, description="Neutral in Phase 0")
    risk_score: float = Field(0.5, description="Neutral in Phase 0")
    source_event_id: str = Field(..., description="Original event_id")


# ── Planning Decision ───────────────────────────────────────────────


class DecisionType(str, enum.Enum):
    NO_OP = "NO_OP"
    BLOCK = "BLOCK"
    ROLLBACK = "ROLLBACK"
    QUARANTINE = "QUARANTINE"
    ESCALATE = "ESCALATE"


class PlanningDecision(BaseModel):
    """Output of the Risk/Planning module."""

    decision: DecisionType = Field(
        DecisionType.NO_OP, description="Bounded action surface"
    )
    rationale: str = Field(
        "Phase 0 shadow mode — no action taken",
        description="Human-readable explanation",
    )
    policy_refs: list[str] = Field(
        default_factory=list,
        description="NIST/ISO/IMO control references (empty in Phase 0)",
    )


# ── Guard Verdict ───────────────────────────────────────────────────


class GuardVerdict(BaseModel):
    """Output of the Policy Guard module."""

    approved: bool = Field(True, description="Always true in Phase 0")
    reason: str = Field(
        "Phase 0 — guard bypassed",
        description="Human-readable guard rationale",
    )


# ── Execution Result ────────────────────────────────────────────────


class ExecutionResult(BaseModel):
    """Output of the Execution module."""

    decision_executed: bool = Field(
        False, description="Always false in Phase 0 (shadow mode)"
    )
    log_message: str = Field("", description="Stdout log line emitted")


# ── BigQuery Decision Row ───────────────────────────────────────────


class DecisionRow(BaseModel):
    """
    One row in agent_metrics.runtime_decisions.
    Schema mirrors infra/runtime.tf § BigQuery: runtime_decisions.
    """

    event_id: str
    event_type: str
    occurred_at: datetime
    source: str
    context: Optional[dict[str, Any]] = None
    decision: str
    decision_executed: bool
    rationale: Optional[str] = None
    policy_refs: Optional[list[str]] = None
    mode: str = "shadow"
    agentops_trace_id: Optional[str] = None
    processed_at: datetime

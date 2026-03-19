"""
Pydantic v2 schemas for the Design-Time Agent.

Covers:
  - Metric context (BQ query results, trend summaries)
  - Proposal input/output (structured improvement proposals)
  - Change specifications (threshold, policy, workflow)
  - Validation result
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Change Types ─────────────────────────────────────────────────────


class ChangeType(str, enum.Enum):
    """Categories of structural changes the agent can propose."""

    THRESHOLD_ADJUSTMENT = "threshold_adjustment"
    POLICY_ADDITION = "policy_addition"
    POLICY_MODIFICATION = "policy_modification"
    WORKFLOW_IMPROVEMENT = "workflow_improvement"
    CONFIG_UPDATE = "config_update"


# ── Metric Summary ───────────────────────────────────────────────────


class ScenarioMetricSummary(BaseModel):
    """Aggregated metrics for a single scenario over a time window."""

    scenario_id: str = Field(..., description="e.g. 's1', 's3', 'ss2'")
    metric_name: str = Field(..., description="e.g. 'MTTD', 'CFR', 'TTD'")
    mean_value: float
    p50_value: Optional[float] = None
    p95_value: Optional[float] = None
    sample_count: int = Field(..., ge=0)
    trend_direction: Optional[str] = Field(
        None, description="'improving', 'degrading', or 'stable'"
    )
    unit: str = Field("", description="e.g. 'seconds', 'percent'")


class RuntimeDecisionSummary(BaseModel):
    """Summary of runtime agent decisions over a time window."""

    total_decisions: int = Field(0, ge=0)
    by_action: dict[str, int] = Field(
        default_factory=dict,
        description="Count per action type: {'NO_OP': 42, 'BLOCK': 3, ...}",
    )
    by_scenario: dict[str, int] = Field(
        default_factory=dict,
        description="Count per scenario: {'s3': 10, 'ss2': 5, ...}",
    )
    execution_rate: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of decisions actually executed",
    )


# ── Analysis Context ─────────────────────────────────────────────────


class AnalysisContext(BaseModel):
    """Full context assembled by the context builder for LLM analysis."""

    built_at: datetime
    window_days: int = Field(30, description="Analysis lookback window in days")
    scenario_metrics: list[ScenarioMetricSummary] = Field(default_factory=list)
    runtime_decisions: RuntimeDecisionSummary = Field(
        default_factory=RuntimeDecisionSummary
    )
    current_thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Key thresholds from config (e.g. 'anomaly_z_threshold': 2.5)",
    )
    active_policies: list[str] = Field(
        default_factory=list,
        description="List of active OPA policy names/paths",
    )
    workflow_summaries: list[str] = Field(
        default_factory=list,
        description="Brief description of active GitHub Actions workflows",
    )


# ── Proposed Change ──────────────────────────────────────────────────


class ProposedChange(BaseModel):
    """A single structural change proposed by the agent."""

    change_type: ChangeType
    target_file: str = Field(..., description="File to modify (e.g. 's3_rollback.yml')")
    description: str = Field(
        ..., description="Human-readable description of the change"
    )
    current_value: Optional[str] = Field(None, description="Current setting/value")
    proposed_value: str = Field(..., description="Proposed new setting/value")
    rationale: str = Field(
        ..., description="Why this change improves the target metric"
    )


# ── Expected Impact ──────────────────────────────────────────────────


class ExpectedImpact(BaseModel):
    """Estimated metric impact from a proposal."""

    metric_name: str = Field(..., description="e.g. 'MTTR', 'CFR'")
    estimated_change: str = Field(..., description="e.g. '-30%', '+15%', 'no change'")
    confidence: float = Field(..., ge=0.0, le=1.0)


# ── Validation Result ────────────────────────────────────────────────


class ValidationResult(BaseModel):
    """Outcome of deterministic validation on a DesignProposal."""

    valid: bool
    checks_passed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Design Proposal ──────────────────────────────────────────────────


class DesignProposal(BaseModel):
    """LLM-generated structural improvement proposal.

    Always requires human review — never executed automatically.
    """

    proposal_id: str = Field(..., description="Unique ID: design-{date}-{uuid8}")
    created_at: datetime
    intent: str = Field(..., description="Goal statement (e.g. 'Reduce MTTR in S3')")
    target_scenarios: list[str] = Field(
        ..., min_length=1, description="Scenarios affected (e.g. ['S3', 'SS2'])"
    )
    analysis_summary: str = Field(
        ..., description="2-5 sentence summary of the metric analysis"
    )
    changes: list[ProposedChange] = Field(
        ..., min_length=1, description="Proposed structural changes"
    )
    expected_impact: list[ExpectedImpact] = Field(
        default_factory=list, description="Estimated metric improvements"
    )
    policy_refs: list[str] = Field(
        default_factory=list,
        description="Relevant NIST/ISO control references",
    )
    validation: ValidationResult = Field(
        default_factory=lambda: ValidationResult(valid=False)
    )
    requires_human_review: Literal[True] = True

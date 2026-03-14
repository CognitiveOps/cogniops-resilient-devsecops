"""
Pydantic v2 schemas for the Security Compliance Agent.

Covers:
  - NIST feed entries (NVD API v2 + SP 800-53 CPRT)
  - Control detail (full text from CPRT)
  - Enriched diff report (current vs latest)
  - Compliance proposal (LLM-generated, always requires human review)
  - Validation result
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Feed Source ──────────────────────────────────────────────────────


class FeedSource(str, enum.Enum):
    """Supported NIST data sources."""

    NIST_NVD = "NIST_NVD"
    NIST_SP800_53 = "NIST_SP800_53"


# ── Feed Entry ───────────────────────────────────────────────────────


class FeedEntry(BaseModel):
    """A single update detected from a NIST feed."""

    source: FeedSource
    ref_id: str = Field(..., description="Control identifier, e.g. 'SP 800-53 CM-3'")
    current_revision: str = Field("", description="Revision currently in our YAML")
    latest_revision: str = Field(..., description="Latest revision from NIST")
    change_summary: str = Field("", description="Brief description of what changed")
    published_at: Optional[datetime] = Field(
        None, description="When the update was published"
    )


# ── Control Detail (full text from CPRT) ─────────────────────────────


class ControlDetail(BaseModel):
    """Full text of an SP 800-53 control fetched from NIST CPRT."""

    control_id: str = Field(..., description="e.g. 'CM-3'")
    title: str = Field(..., description="e.g. 'Configuration Change Control'")
    full_text: str = Field(..., description="Complete control requirement text")
    guidance: str = Field("", description="Supplemental guidance")
    related_controls: list[str] = Field(
        default_factory=list, description="Related control IDs"
    )
    enhancements: list[str] = Field(
        default_factory=list, description="Control enhancement descriptions"
    )


# ── Enriched Entry (feed entry + full text) ──────────────────────────


class EnrichedEntry(BaseModel):
    """A feed entry enriched with the full control text for LLM analysis."""

    feed_entry: FeedEntry
    new_full_text: str = Field("", description="Full text of the new/updated control")
    guidance: str = Field("", description="Supplemental guidance from NIST")
    related_controls: list[str] = Field(default_factory=list)
    change_highlights: str = Field(
        "", description="Key differences (deterministic summary)"
    )


# ── Diff Report ──────────────────────────────────────────────────────


class DiffReport(BaseModel):
    """Result of comparing current YAML/Rego against NIST feed data."""

    checked_at: datetime
    new_entries: list[EnrichedEntry] = Field(
        default_factory=list, description="Controls not in current YAML"
    )
    updated_entries: list[EnrichedEntry] = Field(
        default_factory=list, description="Controls with revision changes"
    )
    affected_decision_types: list[str] = Field(
        default_factory=list,
        description="Decision types impacted (BLOCK, ROLLBACK, ...)",
    )

    @property
    def has_changes(self) -> bool:
        return bool(self.new_entries or self.updated_entries)


# ── YAML Patch ───────────────────────────────────────────────────────


class YAMLPatchEntry(BaseModel):
    """A single ref entry to add or update in control-mappings.yaml."""

    ref: str
    title: str
    revision: Optional[str] = None


class YAMLPatch(BaseModel):
    """Proposed changes to control-mappings.yaml."""

    updates: dict[str, list[YAMLPatchEntry]] = Field(
        default_factory=dict,
        description="Decision type → list of ref entries to add/update",
    )


# ── Compliance Proposal ──────────────────────────────────────────────


class ComplianceProposal(BaseModel):
    """LLM-generated compliance update proposal. Always requires human review."""

    proposal_id: str = Field(..., description="Unique ID: comp-{date}-{seq}")
    created_at: datetime
    diff_report: DiffReport
    proposed_yaml_patch: YAMLPatch
    proposed_rego_suggestions: list[str] = Field(
        default_factory=list,
        description="Optional Rego rule suggestions as human-readable text",
    )
    impact_assessment: str = Field(
        ..., description="LLM-generated reasoning about impact on scenarios"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM confidence in the proposal"
    )
    requires_human_review: Literal[True] = True


# ── Validation Result ────────────────────────────────────────────────


class ValidationResult(BaseModel):
    """Outcome of deterministic validation on a ComplianceProposal."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Feed Snapshot (for GCS caching) ──────────────────────────────────


class FeedSnapshot(BaseModel):
    """Persisted snapshot of a feed ingestion cycle."""

    fetched_at: datetime
    source: FeedSource
    entries: list[FeedEntry]
    api_response_count: int = Field(0, description="Total items returned by the API")


class LastCheckRecord(BaseModel):
    """Timestamp of the last successful feed check."""

    timestamp: datetime
    sources_checked: list[str] = Field(default_factory=list)

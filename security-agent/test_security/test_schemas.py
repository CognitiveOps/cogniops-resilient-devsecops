"""Tests for Pydantic schemas — security-agent/models/schemas.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from models.schemas import (
    ComplianceProposal,
    ControlDetail,
    DiffReport,
    EnrichedEntry,
    FeedEntry,
    FeedSnapshot,
    FeedSource,
    LastCheckRecord,
    ValidationResult,
    YAMLPatch,
    YAMLPatchEntry,
)


# ── FeedEntry ────────────────────────────────────────────────────────


class TestFeedEntry:
    def test_create_nvd_entry(self):
        entry = FeedEntry(
            source=FeedSource.NIST_NVD,
            ref_id="CVE-2026-12345",
            latest_revision="2026-03-14",
            change_summary="Test vulnerability",
        )
        assert entry.source == FeedSource.NIST_NVD
        assert entry.ref_id == "CVE-2026-12345"
        assert entry.current_revision == ""

    def test_create_sp800_53_entry(self):
        entry = FeedEntry(
            source=FeedSource.NIST_SP800_53,
            ref_id="SP 800-53 CM-3",
            current_revision="Rev. 5",
            latest_revision="Rev. 6",
            change_summary="Configuration Change Control",
            published_at=datetime(2026, 3, 14, tzinfo=timezone.utc),
        )
        assert entry.source == FeedSource.NIST_SP800_53
        assert entry.current_revision == "Rev. 5"
        assert entry.latest_revision == "Rev. 6"

    def test_optional_fields_default(self):
        entry = FeedEntry(
            source=FeedSource.NIST_NVD,
            ref_id="CVE-2026-00001",
            latest_revision="1.0",
        )
        assert entry.current_revision == ""
        assert entry.change_summary == ""
        assert entry.published_at is None


# ── ControlDetail ────────────────────────────────────────────────────


class TestControlDetail:
    def test_full_detail(self):
        detail = ControlDetail(
            control_id="CM-3",
            title="Configuration Change Control",
            full_text="The organization determines...",
            guidance="Configuration change control involves...",
            related_controls=["CM-2", "CM-4"],
            enhancements=["Automated Documentation"],
        )
        assert detail.control_id == "CM-3"
        assert len(detail.related_controls) == 2

    def test_minimal_detail(self):
        detail = ControlDetail(
            control_id="IR-6",
            title="Incident Reporting",
            full_text="The organization reports...",
        )
        assert detail.guidance == ""
        assert detail.related_controls == []
        assert detail.enhancements == []


# ── DiffReport ───────────────────────────────────────────────────────


class TestDiffReport:
    def test_empty_diff(self):
        diff = DiffReport(checked_at=datetime.now(timezone.utc))
        assert not diff.has_changes
        assert diff.affected_decision_types == []

    def test_diff_with_updates(self):
        entry = EnrichedEntry(
            feed_entry=FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                current_revision="Rev. 5",
                latest_revision="Rev. 6",
            ),
            change_highlights="CM-3: 'Rev. 5' → 'Rev. 6'",
        )
        diff = DiffReport(
            checked_at=datetime.now(timezone.utc),
            updated_entries=[entry],
            affected_decision_types=["BLOCK"],
        )
        assert diff.has_changes
        assert "BLOCK" in diff.affected_decision_types

    def test_diff_with_new_entries(self):
        entry = EnrichedEntry(
            feed_entry=FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 SI-7",
                latest_revision="Rev. 5",
            ),
            change_highlights="New control: SP 800-53 SI-7",
        )
        diff = DiffReport(
            checked_at=datetime.now(timezone.utc),
            new_entries=[entry],
        )
        assert diff.has_changes


# ── ComplianceProposal ───────────────────────────────────────────────


class TestComplianceProposal:
    def test_valid_proposal(self):
        diff = DiffReport(
            checked_at=datetime.now(timezone.utc),
            updated_entries=[],
            affected_decision_types=["BLOCK"],
        )
        proposal = ComplianceProposal(
            proposal_id="comp-20260314-abcd1234",
            created_at=datetime.now(timezone.utc),
            diff_report=diff,
            proposed_yaml_patch=YAMLPatch(
                updates={
                    "BLOCK": [
                        YAMLPatchEntry(
                            ref="NIST SP 800-53 CM-3", title="Test", revision="Rev. 6"
                        )
                    ]
                }
            ),
            impact_assessment="CM-3 Rev.6 adds supply chain scope affecting S1 CI/CD pipeline.",
            confidence=0.85,
            requires_human_review=True,
        )
        assert proposal.requires_human_review is True
        assert proposal.confidence == 0.85

    def test_requires_human_review_always_true(self):
        """requires_human_review is Literal[True] — cannot be False."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ComplianceProposal(
                proposal_id="test",
                created_at=datetime.now(timezone.utc),
                diff_report=DiffReport(checked_at=datetime.now(timezone.utc)),
                proposed_yaml_patch=YAMLPatch(),
                impact_assessment="Test",
                confidence=0.5,
                requires_human_review=False,
            )

    def test_confidence_bounds(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ComplianceProposal(
                proposal_id="test",
                created_at=datetime.now(timezone.utc),
                diff_report=DiffReport(checked_at=datetime.now(timezone.utc)),
                proposed_yaml_patch=YAMLPatch(),
                impact_assessment="Test",
                confidence=1.5,  # > 1.0
                requires_human_review=True,
            )


# ── ValidationResult ─────────────────────────────────────────────────


class TestValidationResult:
    def test_valid_result(self):
        result = ValidationResult(valid=True)
        assert result.valid
        assert result.errors == []

    def test_invalid_result(self):
        result = ValidationResult(
            valid=False,
            errors=["missing impact_assessment"],
            warnings=["low confidence"],
        )
        assert not result.valid
        assert len(result.errors) == 1


# ── FeedSnapshot ─────────────────────────────────────────────────────


class TestFeedSnapshot:
    def test_snapshot(self):
        snap = FeedSnapshot(
            fetched_at=datetime.now(timezone.utc),
            source=FeedSource.NIST_NVD,
            entries=[],
            api_response_count=0,
        )
        assert snap.source == FeedSource.NIST_NVD

    def test_last_check_record(self):
        record = LastCheckRecord(
            timestamp=datetime.now(timezone.utc),
            sources_checked=["NIST_NVD", "NIST_SP800_53"],
        )
        assert len(record.sources_checked) == 2

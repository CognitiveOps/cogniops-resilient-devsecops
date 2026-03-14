"""Tests for the diff engine — security-agent/agent/tools/diff_engine.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.tools.diff_engine import _extract_base_ref, compute_diff
from models.schemas import FeedEntry, FeedSource


# ── Sample YAML (matches control-mappings.yaml) ─────────────────────

SAMPLE_YAML = {
    "schema_version": "1.0",
    "mappings": {
        "BLOCK": [
            {
                "ref": "NIST SP 800-53 CM-3",
                "title": "Configuration Change Control",
                "revision": "Rev. 5",
            },
            {"ref": "ISO 27001:2022 A.12.1.2", "title": "Change Management"},
        ],
        "ROLLBACK": [
            {
                "ref": "NIST SP 800-53 CP-10",
                "title": "System Recovery",
                "revision": "Rev. 5",
            },
        ],
        "QUARANTINE": [
            {
                "ref": "NIST SP 800-53 SI-3",
                "title": "Malicious Code Protection",
                "revision": "Rev. 5",
            },
        ],
        "ESCALATE": [
            {
                "ref": "NIST SP 800-53 IR-6",
                "title": "Incident Reporting",
                "revision": "Rev. 5",
            },
        ],
        "NO_OP": [],
    },
}


# ── Base Ref Extraction ──────────────────────────────────────────────


class TestExtractBaseRef:
    def test_sp800_53_format(self):
        assert _extract_base_ref("SP 800-53 CM-3") == "CM-3"

    def test_nist_prefix(self):
        assert _extract_base_ref("NIST SP 800-53 CP-10") == "CP-10"

    def test_no_match(self):
        assert _extract_base_ref("ISO 27001:2022 A.12.1.2") is None

    def test_cve_no_match(self):
        assert _extract_base_ref("CVE-2026-12345") is None


# ── Compute Diff ─────────────────────────────────────────────────────


class TestComputeDiff:
    def test_revision_change_detected(self):
        """CM-3 updated from Rev. 5 to Rev. 6 should be flagged."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 6",
                change_summary="Updated with supply chain provisions",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert len(diff.updated_entries) == 1
        assert diff.updated_entries[0].feed_entry.ref_id == "SP 800-53 CM-3"
        assert diff.updated_entries[0].feed_entry.current_revision == "Rev. 5"
        assert "BLOCK" in diff.affected_decision_types

    def test_no_change_when_same_revision(self):
        """CM-3 with same revision should produce empty diff."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 5",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert len(diff.updated_entries) == 0
        assert not diff.has_changes

    def test_new_control_detected(self):
        """SI-7 (not in YAML) from SP 800-53 should be flagged as new."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 SI-7",
                latest_revision="Rev. 5",
                change_summary="Software Integrity Verification",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert len(diff.new_entries) == 1
        assert diff.new_entries[0].feed_entry.ref_id == "SP 800-53 SI-7"

    def test_nvd_cve_informational_only(self):
        """NVD CVEs without matching SP 800-53 ref produce no diff entries."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_NVD,
                ref_id="CVE-2026-99999",
                latest_revision="1.0",
                change_summary="Some vulnerability",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert not diff.has_changes

    def test_multiple_updates(self):
        """Multiple controls updating should all be detected."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 6",
            ),
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CP-10",
                latest_revision="Rev. 6",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert len(diff.updated_entries) == 2
        assert "BLOCK" in diff.affected_decision_types
        assert "ROLLBACK" in diff.affected_decision_types

    def test_empty_feed(self):
        """No feed entries → empty diff."""
        diff = compute_diff([], SAMPLE_YAML)
        assert not diff.has_changes

    def test_empty_yaml(self):
        """Empty YAML → new entries only (no updates)."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 5",
            ),
        ]
        diff = compute_diff(entries, {"mappings": {}})

        assert len(diff.new_entries) == 1
        assert len(diff.updated_entries) == 0

    def test_iso_entries_ignored(self):
        """ISO refs in YAML should not match SP 800-53 feed entries."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 5",  # same as current
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)
        # No change because revision matches
        assert not diff.has_changes

    def test_change_highlights_format(self):
        """Updated entry should have human-readable change highlights."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 SI-3",
                latest_revision="Rev. 6",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert len(diff.updated_entries) == 1
        assert "Rev. 5" in diff.updated_entries[0].change_highlights
        assert "Rev. 6" in diff.updated_entries[0].change_highlights

    def test_affected_decision_types_sorted(self):
        """affected_decision_types should be sorted alphabetically."""
        entries = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 SI-3",
                latest_revision="Rev. 6",
            ),
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 6",
            ),
        ]
        diff = compute_diff(entries, SAMPLE_YAML)

        assert diff.affected_decision_types == sorted(diff.affected_decision_types)

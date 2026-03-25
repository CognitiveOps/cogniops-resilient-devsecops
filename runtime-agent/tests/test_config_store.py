"""Tests for the live-loading config store (GCS + TTL cache).

Covers:
  - GCS unavailable → fallback to built-in _CONTROL_MAP
  - GCS returns valid YAML → cache populated, refs returned
  - TTL expiry → re-fetch triggered
  - Malformed YAML → graceful fallback
  - Empty CONFIG_BUCKET → no GCS attempt, built-in defaults
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import yaml

from models.schemas import DecisionType
from telemetry.config_store import ConfigStore

# ── Sample YAML payload (mirrors config/control-mappings.yaml) ──────

VALID_YAML = {
    "schema_version": "1.0",
    "updated_at": "2026-03-13T00:00:00Z",
    "mappings": {
        "BLOCK": [
            {"ref": "NIST SP 800-53 CM-3", "title": "Config Change Control"},
            {"ref": "ISO 27001:2022 A.12.1.2", "title": "Change Management"},
        ],
        "ROLLBACK": [
            {"ref": "NIST SP 800-53 CP-10", "title": "Recovery"},
        ],
        "QUARANTINE": [
            {"ref": "NIST SP 800-53 SI-3", "title": "Malware Protection"},
        ],
        "ESCALATE": [
            {"ref": "NIST SP 800-53 IR-6", "title": "Incident Reporting"},
        ],
        "NO_OP": [],
    },
}

MALFORMED_YAML_DATA = "not: [a valid: mapping: structure"


# ── Tests: no GCS configured ────────────────────────────────────────


class TestConfigStoreNoGCS:
    """When CONFIG_BUCKET is empty, store falls back to built-in defaults."""

    def test_empty_bucket_returns_builtin(self):
        store = ConfigStore()
        with patch("telemetry.config_store.CONFIG_BUCKET", ""):
            mappings = store.get_control_mappings()
        # Should have all 5 decision types from built-in
        assert "BLOCK" in mappings
        assert "NO_OP" in mappings
        assert len(mappings["BLOCK"]) == 3  # 3 refs in _CONTROL_MAP

    def test_no_gcs_fetch_attempted(self):
        store = ConfigStore()
        with patch("telemetry.config_store.CONFIG_BUCKET", ""):
            result = store._fetch_from_gcs("any/path.yaml")
        assert result is None


# ── Tests: GCS returns valid YAML ───────────────────────────────────


class TestConfigStoreValidGCS:
    """When GCS returns valid YAML, cache is populated."""

    def _make_store_with_gcs(self, yaml_data: dict) -> ConfigStore:
        store = ConfigStore()
        store._fetch_from_gcs = MagicMock(return_value=yaml_data)
        return store

    def test_valid_yaml_populates_cache(self):
        store = self._make_store_with_gcs(VALID_YAML)
        mappings = store.get_control_mappings()
        assert mappings["BLOCK"] == [
            "NIST SP 800-53 CM-3",
            "ISO 27001:2022 A.12.1.2",
        ]
        assert mappings["ROLLBACK"] == ["NIST SP 800-53 CP-10"]
        assert mappings["NO_OP"] == []

    def test_cache_hit_no_refetch(self):
        store = self._make_store_with_gcs(VALID_YAML)
        store.get_control_mappings()  # First call — triggers fetch
        store.get_control_mappings()  # Second call — cache hit
        store._fetch_from_gcs.assert_called_once()

    def test_ttl_expiry_triggers_refetch(self):
        store = self._make_store_with_gcs(VALID_YAML)
        store.get_control_mappings()  # First call
        # Simulate TTL expiry
        store._last_fetch = time.monotonic() - 600  # 10 min ago
        store.get_control_mappings()  # Should refetch
        assert store._fetch_from_gcs.call_count == 2


# ── Tests: GCS failures ─────────────────────────────────────────────


class TestConfigStoreGCSFailure:
    """When GCS is unavailable, falls back to built-in defaults."""

    def test_gcs_exception_returns_builtin(self):
        store = ConfigStore()
        store._fetch_from_gcs = MagicMock(return_value=None)
        mappings = store.get_control_mappings()
        assert "BLOCK" in mappings
        assert len(mappings["BLOCK"]) == 3

    def test_gcs_returns_no_mappings_key(self):
        store = ConfigStore()
        store._fetch_from_gcs = MagicMock(return_value={"bad": "data"})
        mappings = store.get_control_mappings()
        assert "BLOCK" in mappings  # Fell back to built-in

    def test_malformed_entries_skipped(self):
        bad_yaml = {
            "mappings": {
                "BLOCK": [
                    {"ref": "NIST SP 800-53 CM-3"},
                    "not-a-dict",
                    {"no_ref_key": True},
                ],
            },
        }
        store = ConfigStore()
        store._fetch_from_gcs = MagicMock(return_value=bad_yaml)
        mappings = store.get_control_mappings()
        assert mappings["BLOCK"] == ["NIST SP 800-53 CM-3"]


# ── Tests: cache behavior ───────────────────────────────────────────


class TestConfigStoreCacheBehavior:
    """Edge cases around TTL and cache state."""

    def test_fresh_store_is_always_stale(self):
        store = ConfigStore()
        assert store._is_stale() is True

    def test_after_fetch_not_stale(self):
        store = ConfigStore()
        store._last_fetch = time.monotonic()
        assert store._is_stale() is False

    def test_stale_after_interval(self):
        store = ConfigStore()
        store._last_fetch = time.monotonic() - 400
        with patch("telemetry.config_store.REFRESH_INTERVAL_SEC", 300):
            assert store._is_stale() is True

    def test_gcs_success_then_failure_uses_cache(self):
        """If GCS was once successful, subsequent failures use cached data."""
        store = ConfigStore()
        store._fetch_from_gcs = MagicMock(return_value=VALID_YAML)
        mappings1 = store.get_control_mappings()
        assert mappings1["BLOCK"] == [
            "NIST SP 800-53 CM-3",
            "ISO 27001:2022 A.12.1.2",
        ]

        # Simulate TTL expiry + GCS failure
        store._last_fetch = time.monotonic() - 600
        store._fetch_from_gcs = MagicMock(return_value=None)
        mappings2 = store.get_control_mappings()
        # Should still return cached data
        assert mappings2["BLOCK"] == [
            "NIST SP 800-53 CM-3",
            "ISO 27001:2022 A.12.1.2",
        ]

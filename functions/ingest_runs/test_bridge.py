"""Tests for the Pub/Sub bridge logic in the ingest Cloud Function."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Patch GCP clients before importing the module
with patch("google.cloud.bigquery.Client"), patch(
    "google.cloud.pubsub_v1.PublisherClient"
):
    from main import _EVENT_TYPE_MAP, _maybe_publish_runtime_event


@pytest.fixture()
def mock_pubsub():
    with patch("main.pubsub_client") as mock_client, patch(
        "main.PROJECT_ID", "test-project"
    ):
        mock_client.topic_path.return_value = (
            "projects/test-project/topics/runtime-events-v1"
        )
        future = MagicMock()
        future.result.return_value = "msg-123"
        mock_client.publish.return_value = future
        yield mock_client


class TestEventTypeMapping:
    """Verify the (scenario_id, status) → event_type mapping table."""

    def test_s1_failure(self):
        assert _EVENT_TYPE_MAP[("s1", "failure")] == "pipeline_failure"

    def test_s3_failure(self):
        assert _EVENT_TYPE_MAP[("s3", "failure")] == "resilience_degradation"

    def test_ss1_deny(self):
        assert _EVENT_TYPE_MAP[("ss1", "deny")] == "policy_violation"

    def test_ss1_failure(self):
        assert _EVENT_TYPE_MAP[("ss1", "failure")] == "policy_violation"

    def test_ss2_failure(self):
        assert _EVENT_TYPE_MAP[("ss2", "failure")] == "resilience_degradation"

    def test_s1_success_not_mapped(self):
        assert ("s1", "success") not in _EVENT_TYPE_MAP


class TestMaybePublishRuntimeEvent:
    """Test the _maybe_publish_runtime_event bridge function."""

    def _make_payload(
        self, scenario_id: str = "s1", status: str = "failure"
    ) -> dict:
        return {
            "run_id": "run-001",
            "scenario_id": scenario_id,
            "stage": "build",
            "status": status,
            "commit_sha": "abc123",
            "t_end": "2025-01-15T10:00:00Z",
        }

    def test_skips_baseline_variant(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(), {"variant": "baseline"}
        )
        mock_pubsub.publish.assert_not_called()

    def test_skips_empty_variant(self, mock_pubsub):
        _maybe_publish_runtime_event(self._make_payload(), {})
        mock_pubsub.publish.assert_not_called()

    def test_skips_success_status(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(status="success"), {"variant": "runtime_only"}
        )
        mock_pubsub.publish.assert_not_called()

    def test_publishes_for_runtime_only(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(), {"variant": "runtime_only"}
        )
        mock_pubsub.publish.assert_called_once()
        data = json.loads(mock_pubsub.publish.call_args[0][1])
        assert data["event_type"] == "pipeline_failure"
        assert data["source"] == "baseline/s1"
        assert data["context"]["variant"] == "runtime_only"

    def test_publishes_for_full_variant(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(), {"variant": "full"}
        )
        mock_pubsub.publish.assert_called_once()

    def test_ss1_deny_maps_to_policy_violation(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(scenario_id="ss1", status="deny"),
            {"variant": "runtime_only"},
        )
        data = json.loads(mock_pubsub.publish.call_args[0][1])
        assert data["event_type"] == "policy_violation"
        assert data["context"]["severity"] == "critical"

    def test_s3_failure_maps_to_resilience_degradation(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(scenario_id="s3"),
            {"variant": "full"},
        )
        data = json.loads(mock_pubsub.publish.call_args[0][1])
        assert data["event_type"] == "resilience_degradation"
        assert data["context"]["severity"] == "high"

    def test_runtime_event_has_required_fields(self, mock_pubsub):
        _maybe_publish_runtime_event(
            self._make_payload(), {"variant": "runtime_only"}
        )
        data = json.loads(mock_pubsub.publish.call_args[0][1])
        assert "event_id" in data
        assert "event_type" in data
        assert "occurred_at" in data
        assert "source" in data
        assert "context" in data
        ctx = data["context"]
        assert "run_id" in ctx
        assert "scenario_id" in ctx
        assert "stage" in ctx
        assert "status" in ctx
        assert "severity" in ctx
        assert "commit_sha" in ctx

    def test_pubsub_failure_does_not_raise(self, mock_pubsub):
        mock_pubsub.publish.side_effect = Exception("Pub/Sub down")
        # Should not raise — bridge is best-effort
        _maybe_publish_runtime_event(
            self._make_payload(), {"variant": "runtime_only"}
        )

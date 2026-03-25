"""
Tests for mode-gated execution tools (Step 4).

- shadow: log only, executed=False
- advisory: log + notify, executed=False
- enforce: log + execute real action, executed=True
- GitHub API failures → fail-open (NO_OP)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent.tools.execution_tools import (
    block_deployment,
    escalate_to_human,
    no_action,
    quarantine_artifact,
    rollback_deployment,
)


# ── NO_OP (always safe, all modes) ──────────────────────────────────


class TestNoAction:
    """NO_OP works in all modes without side effects."""

    def test_shadow(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "shadow")
        result = no_action(rationale="Low severity")
        assert result["action"] == "NO_OP"
        assert result["executed"] is False
        assert result["mode"] == "shadow"

    def test_advisory(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "advisory")
        result = no_action(rationale="Low severity")
        assert result["action"] == "NO_OP"
        assert result["executed"] is False

    def test_enforce(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")
        result = no_action(rationale="Low severity")
        assert result["action"] == "NO_OP"
        assert result["executed"] is False


# ── BLOCK ────────────────────────────────────────────────────────────


class TestBlockDeployment:
    """BLOCK mode gating."""

    def test_shadow(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "shadow")
        result = block_deployment(rationale="Policy violation", target="d-1")
        assert result["action"] == "BLOCK"
        assert result["executed"] is False
        assert "logged only" in result["message"].lower()

    def test_advisory_creates_issue(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "advisory")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.execution_tools._notify_advisory",
            return_value="https://github.com/issue/1",
        ):
            result = block_deployment(rationale="Policy violation", target="d-1")

        assert result["action"] == "BLOCK"
        assert result["executed"] is False
        assert result["issue_url"] == "https://github.com/issue/1"

    def test_enforce_executes(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")
        with patch(
            "agent.tools.execution_tools._notify_advisory",
            return_value="https://github.com/issue/2",
        ):
            result = block_deployment(rationale="Policy violation", target="d-1")

        assert result["action"] == "BLOCK"
        assert result["executed"] is True


# ── ROLLBACK ─────────────────────────────────────────────────────────


class TestRollbackDeployment:
    """ROLLBACK mode gating."""

    def test_shadow(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "shadow")
        result = rollback_deployment(rationale="Critical failure", target="run-1")
        assert result["action"] == "ROLLBACK"
        assert result["executed"] is False

    def test_advisory(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "advisory")
        with patch(
            "agent.tools.execution_tools._notify_advisory",
            return_value="https://github.com/issue/3",
        ):
            result = rollback_deployment(rationale="Critical failure", target="run-1")
        assert result["executed"] is False
        assert result["issue_url"] == "https://github.com/issue/3"

    def test_enforce_dispatches_workflow(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.dispatch_workflow",
            new_callable=AsyncMock,
            return_value=GitHubResult(ok=True, status_code=204),
        ):
            result = rollback_deployment(rationale="Critical failure", target="run-1")

        assert result["action"] == "ROLLBACK"
        assert result["executed"] is True
        assert result["dispatch_ok"] is True

    def test_enforce_dispatch_failure_failopen(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.dispatch_workflow",
            new_callable=AsyncMock,
            return_value=GitHubResult(ok=False, error="timeout"),
        ):
            result = rollback_deployment(rationale="Critical failure", target="run-1")

        assert result["action"] == "ROLLBACK"
        assert result["executed"] is False


# ── QUARANTINE ───────────────────────────────────────────────────────


class TestQuarantineArtifact:
    """QUARANTINE mode gating."""

    def test_shadow(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "shadow")
        result = quarantine_artifact(rationale="PQC failure", artifact_id="art-1")
        assert result["action"] == "QUARANTINE"
        assert result["executed"] is False

    def test_advisory(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "advisory")
        with patch(
            "agent.tools.execution_tools._notify_advisory",
            return_value="https://github.com/issue/4",
        ):
            result = quarantine_artifact(rationale="PQC failure", artifact_id="art-1")
        assert result["executed"] is False

    def test_enforce_creates_issue(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.create_issue",
            new_callable=AsyncMock,
            return_value=GitHubResult(
                ok=True, status_code=201, url="https://github.com/issue/5"
            ),
        ):
            result = quarantine_artifact(rationale="PQC failure", artifact_id="art-1")

        assert result["action"] == "QUARANTINE"
        assert result["executed"] is True

    def test_enforce_issue_failure_failopen(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.create_issue",
            new_callable=AsyncMock,
            return_value=GitHubResult(ok=False, error="auth failed"),
        ):
            result = quarantine_artifact(rationale="PQC failure", artifact_id="art-1")

        assert result["executed"] is False


# ── ESCALATE (HITL) ─────────────────────────────────────────────────


class TestEscalateToHuman:
    """ESCALATE mode gating."""

    def test_shadow(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "shadow")
        result = escalate_to_human(rationale="Ambiguous signals", summary="Review")
        assert result["action"] == "ESCALATE"
        assert result["executed"] is False

    def test_advisory_creates_issue(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "advisory")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.create_issue",
            new_callable=AsyncMock,
            return_value=GitHubResult(
                ok=True, status_code=201, url="https://github.com/issue/6"
            ),
        ):
            result = escalate_to_human(rationale="Ambiguous", summary="Review")

        assert result["executed"] is False  # advisory never executes
        assert "issue/6" in (result.get("issue_url") or "")

    def test_enforce_creates_and_executes(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.create_issue",
            new_callable=AsyncMock,
            return_value=GitHubResult(
                ok=True, status_code=201, url="https://github.com/issue/7"
            ),
        ):
            result = escalate_to_human(rationale="Ambiguous", summary="Review")

        assert result["executed"] is True

    def test_enforce_issue_failure_failopen(self, monkeypatch):
        monkeypatch.setenv("COGNIOPS_MODE", "enforce")

        from agent.tools.github_client import GitHubResult

        with patch(
            "agent.tools.github_client.create_issue",
            new_callable=AsyncMock,
            return_value=GitHubResult(ok=False, error="404"),
        ):
            result = escalate_to_human(rationale="Test", summary="Test")

        assert result["executed"] is False


# ── Default mode ─────────────────────────────────────────────────────


class TestDefaultMode:
    """COGNIOPS_MODE defaults to shadow when not set."""

    def test_default_is_shadow(self, monkeypatch):
        monkeypatch.delenv("COGNIOPS_MODE", raising=False)
        result = no_action(rationale="test")
        assert result["mode"] == "shadow"

    def test_all_tools_shadow_by_default(self, monkeypatch):
        monkeypatch.delenv("COGNIOPS_MODE", raising=False)
        for fn in [
            no_action,
            block_deployment,
            rollback_deployment,
            quarantine_artifact,
            escalate_to_human,
        ]:
            result = fn(rationale="test")
            assert result["executed"] is False
            assert result["mode"] == "shadow"

"""
Tests for GitHub API client (Step 4).

All tests mock httpx — never call the real GitHub API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.github_client import (
    GitHubResult,
    create_issue,
    dispatch_workflow,
)


def _mock_httpx_client(mock_resp):
    """Build a mock httpx.AsyncClient context manager returning *mock_resp*."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ── dispatch_workflow ────────────────────────────────────────────────


class TestDispatchWorkflow:
    """Verify workflow_dispatch API interactions."""

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_resp.text = ""

        with patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)):
            result = await dispatch_workflow(
                "s3_edge_rollback.yml", inputs={"run_id": "123"}
            )

        assert result.ok is True
        assert result.status_code == 204

    @pytest.mark.asyncio
    async def test_no_repo(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        result = await dispatch_workflow("test.yml")
        assert result.ok is False
        assert "GITHUB_REPOSITORY" in (result.error or "")

    @pytest.mark.asyncio
    async def test_no_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        result = await dispatch_workflow("test.yml")
        assert result.ok is False
        assert "GITHUB_TOKEN" in (result.error or "")

    @pytest.mark.asyncio
    async def test_http_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = "Unprocessable"

        with patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)):
            result = await dispatch_workflow("test.yml")

        assert result.ok is False
        assert result.status_code == 422

    @pytest.mark.asyncio
    async def test_network_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=ConnectionError("unreachable"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await dispatch_workflow("test.yml")

        assert result.ok is False
        assert "unreachable" in (result.error or "")


# ── create_issue ─────────────────────────────────────────────────────


class TestCreateIssue:
    """Verify issue creation API interactions."""

    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "html_url": "https://github.com/myorg/myrepo/issues/42"
        }

        with patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)):
            result = await create_issue(
                title="[HITL] Review",
                body="Test body",
                labels=["cogniops"],
            )

        assert result.ok is True
        assert "issues/42" in result.url

    @pytest.mark.asyncio
    async def test_no_repo(self, monkeypatch):
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        result = await create_issue(title="Test", body="Body")
        assert result.ok is False

    @pytest.mark.asyncio
    async def test_no_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        result = await create_issue(title="Test", body="Body")
        assert result.ok is False

    @pytest.mark.asyncio
    async def test_http_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"

        with patch("httpx.AsyncClient", return_value=_mock_httpx_client(mock_resp)):
            result = await create_issue(title="Test", body="Body")

        assert result.ok is False
        assert result.status_code == 403

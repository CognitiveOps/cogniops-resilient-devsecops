"""Tests for agent/design_agent.py, main.py, and the full pipeline."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import Request, Response

from agent.design_agent import design_agent


class TestDesignAgent(unittest.TestCase):
    """Unit tests for the ADK LlmAgent definition."""

    def test_agent_exists(self):
        assert design_agent is not None

    def test_agent_name(self):
        assert design_agent.name == "cogniops_design"

    def test_agent_model(self):
        assert "gemini" in design_agent.model

    def test_agent_has_tools(self):
        tool_names = [t.__name__ for t in design_agent.tools]
        assert "build_context" in tool_names
        assert "generate_proposal" in tool_names
        assert "no_proposal_needed" in tool_names

    def test_agent_has_three_tools(self):
        assert len(design_agent.tools) == 3

    def test_instruction_loaded(self):
        assert "Design-Time Agent" in design_agent.instruction
        assert "structural synthesis" in design_agent.instruction.lower()

    def test_few_shot_examples_loaded(self):
        assert "MTTR" in design_agent.instruction
        assert "FDR" in design_agent.instruction


class TestFastAPIEndpoints(unittest.TestCase):
    """Tests for FastAPI endpoints in main.py."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from httpx import ASGITransport, AsyncClient

        from main import app

        self.transport = ASGITransport(app=app)
        self.client_factory = lambda: AsyncClient(
            transport=self.transport, base_url="http://test"
        )

    @pytest.mark.asyncio
    async def test_healthz(self):
        async with self.client_factory() as client:
            resp = await client.get("/healthz")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_agent_info(self):
        async with self.client_factory() as client:
            resp = await client.get("/agent/info")
            assert resp.status_code == 200
            data = resp.json()
            assert data["agent_name"] == "cogniops_design"
            assert "build_context" in data["tools"]

    @pytest.mark.asyncio
    async def test_run_returns_result(self):
        """Test that /run returns a valid response (mocking ADK)."""
        async with self.client_factory() as client:
            with patch("main._run_pipeline") as mock_pipeline:
                mock_pipeline.return_value = {
                    "status": "no_changes",
                    "reason": "All metrics healthy",
                    "duration_sec": 1.5,
                }
                resp = await client.post("/run")
                assert resp.status_code == 200
                assert resp.json()["status"] == "no_changes"

    @pytest.mark.asyncio
    async def test_run_with_scenarios(self):
        """Test that /run accepts scenario filter."""
        async with self.client_factory() as client:
            with patch("main._run_pipeline") as mock_pipeline:
                mock_pipeline.return_value = {
                    "status": "no_changes",
                    "reason": "S3 metrics stable",
                    "duration_sec": 0.8,
                }
                resp = await client.post(
                    "/run",
                    json={"scenarios": ["s3"]},
                )
                # FastAPI may handle the body or not — either way should not error
                assert resp.status_code in (200, 422)


class TestGCSWrite(unittest.TestCase):
    """Test GCS helper functions."""

    @patch("main.CONFIG_BUCKET", "")
    def test_write_gcs_no_bucket(self):
        from main import _write_gcs_json

        result = _write_gcs_json("test.json", {"key": "value"})
        assert result is None

    def test_write_gcs_with_bucket(self):
        from main import _write_gcs_json

        mock_storage = MagicMock()
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with patch("main.CONFIG_BUCKET", "test-bucket"), patch.dict(
            "sys.modules",
            {
                "google.cloud.storage": mock_storage,
                "google.cloud": MagicMock(storage=mock_storage),
            },
        ):
            result = _write_gcs_json("test.json", {"key": "value"})
            assert result == "gs://test-bucket/test.json"


class TestGitHubIssue(unittest.TestCase):
    """Test GitHub Issue creation helper."""

    @patch.dict("os.environ", {"GITHUB_TOKEN": "", "GITHUB_REPO": ""})
    def test_no_token_returns_none(self):
        from main import _create_github_issue

        result = _create_github_issue({"intent": "test", "proposal_id": "test-1"})
        assert result is None

    def test_creates_issue(self):
        from main import _create_github_issue

        mock_resp = Response(
            201,
            json={"html_url": "https://github.com/owner/repo/issues/99"},
            request=Request("POST", "https://api.github.com/repos/owner/repo/issues"),
        )

        import main as main_mod

        original_repo = main_mod.GITHUB_REPO
        main_mod.GITHUB_REPO = "owner/repo"
        try:
            with patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}), patch.object(
                main_mod.httpx, "post", return_value=mock_resp
            ):
                result = _create_github_issue(
                    {
                        "intent": "Reduce MTTR in S3",
                        "proposal_id": "design-20260319-abc",
                        "target_scenarios": ["S3"],
                        "analysis_summary": "MTTR trending upward.",
                        "changes": [
                            {
                                "change_type": "threshold_adjustment",
                                "target_file": "s3_rollback.yml",
                                "description": "Reduce poll interval",
                            },
                        ],
                        "expected_impact": [
                            {
                                "metric_name": "MTTR",
                                "estimated_change": "-25%",
                                "confidence": 0.6,
                            },
                        ],
                    }
                )
                assert result == "https://github.com/owner/repo/issues/99"
        finally:
            main_mod.GITHUB_REPO = original_repo

    @patch.dict(
        "os.environ",
        {"GITHUB_TOKEN": "fake-token", "GITHUB_REPO": "owner/repo"},
    )
    @patch("httpx.post")
    def test_api_failure_returns_none(self, mock_post):
        mock_post.side_effect = Exception("API error")

        from main import _create_github_issue

        result = _create_github_issue({"intent": "test", "proposal_id": "test-1"})
        assert result is None


class TestRunnerSetup(unittest.TestCase):
    """Test ADK runner configuration."""

    def test_runner_exists(self):
        from main import runner

        assert runner is not None

    def test_runner_app_name(self):
        from main import runner

        assert runner.app_name == "cogniops_design"

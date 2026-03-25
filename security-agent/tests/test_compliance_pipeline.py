"""Tests for the ADK compliance agent and main pipeline endpoint.

Uses mocked NIST feeds and ADK InMemoryRunner with mocked LLM.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from models.schemas import FeedEntry, FeedSource


# ── Healthz / Info ───────────────────────────────────────────────────


class TestHealthz:
    @pytest.mark.asyncio
    async def test_healthz(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/healthz")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["agent"] == "security-compliance"

    @pytest.mark.asyncio
    async def test_agent_info(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/agent/info")

        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_name"] == "cogniops_compliance_planner"
        assert "evaluate_and_propose" in data["tools"]
        assert "no_proposal_needed" in data["tools"]


# ── Pipeline: No Updates ─────────────────────────────────────────────


class TestPipelineNoUpdates:
    @pytest.mark.asyncio
    async def test_no_feed_updates(self):
        """When feeds return empty → pipeline returns no_updates."""
        with (
            patch("main.ingest_feeds", new_callable=AsyncMock, return_value=[]),
            patch(
                "main._get_last_check",
                return_value=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            patch("main._save_last_check"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/run")

        assert resp.status_code == 200
        assert resp.json()["status"] == "no_updates"

    @pytest.mark.asyncio
    async def test_no_relevant_changes(self):
        """When feed has entries but none differ from current YAML → no_changes."""
        feed = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 5",  # same as YAML
            ),
        ]
        yaml_data = {
            "mappings": {
                "BLOCK": [{"ref": "NIST SP 800-53 CM-3", "revision": "Rev. 5"}],
            }
        }
        with (
            patch("main.ingest_feeds", new_callable=AsyncMock, return_value=feed),
            patch(
                "main._get_last_check",
                return_value=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            patch("main._save_last_check"),
            patch("main._load_current_yaml", return_value=yaml_data),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/run")

        assert resp.status_code == 200
        assert resp.json()["status"] == "no_changes"


# ── Pipeline: With Changes (Mocked LLM) ─────────────────────────────


class TestPipelineWithChanges:
    @pytest.mark.asyncio
    async def test_proposal_created(self):
        """When feed has changes, pipeline should produce a proposal."""
        feed = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 6",
                change_summary="Added supply chain provisions",
            ),
        ]
        yaml_data = {
            "mappings": {
                "BLOCK": [
                    {
                        "ref": "NIST SP 800-53 CM-3",
                        "title": "Configuration Change Control",
                        "revision": "Rev. 5",
                    },
                ],
                "NO_OP": [],
            }
        }

        # Mock the ADK runner to return a tool result
        mock_adk_event = MagicMock()
        mock_part = MagicMock()
        mock_part.function_response = MagicMock()
        mock_part.function_response.response = {
            "status": "proposal_ready",
            "impact_assessment": "CM-3 Rev.6 adds supply chain scope. Affects S1 CI/CD pipeline security and SS1 policy audit.",
            "confidence": 0.85,
            "decision_type_assignments": {"BLOCK": ["SP 800-53 CM-3"]},
            "rego_suggestions": [
                "Consider adding supply chain check to BLOCK threshold"
            ],
        }
        mock_adk_event.content = MagicMock()
        mock_adk_event.content.parts = [mock_part]

        async def mock_run_async(**kwargs):
            yield mock_adk_event

        with (
            patch("main.ingest_feeds", new_callable=AsyncMock, return_value=feed),
            patch(
                "main._get_last_check",
                return_value=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            patch("main._save_last_check"),
            patch("main._load_current_yaml", return_value=yaml_data),
            patch("main.enrich_diff", new_callable=AsyncMock, side_effect=lambda d: d),
            patch.object(app.state if hasattr(app, "state") else app, "__dict__", {}),
            patch("main.runner") as mock_runner,
            patch("main._write_gcs_json", return_value=True),
            patch(
                "main._create_github_issue",
                return_value="https://github.com/test/issues/1",
            ),
        ):
            mock_runner.run_async = mock_run_async

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/run")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "proposal_created"
        assert data["valid"] is True
        assert data["confidence"] == 0.85
        assert data["updated_entries"] == 1

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        """When ADK runner fails, pipeline should still produce a fallback proposal."""
        feed = [
            FeedEntry(
                source=FeedSource.NIST_SP800_53,
                ref_id="SP 800-53 CM-3",
                latest_revision="Rev. 6",
                change_summary="Updated control",
            ),
        ]
        yaml_data = {
            "mappings": {
                "BLOCK": [
                    {"ref": "NIST SP 800-53 CM-3", "revision": "Rev. 5"},
                ],
            }
        }

        async def mock_run_async_fail(**kwargs):
            raise RuntimeError("Gemini API unavailable")
            yield  # pragma: no cover — makes this an async generator

        with (
            patch("main.ingest_feeds", new_callable=AsyncMock, return_value=feed),
            patch(
                "main._get_last_check",
                return_value=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
            patch("main._save_last_check"),
            patch("main._load_current_yaml", return_value=yaml_data),
            patch("main.enrich_diff", new_callable=AsyncMock, side_effect=lambda d: d),
            patch("main.runner") as mock_runner,
            patch("main._write_gcs_json", return_value=True),
            patch("main._create_github_issue", return_value=None),
        ):
            mock_runner.run_async = mock_run_async_fail

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/run")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "proposal_created"
        assert data["confidence"] == 0.3  # fallback confidence


# ── ADK Agent Tool Tests ─────────────────────────────────────────────


class TestADKTools:
    def test_evaluate_and_propose(self):
        from agent.compliance_agent import evaluate_and_propose

        result = evaluate_and_propose(
            impact_assessment="Test impact for S1 CI/CD",
            confidence=0.8,
            decision_type_assignments={"BLOCK": ["SP 800-53 CM-3"]},
            rego_suggestions=["Lower threshold"],
        )

        assert result["status"] == "proposal_ready"
        assert result["confidence"] == 0.8
        assert "BLOCK" in result["decision_type_assignments"]

    def test_evaluate_clamps_confidence(self):
        from agent.compliance_agent import evaluate_and_propose

        result = evaluate_and_propose(
            impact_assessment="Test",
            confidence=5.0,
            decision_type_assignments={},
        )
        assert result["confidence"] == 1.0

    def test_no_proposal_needed(self):
        from agent.compliance_agent import no_proposal_needed

        result = no_proposal_needed(reason="No changes detected")

        assert result["status"] == "no_op"
        assert "No changes" in result["reason"]

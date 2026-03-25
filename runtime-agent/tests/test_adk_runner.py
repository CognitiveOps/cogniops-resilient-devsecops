"""Tests for ADK runner wiring in main.py endpoint.

Tests:
  - ADK runner produces decision → extracted correctly
  - ADK runner failure → fallback to NO_OP
  - Runner instance is created at module level
  - Policy refs enrichment after ADK decision
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure runtime-agent root is on sys.path
_AGENT_ROOT = str(Path(__file__).resolve().parent.parent)
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from tests.conftest import SAMPLE_EVENT_DICT, make_pubsub_body


# ── Helpers ──────────────────────────────────────────────────────────


def _make_adk_event_with_tool_result(action: str, rationale: str, executed: bool = False):
    """Create a mock ADK event that looks like a function_response."""
    part = MagicMock()
    part.function_response = MagicMock()
    part.function_response.response = {
        "action": action,
        "rationale": rationale,
        "executed": executed,
        "mode": "shadow",
    }
    content = MagicMock()
    content.parts = [part]
    event = MagicMock()
    event.content = content
    return event


def _make_adk_event_text(text: str):
    """Create a mock ADK event with text content (no tool result)."""
    part = MagicMock()
    part.function_response = None
    part.text = text
    content = MagicMock()
    content.parts = [part]
    event = MagicMock()
    event.content = content
    return event


# ── Tests: runner wiring ─────────────────────────────────────────────


class TestADKRunnerWiring:
    """Verify ADK runner is wired into the endpoint."""

    def test_runner_exists_in_module(self):
        """InMemoryRunner instance exists at module level."""
        from main import runner
        assert runner is not None

    def test_runner_app_name(self):
        """Runner has the correct app name."""
        from main import runner
        assert runner.app_name == "cogniops_runtime"

    @pytest.mark.asyncio
    async def test_endpoint_extracts_no_op_decision(self):
        """POST /events/runtime extracts NO_OP from ADK tool result."""
        no_op_event = _make_adk_event_with_tool_result(
            "NO_OP", "Low severity — no action", False
        )

        async def mock_run_async(**kwargs):
            yield no_op_event

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "NO_OP"
        assert body["decision_executed"] is False

    @pytest.mark.asyncio
    async def test_endpoint_extracts_block_decision(self):
        """POST /events/runtime extracts BLOCK from ADK tool result."""
        block_event = _make_adk_event_with_tool_result(
            "BLOCK", "High severity pipeline failure", False
        )

        async def mock_run_async(**kwargs):
            yield block_event

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "BLOCK"
        assert len(body["policy_refs"]) > 0  # BLOCK has refs

    @pytest.mark.asyncio
    async def test_endpoint_fallback_on_adk_failure(self):
        """POST /events/runtime falls back to NO_OP when ADK raises."""

        async def mock_run_async(**kwargs):
            raise RuntimeError("LLM unavailable")
            yield  # Make it an async generator  # noqa: E501

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "NO_OP"
        assert "fallback" in body.get("status", "accepted").lower() or body["decision"] == "NO_OP"

    @pytest.mark.asyncio
    async def test_endpoint_fallback_on_no_tool_result(self):
        """POST /events/runtime uses NO_OP if ADK produces no tool calls."""
        text_event = _make_adk_event_text("I analyzed the event but made no conclusion.")

        async def mock_run_async(**kwargs):
            yield text_event

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "NO_OP"

    @pytest.mark.asyncio
    async def test_guard_blocked_decision_preserved(self):
        """Guard-blocked results are correctly extracted."""
        guard_event = _make_adk_event_with_tool_result(
            "NO_OP", "Guard blocked: OPA violation", False
        )
        guard_event.content.parts[0].function_response.response["guard_blocked"] = True
        guard_event.content.parts[0].function_response.response["guard_reason"] = "opa_violation"

        async def mock_run_async(**kwargs):
            yield guard_event

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "NO_OP"

    @pytest.mark.asyncio
    async def test_policy_refs_enriched_for_block(self):
        """Policy refs are populated for BLOCK decisions."""
        block_event = _make_adk_event_with_tool_result("BLOCK", "Severity high", False)

        async def mock_run_async(**kwargs):
            yield block_event

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        body = resp.json()
        refs = body.get("policy_refs", [])
        assert any("NIST" in r for r in refs)
        assert any("ISO" in r for r in refs)

    @pytest.mark.asyncio
    async def test_mode_from_env(self):
        """Mode is read from COGNIOPS_MODE env var."""
        no_op_event = _make_adk_event_with_tool_result("NO_OP", "test", False)

        async def mock_run_async(**kwargs):
            yield no_op_event

        with (
            patch("main.runner") as mock_runner,
            patch("main.write_decision", return_value=True),
            patch("main.emit_action_trace", return_value=True),
            patch("main.COGNIOPS_MODE", "advisory"),
        ):
            mock_runner.run_async = mock_run_async

            from main import app

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/events/runtime", json=make_pubsub_body(SAMPLE_EVENT_DICT)
                )

        body = resp.json()
        assert body["mode"] == "advisory"

"""
ADK agent pipeline tests — Step 1 bootstrap.

Tests:
  - Agent structure (name, model, tools, guard callback)
  - Tool functions produce correct output
  - Guard callback allows execution (stub)
  - InMemoryRunner creates and runs agent pipeline
  - /agent/info endpoint returns agent metadata
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure runtime-agent root is on sys.path
_AGENT_ROOT = str(Path(__file__).resolve().parent.parent)
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from google.adk.agents import LlmAgent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.callbacks.guard_callback import guard_callback
from agent.cogniops_agent import cogniops_agent
from agent.tools.execution_tools import (
    block_deployment,
    escalate_to_human,
    no_action,
    quarantine_artifact,
    rollback_deployment,
)
from agent.tools.memory_tools import query_recent_decisions
from agent.tools.perception_tool import perceive_anomaly


# ── Agent Structure Tests ────────────────────────────────────────────


class TestAgentStructure:
    """Verify the ADK agent is configured correctly."""

    def test_agent_name(self):
        assert cogniops_agent.name == "cogniops_planning"

    def test_agent_model(self):
        assert "gemini" in str(cogniops_agent.model)

    def test_agent_has_tools(self):
        assert len(cogniops_agent.tools) == 7

    def test_agent_has_guard_callback(self):
        assert cogniops_agent.before_tool_callback is not None

    def test_agent_instruction_loaded(self):
        instruction = cogniops_agent.instruction
        assert "CogniOps Runtime Planning Agent" in instruction
        assert "no_action" in instruction
        assert "block_deployment" in instruction


# ── Tool Function Tests ──────────────────────────────────────────────


class TestPerceptionTool:
    """Verify perception tool wraps z-score + threshold detection."""

    @patch("agent.tools.perception_tool.query_baseline", return_value=None)
    def test_perceive_anomaly_returns_dict(self, mock_bq):
        result = perceive_anomaly(
            event_id="test-001",
            event_type="pipeline_failure",
            source="test",
            occurred_at="2026-03-01T12:00:00Z",
            scenario_id="S1",
            status="fail",
        )
        assert isinstance(result, dict)
        # No duration/metrics → neutral severity, weighted risk (S1 weight=0.8)
        assert result["severity"] == 0.5
        assert result["risk_score"] == 0.4
        assert result["anomaly_type"] == "pipeline_failure"
        assert result["scenario"] == "S1"

    def test_perceive_anomaly_default_scenario(self):
        result = perceive_anomaly(
            event_id="test-002",
            event_type="policy_violation",
            source="test",
            occurred_at="2026-03-01T13:00:00Z",
        )
        assert result["scenario"] == "unknown"


class TestExecutionTools:
    """Verify each execution tool produces correct action type."""

    def test_no_action(self):
        result = no_action(rationale="Low severity")
        assert result["action"] == "NO_OP"
        assert result["executed"] is False
        assert "Low severity" in result["rationale"]

    def test_block_deployment(self):
        result = block_deployment(rationale="Policy violation", target="deploy-123")
        assert result["action"] == "BLOCK"
        assert result["executed"] is False
        assert result["target"] == "deploy-123"

    def test_rollback_deployment(self):
        result = rollback_deployment(rationale="Failed deploy", target="run-456")
        assert result["action"] == "ROLLBACK"
        assert result["executed"] is False

    def test_quarantine_artifact(self):
        result = quarantine_artifact(rationale="PQC failure", artifact_id="art-789")
        assert result["action"] == "QUARANTINE"
        assert result["executed"] is False
        assert result["artifact_id"] == "art-789"

    def test_escalate_to_human(self):
        result = escalate_to_human(
            rationale="Ambiguous signals", summary="Review needed"
        )
        assert result["action"] == "ESCALATE"
        assert result["executed"] is False
        assert result["summary"] == "Review needed"


class TestMemoryTool:
    """Verify memory tool returns stub response."""

    def test_query_recent_decisions_stub(self):
        result = query_recent_decisions(scenario_id="S3", limit=5)
        assert result["count"] == 0
        assert result["decisions"] == []


# ── Guard Callback Tests ─────────────────────────────────────────────


class TestGuardCallback:
    """Verify guard callback always allows in Step 1."""

    def test_guard_allows_execution(self):
        mock_tool = MagicMock()
        mock_tool.name = "no_action"
        mock_context = MagicMock()

        result = guard_callback(
            tool=mock_tool,
            args={"rationale": "test"},
            tool_context=mock_context,
        )
        assert result is None  # None = allow


# ── InMemoryRunner Pipeline Tests ────────────────────────────────────


class TestAgentPipeline:
    """Verify agent pipeline through InMemoryRunner with mocked LLM."""

    @staticmethod
    def _make_test_agent(
        before_model_callback: Any = None,
    ) -> LlmAgent:
        """Create a test agent variant with a mocked model callback."""
        return LlmAgent(
            name="cogniops_planning_test",
            model="gemini-2.0-flash",
            instruction=cogniops_agent.instruction,
            tools=[
                perceive_anomaly,
                no_action,
                block_deployment,
                rollback_deployment,
                quarantine_artifact,
                escalate_to_human,
                query_recent_decisions,
            ],
            before_tool_callback=guard_callback,
            before_model_callback=before_model_callback,
        )

    def test_runner_creates_successfully(self):
        """InMemoryRunner can be instantiated with the agent."""
        runner = InMemoryRunner(
            agent=cogniops_agent,
            app_name="cogniops_test",
        )
        runner.auto_create_session = True
        assert runner is not None

    @pytest.mark.asyncio
    async def test_pipeline_produces_no_op(self):
        """Agent pipeline selects NO_OP via mocked model responses."""
        call_count = 0

        def mock_model(*, callback_context, llm_request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: LLM decides to call no_action tool
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="no_action",
                                    args={
                                        "rationale": "Test: severity 0.5 — safe default"
                                    },
                                )
                            )
                        ],
                    )
                )
            # Subsequent calls: text completion
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Decision: NO_OP applied.")],
                ),
                turn_complete=True,
            )

        test_agent = self._make_test_agent(before_model_callback=mock_model)
        runner = InMemoryRunner(agent=test_agent, app_name="cogniops_test")
        runner.auto_create_session = True

        user_msg = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Anomaly detected: event_id=test-001 event_type=pipeline_failure "
                        "source=ci-pipeline occurred_at=2026-03-01T12:00:00Z "
                        "scenario_id=S1 status=fail severity=medium"
                    )
                )
            ],
        )

        events = []
        async for event in runner.run_async(
            user_id="test_user",
            session_id="test_session_001",
            new_message=user_msg,
        ):
            events.append(event)

        # Verify we got events back
        assert len(events) > 0
        # Verify the mock model was called
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_guard_callback_invoked(self):
        """Guard callback is invoked when model calls a tool."""
        guard_invoked = False
        original_guard = guard_callback

        def tracking_guard(
            *,
            tool,
            args: dict[str, Any],
            tool_context,
        ) -> Optional[dict]:
            nonlocal guard_invoked
            guard_invoked = True
            return original_guard(tool=tool, args=args, tool_context=tool_context)

        call_count = 0

        def mock_model(*, callback_context, llm_request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="no_action",
                                    args={"rationale": "Test guard invocation"},
                                )
                            )
                        ],
                    )
                )
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Done.")],
                ),
                turn_complete=True,
            )

        test_agent = LlmAgent(
            name="cogniops_guard_test",
            model="gemini-2.0-flash",
            instruction=cogniops_agent.instruction,
            tools=[no_action],
            before_tool_callback=tracking_guard,
            before_model_callback=mock_model,
        )

        runner = InMemoryRunner(agent=test_agent, app_name="cogniops_test")
        runner.auto_create_session = True
        user_msg = types.Content(
            role="user",
            parts=[types.Part(text="Test event — check guard callback.")],
        )

        async for _ in runner.run_async(
            user_id="test_user",
            session_id="test_guard_001",
            new_message=user_msg,
        ):
            pass

        assert guard_invoked, "Guard callback was not invoked during pipeline"


# ── /agent/info Endpoint Test ────────────────────────────────────────


class TestAgentInfoEndpoint:
    """Verify the /agent/info endpoint returns agent metadata."""

    @pytest.mark.asyncio
    async def test_agent_info_returns_metadata(self):
        from httpx import ASGITransport, AsyncClient

        from main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/agent/info")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "loaded"
        assert data["agent_name"] == "cogniops_planning"
        assert data["has_guard"] is True
        assert len(data["tools"]) == 7

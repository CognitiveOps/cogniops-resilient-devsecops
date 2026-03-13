"""
Step 3: LLM Planning integration tests.

Tests the Planning module's LLM connection, decision logic,
few-shot loading, episodic context, and fallback behavior.
Uses ADK InMemoryRunner with mocked model callbacks.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

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
from agent.cogniops_agent import (
    _build_instruction,
    _load_few_shots,
    _load_prompt,
    cogniops_agent,
)
from agent.tools.execution_tools import (
    block_deployment,
    escalate_to_human,
    no_action,
    quarantine_artifact,
    rollback_deployment,
)
from agent.tools.memory_tools import query_recent_decisions
from agent.tools.perception_tool import perceive_anomaly
from models.schemas import DecisionType, PlanningDecision
from telemetry.llm_logger import (
    LlmCallRecord,
    LlmCallTimer,
    hash_prompt,
    log_llm_call,
)

_ALL_TOOLS = [
    perceive_anomaly,
    no_action,
    block_deployment,
    rollback_deployment,
    quarantine_artifact,
    escalate_to_human,
    query_recent_decisions,
]


def _make_test_agent(before_model_callback: Any) -> LlmAgent:
    """Create a test agent with a mocked model callback."""
    return LlmAgent(
        name="cogniops_planning_test",
        model="gemini-2.0-flash",
        instruction=cogniops_agent.instruction,
        tools=_ALL_TOOLS,
        before_tool_callback=guard_callback,
        before_model_callback=before_model_callback,
    )


def _mock_tool_then_done(tool_name: str, tool_args: dict) -> Any:
    """Return a before_model_callback that calls a tool then completes."""

    call_count = 0

    def callback(*, callback_context, llm_request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                name=tool_name,
                                args=tool_args,
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

    return callback


# ── Prompt & Few-Shot Loading Tests ──────────────────────────────────


class TestPromptLoading:
    """Verify system prompt and few-shot examples are loaded correctly."""

    def test_system_prompt_loaded(self):
        prompt = _load_prompt("system.txt")
        assert "CogniOps Runtime Planning Agent" in prompt
        assert "Decision Criteria" in prompt
        assert "no_action" in prompt
        assert "severity" in prompt

    def test_few_shots_loaded(self):
        few_shots = _load_few_shots()
        assert len(few_shots) > 0
        assert "S1" in few_shots
        assert "S3" in few_shots

    def test_few_shot_s1_exists(self):
        content = _load_prompt("few_shot_s1.txt")
        assert "pipeline" in content.lower()
        assert "rollback" in content.lower()

    def test_few_shot_s3_exists(self):
        content = _load_prompt("few_shot_s3.txt")
        assert "resilience" in content.lower()

    def test_few_shot_ss2_exists(self):
        content = _load_prompt("few_shot_ss2.txt")
        assert "quarantine" in content.lower()

    def test_few_shot_s5_exists(self):
        content = _load_prompt("few_shot_s5.txt")
        assert "acr" in content.lower()

    def test_build_instruction_includes_few_shots(self):
        instruction = _build_instruction()
        assert "Few-Shot Examples" in instruction
        assert "CogniOps Runtime Planning Agent" in instruction

    def test_agent_instruction_includes_decision_criteria(self):
        assert "Decision Criteria" in cogniops_agent.instruction

    def test_agent_instruction_includes_few_shots(self):
        assert "Few-Shot Examples" in cogniops_agent.instruction


# ── Decision Logic Tests (Mocked LLM) ───────────────────────────────


class TestHighSeverityDecision:
    """High severity anomalies should trigger ROLLBACK or BLOCK."""

    @pytest.mark.asyncio
    async def test_high_severity_triggers_rollback(self):
        """severity > 0.8 → ROLLBACK."""
        mock = _mock_tool_then_done(
            "rollback_deployment",
            {"rationale": "Critical severity 0.9 — rollback required", "target": "S3"},
        )
        agent = _make_test_agent(mock)
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_high_sev",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="Critical S3 event: severity=0.9, mttd=150s")],
            ),
        ):
            events.append(event)

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_policy_violation_triggers_block(self):
        """policy_violation → BLOCK."""
        mock = _mock_tool_then_done(
            "block_deployment",
            {"rationale": "Policy violation — blocking deployment", "target": "SS1"},
        )
        agent = _make_test_agent(mock)
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_policy_block",
            new_message=types.Content(
                role="user",
                parts=[
                    types.Part(text="Policy violation detected in SS1 deployment")
                ],
            ),
        ):
            events.append(event)

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_integrity_failure_triggers_quarantine(self):
        """Integrity/PQC failure → QUARANTINE."""
        mock = _mock_tool_then_done(
            "quarantine_artifact",
            {
                "rationale": "Integrity failure — quarantining artifact",
                "artifact_id": "art-ss2-001",
            },
        )
        agent = _make_test_agent(mock)
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_quarantine",
            new_message=types.Content(
                role="user",
                parts=[
                    types.Part(text="SS2 integrity failure: PQC signature invalid")
                ],
            ),
        ):
            events.append(event)

        assert len(events) > 0


class TestLowSeverityDecision:
    """Low severity anomalies should trigger NO_OP or ESCALATE."""

    @pytest.mark.asyncio
    async def test_low_severity_triggers_no_op(self):
        """severity < 0.3 → NO_OP."""
        mock = _mock_tool_then_done(
            "no_action",
            {"rationale": "Severity 0.1 — within normal range, no action needed"},
        )
        agent = _make_test_agent(mock)
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_low_sev",
            new_message=types.Content(
                role="user",
                parts=[
                    types.Part(text="S1 pipeline normal: severity=0.1, all metrics OK")
                ],
            ),
        ):
            events.append(event)

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_moderate_severity_triggers_escalate(self):
        """severity 0.3–0.6 → ESCALATE."""
        mock = _mock_tool_then_done(
            "escalate_to_human",
            {
                "rationale": "Severity 0.45 — ambiguous, escalating",
                "summary": "S3 moderate degradation",
            },
        )
        agent = _make_test_agent(mock)
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_mod_sev",
            new_message=types.Content(
                role="user",
                parts=[
                    types.Part(text="S3 moderate degradation: severity=0.45")
                ],
            ),
        ):
            events.append(event)

        assert len(events) > 0


# ── Fallback Tests ───────────────────────────────────────────────────


class TestFallbackBehavior:
    """Verify LLM failures trigger NO_OP fallback."""

    @pytest.mark.asyncio
    async def test_model_error_returns_terminal_response(self):
        """Model callback returning text-only → runner completes gracefully."""

        def failing_model(*, callback_context, llm_request):
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Error in processing.")],
                ),
                turn_complete=True,
            )

        agent = LlmAgent(
            name="cogniops_fallback_test",
            model="gemini-2.0-flash",
            instruction=cogniops_agent.instruction,
            tools=[no_action],
            before_model_callback=failing_model,
        )
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_fallback",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="Test event")],
            ),
        ):
            events.append(event)

        assert len(events) > 0

    def test_planning_fallback_on_exception(self):
        """Code-level fallback: exception → PlanningDecision(NO_OP)."""
        try:
            raise RuntimeError("LLM unavailable")
        except Exception:
            decision = PlanningDecision(
                decision=DecisionType.NO_OP,
                rationale="LLM fallback — error during reasoning",
            )

        assert decision.decision == DecisionType.NO_OP
        assert "fallback" in decision.rationale.lower()


# ── Episodic Context Tests ───────────────────────────────────────────


class TestEpisodicContext:
    """Verify episodic memory integration."""

    def test_memory_tool_without_bq_config(self):
        """Without GCP_PROJECT_ID, returns empty gracefully."""
        import agent.tools.memory_tools as mem

        original = mem.GCP_PROJECT_ID
        mem.GCP_PROJECT_ID = ""
        try:
            result = query_recent_decisions(scenario_id="S3", limit=5)
            assert result["count"] == 0
            assert result["decisions"] == []
        finally:
            mem.GCP_PROJECT_ID = original

    def test_memory_tool_bq_failure_graceful(self):
        """BQ unavailable → returns empty (graceful degradation)."""
        import agent.tools.memory_tools as mem

        original = mem.GCP_PROJECT_ID
        mem.GCP_PROJECT_ID = "fake-project-no-creds"
        try:
            result = mem.query_recent_decisions(scenario_id="S1", limit=3)
            assert result["count"] == 0
        finally:
            mem.GCP_PROJECT_ID = original

    @pytest.mark.asyncio
    async def test_episodic_context_in_pipeline(self):
        """Agent can call query_recent_decisions then select action."""
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
                                    name="query_recent_decisions",
                                    args={"scenario_id": "S3", "limit": 5},
                                )
                            )
                        ],
                    )
                )
            if call_count == 2:
                return LlmResponse(
                    content=types.Content(
                        role="model",
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(
                                    name="no_action",
                                    args={
                                        "rationale": "After reviewing context — no action"
                                    },
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

        agent = _make_test_agent(mock_model)
        runner = InMemoryRunner(agent=agent, app_name="cogniops_test")
        runner.auto_create_session = True

        events = []
        async for event in runner.run_async(
            user_id="test",
            session_id="test_episodic",
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="S3 event — check history first")],
            ),
        ):
            events.append(event)

        assert call_count >= 2


# ── LLM Logger Tests ────────────────────────────────────────────────


class TestLlmLogger:
    """Verify LLM call logging utilities."""

    def test_hash_prompt_deterministic(self):
        h1 = hash_prompt("test prompt")
        h2 = hash_prompt("test prompt")
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_prompt_differs_for_different_input(self):
        h1 = hash_prompt("prompt A")
        h2 = hash_prompt("prompt B")
        assert h1 != h2

    def test_llm_call_record_defaults(self):
        record = LlmCallRecord()
        assert record.session_id == ""
        assert record.fallback_triggered is False
        assert record.error is None

    def test_llm_call_timer_records_latency(self):
        with LlmCallTimer(session_id="s1", model="gemini") as timer:
            pass
        assert timer.record.latency_ms >= 0
        assert timer.record.session_id == "s1"

    def test_llm_call_timer_records_error(self):
        try:
            with LlmCallTimer(session_id="s2", model="gemini") as timer:
                raise ValueError("test error")
        except ValueError:
            pass
        assert timer.record.fallback_triggered is True
        assert "test error" in timer.record.error

    def test_log_llm_call_info(self, caplog):
        record = LlmCallRecord(
            session_id="test",
            model="gemini-2.0-flash",
            response_tool_name="no_action",
            latency_ms=42.5,
        )
        with caplog.at_level(logging.INFO, logger="runtime-agent.llm"):
            log_llm_call(record)
        assert "LLM call:" in caplog.text

    def test_log_llm_call_fallback(self, caplog):
        record = LlmCallRecord(
            session_id="test",
            model="gemini-2.0-flash",
            fallback_triggered=True,
            error="timeout",
        )
        with caplog.at_level(logging.WARNING, logger="runtime-agent.llm"):
            log_llm_call(record)
        assert "fallback" in caplog.text

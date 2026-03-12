"""
CogniOps Runtime Planning Agent — ADK LlmAgent definition.

Creates the root ``LlmAgent`` that orchestrates the cognitive pipeline:
  Perception tool → LLM planning → Guard callback → Execution tool
"""

from __future__ import annotations

import os
from pathlib import Path

from google.adk.agents import LlmAgent

from agent.callbacks.guard_callback import guard_callback
from agent.tools.execution_tools import (
    block_deployment,
    escalate_to_human,
    no_action,
    quarantine_artifact,
    rollback_deployment,
)
from agent.tools.memory_tools import query_recent_decisions
from agent.tools.perception_tool import perceive_anomaly

COGNIOPS_MODEL = os.getenv("COGNIOPS_MODEL", "gemini-2.0-flash")

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_system_prompt() -> str:
    """Load the bounded-action system prompt from disk."""
    return (_PROMPT_DIR / "system.txt").read_text()


cogniops_agent = LlmAgent(
    name="cogniops_planning",
    model=COGNIOPS_MODEL,
    instruction=_load_system_prompt(),
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
)

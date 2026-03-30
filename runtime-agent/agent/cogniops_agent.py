"""
CogniOps Runtime Planning Agent — ADK LlmAgent definition.

Creates the root ``LlmAgent`` that orchestrates the cognitive pipeline:
  Perception tool → LLM planning → Guard callback → Execution tool

Step 3: Connected to Vertex AI Gemini via ADK tool calling.
System prompt + few-shot examples loaded from agent/prompts/.
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

COGNIOPS_MODEL = os.getenv("COGNIOPS_MODEL", "gemini-2.5-flash")

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt file from the prompts directory."""
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


def _load_few_shots() -> str:
    """Load and concatenate all few-shot example files.

    Files are sorted alphabetically to ensure deterministic ordering.
    """
    few_shot_files = sorted(_PROMPT_DIR.glob("few_shot_*.txt"))
    if not few_shot_files:
        return ""
    sections = []
    for path in few_shot_files:
        sections.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(sections)


def _build_instruction() -> str:
    """Assemble the full system instruction: system prompt + few-shot examples."""
    system = _load_prompt("system.txt")
    few_shots = _load_few_shots()
    if few_shots:
        return f"{system}\n\n## Few-Shot Examples\n\n{few_shots}"
    return system


cogniops_agent = LlmAgent(
    name="cogniops_planning",
    model=COGNIOPS_MODEL,
    instruction=_build_instruction(),
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

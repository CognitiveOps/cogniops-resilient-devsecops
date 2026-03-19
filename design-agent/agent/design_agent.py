"""
CogniOps Design-Time Agent — ADK LlmAgent definition.

Pipeline:
  Context Builder (deterministic) → LLM Planning (this agent)
    → Proposal Generator (deterministic) → Validator (deterministic) → Output

The LlmAgent is the ONLY component that uses Gemini.
All other pipeline stages are deterministic Python.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from google.adk.agents import LlmAgent

from agent.tools.context_builder import build_context
from agent.tools.proposal_generator import generate_proposal, no_proposal_needed

logger = logging.getLogger("design-agent.design_agent")

COGNIOPS_MODEL = os.getenv("COGNIOPS_MODEL", "gemini-2.0-flash")

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt file from the prompts directory."""
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


def _load_few_shots() -> str:
    """Load and concatenate all few-shot example files."""
    few_shot_files = sorted(_PROMPT_DIR.glob("few_shot_*.txt"))
    if not few_shot_files:
        return ""
    sections = []
    for path in few_shot_files:
        sections.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(sections)


def _build_instruction() -> str:
    """Assemble the full system instruction: system prompt + few-shot examples."""
    system = _load_prompt("design_system.txt")
    few_shots = _load_few_shots()
    if few_shots:
        return f"{system}\n\n## Few-Shot Examples\n\n{few_shots}"
    return system


design_agent = LlmAgent(
    name="cogniops_design",
    model=COGNIOPS_MODEL,
    instruction=_build_instruction(),
    tools=[
        build_context,
        generate_proposal,
        no_proposal_needed,
    ],
)

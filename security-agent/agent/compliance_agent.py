"""
CogniOps Security Compliance Agent — ADK LlmAgent definition.

Pipeline:
  Feed Ingestion (deterministic) → Diff Engine (deterministic)
    → LLM Planning (this agent) → Validator (deterministic) → Output

The LlmAgent is the ONLY component that uses Gemini.
All other pipeline stages are deterministic Python.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from google.adk.agents import LlmAgent

logger = logging.getLogger("security-agent.compliance_agent")

COGNIOPS_MODEL = os.getenv("COGNIOPS_MODEL", "gemini-2.0-flash")

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt file from the prompts directory."""
    return (_PROMPT_DIR / name).read_text(encoding="utf-8")


# ── ADK Tool Functions ───────────────────────────────────────────────
# These are called by the LLM via function calling.
# The LLM receives the DiffReport as context and calls evaluate_and_propose
# with its structured analysis.


def evaluate_and_propose(
    impact_assessment: str,
    confidence: float,
    decision_type_assignments: dict[str, list[str]],
    rego_suggestions: list[str] | None = None,
) -> dict:
    """Evaluate compliance diff and produce a structured proposal.

    Args:
        impact_assessment: 2-5 sentence analysis of what changed and why it matters
            for CogniOps scenarios and metrics.
        confidence: Certainty score (0.0-1.0) that the mapping is correct.
        decision_type_assignments: Map of decision type → list of affected ref_ids.
            Example: {"BLOCK": ["SP 800-53 CM-3"], "QUARANTINE": ["SP 800-53 SI-7"]}
        rego_suggestions: Optional list of human-readable OPA policy suggestions.

    Returns:
        Structured result for proposal building.
    """
    return {
        "status": "proposal_ready",
        "impact_assessment": impact_assessment,
        "confidence": max(0.0, min(1.0, confidence)),
        "decision_type_assignments": decision_type_assignments or {},
        "rego_suggestions": rego_suggestions or [],
    }


def no_proposal_needed(reason: str) -> dict:
    """Signal that no compliance proposal is needed.

    Args:
        reason: Explanation of why no changes are required.

    Returns:
        NO_OP result.
    """
    return {
        "status": "no_op",
        "reason": reason,
    }


# ── Agent Definition ─────────────────────────────────────────────────

compliance_agent = LlmAgent(
    name="cogniops_compliance_planner",
    model=COGNIOPS_MODEL,
    instruction=_load_prompt("compliance_system.txt"),
    tools=[
        evaluate_and_propose,
        no_proposal_needed,
    ],
)

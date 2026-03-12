"""ADK before_tool_callback — policy guard for execution tools."""

from __future__ import annotations

import logging
from typing import Any, Optional

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger("runtime-agent.guard")


def guard_callback(
    *,
    tool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Policy guard invoked before every tool execution.

    In Step 1 this is a stub that always allows tool execution.
    Step 4 will add OPA policy re-check and PQC integrity verification.

    Args:
        tool: The ADK tool about to be executed.
        args: Arguments the LLM passed to the tool.
        tool_context: ADK tool context.

    Returns:
        None to allow execution, or dict to block (skip tool, use dict as result).
    """
    logger.info(
        "Guard check: tool=%s args=%s — ALLOWED (Step 1 stub)",
        tool.name,
        args,
    )
    return None

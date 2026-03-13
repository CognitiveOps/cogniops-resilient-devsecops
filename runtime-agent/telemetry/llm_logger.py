"""
LLM call logger — structured logging for every Gemini interaction.

Logs prompt hash, response tool call, latency, model version, and token count.
All data goes to Python logging (Cloud Logging in GCP).

Privacy: only SHA-256 prompt hashes are logged, never full prompt text.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

logger = logging.getLogger("runtime-agent.llm")


@dataclass
class LlmCallRecord:
    """Structured record of a single LLM call."""

    session_id: str = ""
    model: str = ""
    prompt_hash: str = ""
    response_tool_name: Optional[str] = None
    response_tool_args: Optional[dict[str, Any]] = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    fallback_triggered: bool = False
    error: Optional[str] = None


def hash_prompt(prompt: str) -> str:
    """SHA-256 hash of a prompt (privacy: don't log full prompt)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def log_llm_call(record: LlmCallRecord) -> None:
    """Log an LLM call record as structured JSON."""
    log_data = asdict(record)
    if record.fallback_triggered or record.error:
        logger.warning("LLM call (fallback): %s", log_data)
    else:
        logger.info("LLM call: %s", log_data)


class LlmCallTimer:
    """Context manager for timing LLM calls and recording metadata.

    Usage::

        with LlmCallTimer(session_id="s1", model="gemini-2.0-flash") as timer:
            # ... run ADK pipeline ...
            timer.record.response_tool_name = "rollback_deployment"
        # timer.record.latency_ms is automatically populated
    """

    def __init__(self, session_id: str = "", model: str = "") -> None:
        self.session_id = session_id
        self.model = model
        self._start: float = 0.0
        self.record = LlmCallRecord(session_id=session_id, model=model)

    def __enter__(self) -> "LlmCallTimer":
        self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> None:
        elapsed = (time.monotonic() - self._start) * 1000
        self.record.latency_ms = round(elapsed, 2)
        if exc_type is not None:
            self.record.fallback_triggered = True
            self.record.error = str(exc_val)
        log_llm_call(self.record)

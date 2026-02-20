"""
S5 Explainability & Human-in-the-Loop (HITL) kit.

This package provides reusable primitives that are:
- Benchmarked standalone by S5
- Reused by SS2 to avoid duplicated implementations
"""

from .schema import compute_acr, validate_action_trace
from .cloudevents import new_cloudevent
from .report import render_explanation_markdown, render_explanation_json
from .emit import emit_stage_event
from .approval import write_timestamp, read_timestamp, compute_approval_latency_sec

__all__ = [
    "compute_acr",
    "validate_action_trace",
    "new_cloudevent",
    "render_explanation_markdown",
    "render_explanation_json",
    "emit_stage_event",
    "write_timestamp",
    "read_timestamp",
    "compute_approval_latency_sec",
]


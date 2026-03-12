"""ADK tool for querying recent agent decisions (episodic memory)."""

from __future__ import annotations


def query_recent_decisions(scenario_id: str = "", limit: int = 5) -> dict:
    """Query recent agent decisions from BigQuery for context.

    Use this to check if similar events have been seen before and what
    actions were taken. Helps avoid repeated escalations and supports
    pattern-based reasoning.

    Args:
        scenario_id: Filter by scenario (S1-S5, SS1-SS2). Empty means all.
        limit: Maximum number of recent decisions to return (1-20).

    Returns:
        dict with list of recent decisions and count.
    """
    # Step 1 stub — real BQ query added in Step 2+
    return {
        "decisions": [],
        "count": 0,
        "note": "Memory query not yet implemented (Step 1 stub)",
    }

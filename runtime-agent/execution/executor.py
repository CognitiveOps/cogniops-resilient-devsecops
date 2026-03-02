"""
Execution module – Phase 0 stub.

Receives an approved decision and logs it. No operational action is taken.
In Phase 1 this will dispatch workflows, HITL escalations, and rollbacks.
"""

from __future__ import annotations

import logging

from models.schemas import ExecutionResult, GuardVerdict, PlanningDecision

logger = logging.getLogger(__name__)


def execute(decision: PlanningDecision, verdict: GuardVerdict) -> ExecutionResult:
    """
    Log the approved decision to stdout (Cloud Logging captures this).

    Phase 0: decision_executed is always False (shadow mode).
    No destructive actions are performed.
    """
    log_msg = (
        f"Execution: decision={decision.decision.value} "
        f"approved={verdict.approved} "
        f"rationale='{decision.rationale}' — "
        f"shadow mode, no action taken"
    )

    logger.info(log_msg)

    return ExecutionResult(
        decision_executed=False,
        log_message=log_msg,
    )

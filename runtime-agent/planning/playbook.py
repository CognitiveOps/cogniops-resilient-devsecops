"""
Risk / Planning module – Phase 0 stub.

Receives an AnomalyOutput from Perception and returns a hardcoded
PlanningDecision (always NO_OP in Phase 0).

In Phase 1 this will perform LLM-scored bounded playbook selection.
"""

from __future__ import annotations

import logging

from models.schemas import AnomalyOutput, DecisionType, PlanningDecision

logger = logging.getLogger(__name__)


def select_playbook(anomaly: AnomalyOutput) -> PlanningDecision:
    """
    Return a hardcoded NO_OP decision (Phase 0 shadow mode).

    In Phase 1 the LLM reasoning will evaluate the anomaly and choose
    from the bounded action surface: NO_OP, BLOCK, ROLLBACK,
    QUARANTINE, ESCALATE.
    """
    decision = PlanningDecision(
        decision=DecisionType.NO_OP,
        rationale="Phase 0 shadow mode — no action taken",
        policy_refs=[],
    )

    logger.info(
        "Planning: anomaly event_id=%s → decision=%s",
        anomaly.source_event_id,
        decision.decision.value,
    )
    return decision

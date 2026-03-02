"""
Policy Guard module – Phase 0 stub.

Receives a PlanningDecision and always returns approved=True.
In Phase 1 this will perform OPA re-check + PQC verification.
"""

from __future__ import annotations

import logging

from models.schemas import GuardVerdict, PlanningDecision

logger = logging.getLogger(__name__)


def check_policy(decision: PlanningDecision) -> GuardVerdict:
    """
    Always approve the decision in Phase 0 (guard bypassed).

    In Phase 1 the guard will re-evaluate the decision against
    OPA policies and verify PQC signatures before approval.
    """
    verdict = GuardVerdict(
        approved=True,
        reason="Phase 0 — guard bypassed",
    )

    logger.info(
        "Guard: decision=%s → approved=%s (%s)",
        decision.decision.value,
        verdict.approved,
        verdict.reason,
    )
    return verdict

"""
Inline risk assessment for S5 agent-managed workflows.

Evaluates the recommendation produced by s5_explainability_runner.py
and determines whether it is low-risk (auto-approve) or high-risk
(require human approval delay).

Key differences from baseline S5:
- Baseline: always sleeps S5_APPROVAL_DELAY_SEC (simulated HITL)
- Runtime: classifies risk → low-risk actions skip the delay entirely
  → measurable reduction in Approval Latency (AL)

Risk classification (deterministic, no LLM):
- LOW: rollback to known-good, NO_OP, routine policy update
- HIGH: new deployment, infrastructure change, security exception

Runs as CLI in GitHub Actions step. Outputs auto_approve (true/false)
and risk_level (low/high) as GitHub outputs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Actions that are considered low-risk and can be auto-approved.
LOW_RISK_ACTIONS = frozenset({
    "NO_OP",
    "ROLLBACK",
    "QUARANTINE",
    "rollback",
    "no_op",
    "quarantine",
    "routine_update",
    "patch_update",
})

# Severity thresholds
HIGH_SEVERITY_THRESHOLD = 0.7


def assess_risk(recommendation: dict) -> dict:
    """Assess risk of a recommendation and decide auto-approve.

    Args:
        recommendation: The recommendation.json produced by S5 explain stage.

    Returns:
        Dict with risk_level, auto_approve, reason.
    """
    action = recommendation.get("action", "UNKNOWN")
    severity = recommendation.get("severity", 0.5)
    confidence = recommendation.get("confidence", 0.5)

    # Determine risk level
    if action.upper() in {a.upper() for a in LOW_RISK_ACTIONS}:
        if severity < HIGH_SEVERITY_THRESHOLD:
            return {
                "risk_level": "low",
                "auto_approve": True,
                "reason": f"Low-risk action '{action}' with severity {severity:.2f}",
                "assessed_action": action,
                "assessed_severity": severity,
                "assessed_confidence": confidence,
            }

    # ESCALATE always requires human review
    if action.upper() == "ESCALATE":
        return {
            "risk_level": "high",
            "auto_approve": False,
            "reason": f"ESCALATE action always requires human review",
            "assessed_action": action,
            "assessed_severity": severity,
            "assessed_confidence": confidence,
        }

    # High severity → always human review
    if severity >= HIGH_SEVERITY_THRESHOLD:
        return {
            "risk_level": "high",
            "auto_approve": False,
            "reason": f"High severity ({severity:.2f}) requires human review",
            "assessed_action": action,
            "assessed_severity": severity,
            "assessed_confidence": confidence,
        }

    # Low confidence → human review
    if confidence < 0.5:
        return {
            "risk_level": "high",
            "auto_approve": False,
            "reason": f"Low confidence ({confidence:.2f}) requires human review",
            "assessed_action": action,
            "assessed_severity": severity,
            "assessed_confidence": confidence,
        }

    # Default: unknown action → human review
    return {
        "risk_level": "high",
        "auto_approve": False,
        "reason": f"Unknown action '{action}' defaults to human review",
        "assessed_action": action,
        "assessed_severity": severity,
        "assessed_confidence": confidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inline S5 risk assessment")
    parser.add_argument(
        "--recommendation-file", required=True,
        help="Path to recommendation.json from S5 explain stage",
    )
    args = parser.parse_args()

    with open(args.recommendation_file, encoding="utf-8") as f:
        recommendation = json.load(f)

    result = assess_risk(recommendation)

    print(f"Risk assessment: {result['risk_level']} — {result['reason']}")
    print(f"Auto-approve: {result['auto_approve']}")

    # Write outputs for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"risk_level={result['risk_level']}\n")
            f.write(f"auto_approve={str(result['auto_approve']).lower()}\n")
            f.write(f"reason={result['reason']}\n")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

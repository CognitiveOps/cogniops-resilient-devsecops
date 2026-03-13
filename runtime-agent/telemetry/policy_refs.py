"""
ISO/NIST control mapping for bounded action surface.

Maps each DecisionType to its corresponding regulatory control references:
- NIST SP 800-53 Rev. 5
- ISO 27001:2022
- IMO MSC.428(98) for maritime cyber-risk management

NO_OP has no control references (no action → no compliance requirement).
"""

from __future__ import annotations

from models.schemas import DecisionType

# ── Control reference matrix ─────────────────────────────────────────

_CONTROL_MAP: dict[DecisionType, list[str]] = {
    DecisionType.NO_OP: [],
    DecisionType.BLOCK: [
        "NIST SP 800-53 CM-3",  # Configuration Change Control
        "ISO 27001:2022 A.12.1.2",  # Change Management
        "IMO MSC.428(98) §4.1",  # Identify — risk assessment
    ],
    DecisionType.ROLLBACK: [
        "NIST SP 800-53 CP-10",  # System Recovery and Reconstitution
        "ISO 27001:2022 A.17.1.2",  # Implementing Information Security Continuity
        "IMO MSC.428(98) §4.4",  # Respond — contingency plans
    ],
    DecisionType.QUARANTINE: [
        "NIST SP 800-53 SI-3",  # Malicious Code Protection
        "ISO 27001:2022 A.12.2.1",  # Controls Against Malware
        "IMO MSC.428(98) §4.3",  # Detect — anomaly detection
    ],
    DecisionType.ESCALATE: [
        "NIST SP 800-53 IR-6",  # Incident Reporting
        "ISO 27001:2022 A.16.1.2",  # Reporting Information Security Events
        "IMO MSC.428(98) §4.5",  # Recover — lessons learned
    ],
}


def get_policy_refs(decision: DecisionType) -> list[str]:
    """Return control references for the given decision type.

    Returns an empty list for NO_OP.
    """
    return list(_CONTROL_MAP.get(decision, []))

package cogniops.runtime

# Runtime agent decision guardrails.
# Input: { action, scenario, severity, risk_score, event_type, mode, args }

# Block high-severity actions in shadow mode — only NO_OP is truly "executed"
deny contains "enforce-only action in shadow mode" if {
    input.mode == "shadow"
    input.action != "NO_OP"
}

# Require minimum severity for ROLLBACK
deny contains sprintf("ROLLBACK requires severity >= 0.7, got %v", [input.severity]) if {
    input.action == "ROLLBACK"
    input.severity < 0.7
}

# Require minimum severity for BLOCK
deny contains sprintf("BLOCK requires severity >= 0.6, got %v", [input.severity]) if {
    input.action == "BLOCK"
    input.severity < 0.6
}

# QUARANTINE only for S4/SS2 scenarios
deny contains sprintf("QUARANTINE only for S4/SS2, got %v", [input.scenario]) if {
    input.action == "QUARANTINE"
    not input.scenario in {"S4", "SS2"}
}

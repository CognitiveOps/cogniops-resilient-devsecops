---
description: "Implement LLM call logging, explainability ActionTraces for agent decisions, and ADK session state export."
agent: "agent"
---

# Step 5: Telemetry + Explainability

Read first:
- [Runtime agent instructions](../instructions/runtime-agent.instructions.md)
- [Existing telemetry](../../runtime-agent/telemetry/agentops_client.py)
- [Explainability schema](../../baseline/explainability/schema.py)
- [CloudEvents helpers](../../baseline/explainability/cloudevents.py)
- [Report rendering](../../baseline/explainability/report.py)

## Task

Add LLM-specific telemetry and connect agent decisions to the existing explainability framework.

## Implementation

### 1. LLM Logger (`telemetry/llm_logger.py`)
Log every Gemini call to Cloud Logging (structured JSON):
```python
{
    "event_type": "llm_call",
    "session_id": "...",
    "model": "gemini-2.0-flash",
    "prompt_hash": "sha256:...",       # Privacy: hash, not full prompt
    "prompt_tokens": 1250,
    "response_tokens": 85,
    "tool_call": "trigger_rollback",
    "tool_params": {"scenario": "S3", "rationale": "..."},
    "latency_ms": 340,
    "status": "success",               # success | fallback | error
    "timestamp": "2026-03-09T..."
}
```

### 2. Decision → ActionTrace CloudEvent
Extend baseline explainability kit for agent decisions:
- Use existing `baseline/explainability/cloudevents.py::new_cloudevent()`
- Emit CloudEvent with `type="cogniops.runtime.decision"`
- Data includes: anomaly context, decision, rationale, policy_refs, mode
- Send to ingest endpoint (same path as S5/SS2 traces)
- ACR validation: every decision must pass `validate_action_trace()`

### 3. ISO/NIST Control Mapping
Map decisions to compliance controls:
| Decision | Policy References |
|----------|------------------|
| BLOCK | NIST SP 800-53 CM-3, ISO 27001 A.12.1.2 |
| ROLLBACK | NIST SP 800-53 CP-10, ISO 27001 A.17.1.2 |
| QUARANTINE | NIST SP 800-53 SI-3, ISO 27001 A.12.2.1 |
| ESCALATE | NIST SP 800-53 IR-6, ISO 27001 A.16.1.2 |
| NO_OP | (no control — baseline operating normally) |

### 4. ADK Session State → BQ
Export session state after each pipeline run:
- Decision chain (perception → planning → guard → execution)
- All intermediate data (anomaly scores, tool calls, guard results)
- Write as additional fields in `runtime_decisions` row

### 5. Tests
- `tests/test_llm_logger.py`: verify structured log format
- `tests/test_explainability.py`: verify ActionTrace passes ACR validation
- `tests/test_policy_refs.py`: verify correct control mapping per decision type

## Constraints
- Explainability integration extends (not modifies) the baseline kit
- LLM logger must not log raw prompts (hash only for privacy)
- All CloudEvents must pass existing `validate_action_trace` checks

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - LLM call logging approach (Cloud Logging structured JSON)
   - ActionTrace integration with explainability kit
   - ISO/NIST control mapping per decision type
   - Session state export to BQ
2. Update `README.md` § "📊 Implementation Progress" — mark Step 5 as ✅
3. Update `docs/system-guardrails.md` § A-1, A-2, A-3 with actual logging/audit details

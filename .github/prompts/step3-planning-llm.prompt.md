---
description: "Implement LLM-based Planning via ADK with Vertex AI Gemini. Structured output, bounded actions, episodic context, few-shot prompts."
agent: "llm-specialist"
---

# Step 3: Planning — LLM Integration via ADK

Read first:
- [Runtime agent instructions](../instructions/runtime-agent.instructions.md)
- [ADK agent definition](../../runtime-agent/agent/cogniops_agent.py) (from Step 1)
- [System prompt](../../runtime-agent/agent/prompts/system.txt) (from Step 1)
- [Perception tool](../../runtime-agent/agent/tools/perception_tool.py) (from Step 2)
- [Existing schemas](../../runtime-agent/models/schemas.py)

## Task

Connect the ADK Planning agent to Vertex AI Gemini. The LLM selects bounded mitigation actions through ADK tool calling. This is THE ONLY module that uses LLM.

## Implementation

### 1. Update system prompt (`agent/prompts/system.txt`)
Enhance with:
- Full role definition: CogniOps Runtime Planning Agent
- Input format: anomaly context (scenario, type, severity, risk, evidence)
- Episodic context: recent decisions and their outcomes
- Decision criteria matrix:
  - severity < 0.3 → NO_OP
  - severity 0.3-0.6 → ESCALATE (human review)
  - severity 0.6-0.8 + known playbook → ROLLBACK or BLOCK
  - severity > 0.8 + critical scenario → ROLLBACK + ESCALATE
  - PQC failure → always QUARANTINE
  - policy_violation → always BLOCK
- Output: call exactly one action tool with rationale parameter

### 2. Create few-shot examples
```
agent/prompts/
├── system.txt                  # Enhanced system prompt
├── few_shot_s1.txt            # Pipeline failure: high CFR → ROLLBACK
├── few_shot_s3.txt            # Resilience: high MTTD → ESCALATE, high MTTR → ROLLBACK
├── few_shot_ss2.txt           # Adaptive threat: integrity failure → QUARANTINE
└── few_shot_s5.txt            # Explainability: low ACR → ESCALATE
```

### 3. Episodic context (`agent/tools/memory_tools.py`)
```python
def get_recent_decisions(scenario: str, limit: int = 5) -> list[dict]:
    """Query last N decisions from runtime_decisions for this scenario."""
    # BQ query: SELECT decision, rationale, event_type, processed_at
    # FROM agent_metrics.runtime_decisions
    # WHERE context.scenario_id = @scenario
    # ORDER BY processed_at DESC LIMIT @limit
```
Inject results into prompt as "Recent decisions for context" section.

### 4. Connect Gemini model (`agent/cogniops_agent.py`)
```python
planning_agent = Agent(
    name="cogniops_planning",
    model="gemini-2.0-flash",  # or from env: COGNIOPS_MODEL
    instruction=load_prompt("system.txt") + load_few_shots(scenario),
    tools=[no_action, trigger_rollback, block_deployment,
           quarantine_artifact, create_hitl_issue],
    before_tool_callback=guard_check,
)
```

### 5. Fallback handling
```python
try:
    response = await runner.run(session, input_message)
    # ADK validates tool call schema automatically
except Exception:
    # ANY failure → safe default
    return PlanningDecision(decision=DecisionType.NO_OP,
                            rationale="LLM fallback — error during reasoning")
```

### 6. LLM call logging (`telemetry/llm_logger.py`)
Log every Gemini call:
- Prompt hash (not full prompt — privacy)
- Response tool call name + parameters
- Latency (ms)
- Model version
- Token count (input + output)
- Session ID for correlation

### 7. Tests
- `tests/test_planning_llm.py` using ADK `InMemoryRunner`
- Test: high severity anomaly → ROLLBACK or BLOCK tool call
- Test: low severity → NO_OP tool call
- Test: invalid LLM response → fallback to NO_OP
- Test: episodic context injection (mock BQ → verify prompt includes recent decisions)
- Test: few-shot loading per scenario

## Constraints
- LLM ONLY selects which tool to call — never generates free text
- If Gemini is unavailable → NO_OP (zero risk)
- All prompts in files (never hardcoded strings in Python)
- Log every LLM interaction for audit trail
- shadow mode: decisions logged, tools don't execute real actions

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - LLM integration (Gemini model, ADK tool calling)
   - System prompt structure + few-shot examples
   - Fallback behaviour (NO_OP on any LLM failure)
   - Decision criteria matrix (severity → action mapping)
2. Update `README.md` § "📊 Implementation Progress" — mark Step 3 as ✅
3. Update `docs/ai-design-architecture.md` § 7 (Prompt Engineering) with actual prompt content summary
4. Update `docs/system-guardrails.md` § S-2 and § C-2 if fallback behaviour differs from spec

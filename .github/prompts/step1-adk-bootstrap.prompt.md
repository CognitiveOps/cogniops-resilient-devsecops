---
description: "Bootstrap ADK agent structure in runtime-agent. Replaces Phase 0 stubs with ADK skeleton while preserving existing FastAPI app."
agent: "agent"
---

# Step 1: ADK Bootstrap

Read first:
- [Runtime agent instructions](../instructions/runtime-agent.instructions.md)
- [Existing main.py](../../runtime-agent/main.py)
- [Existing schemas](../../runtime-agent/models/schemas.py)
- [Phase 0 spec](../../docs/phase0-runtime-ready-spec.md)

## Task

Set up the Google ADK agent structure inside `runtime-agent/`. This is a **structural migration** — no LLM integration yet. The agent pipeline should produce the same output as Phase 0 (always NO_OP) but with ADK architecture.

## Implementation

### 1. Update dependencies
Add to `runtime-agent/requirements.txt`:
```
google-adk>=1.0,<2.0
google-cloud-aiplatform>=1.60,<2.0
```

### 2. Create ADK agent structure
```
runtime-agent/agent/
├── __init__.py
├── cogniops_agent.py          # Root agent definition
├── tools/
│   ├── __init__.py
│   ├── perception_tool.py     # ADK FunctionTool wrapping perception logic
│   ├── execution_tools.py     # ADK FunctionTools: no_action, rollback, block, escalate
│   └── memory_tools.py        # ADK FunctionTool: query recent decisions from BQ
├── callbacks/
│   ├── __init__.py
│   └── guard_callback.py      # before_tool_callback (stub: always allows)
└── prompts/
    └── system.txt             # System prompt (bounded action surface)
```

### 3. ADK Agent definition (cogniops_agent.py)
- Create an `LlmAgent` named "cogniops_planning"
- Model: use env var `COGNIOPS_MODEL` (default: "gemini-2.0-flash")
- Instruction: loaded from `agent/prompts/system.txt`
- Tools: perception, execution tools (no_action, rollback, block, escalate)
- before_tool_callback: guard_callback (stub, always passes)

### 4. System prompt (prompts/system.txt)
Write bounded-action system prompt:
- Role: CogniOps Runtime Planning Agent
- Context: anomaly detected in DevSecOps pipeline
- Available actions: NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE
- Decision criteria per severity/risk threshold
- Output: select exactly one action tool with rationale

### 5. FastAPI integration (main.py)
- Keep existing POST /events/runtime endpoint working
- Add ADK runner alongside (new endpoint or internal call)
- Existing Phase 0 pipeline remains functional during migration

### 6. Tests
- `tests/test_agent_pipeline.py`: InMemoryRunner tests
- Verify agent produces valid tool calls
- Verify guard callback is invoked
- Verify fallback to no_action on errors

## Constraints
- Preserve all existing files (backward compatibility)
- New ADK code goes in `agent/` subdirectory
- Existing Pydantic schemas, BQ writer, AgentOps telemetry unchanged
- Do not connect to real Gemini yet (use InMemoryRunner for tests)

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - ADK dependency added
   - `agent/` directory structure created
   - SequentialAgent + FastAPI coexistence pattern
2. Update `README.md` § "📊 Implementation Progress" — mark Step 1 as ✅
3. Update `docs/ai-design-architecture.md` § 10 if any architecture decisions changed
4. Update `runtime-agent/README.md` with new directory layout and agent module docs

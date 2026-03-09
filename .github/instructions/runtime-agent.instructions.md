---
description: "Use when modifying runtime-agent modules: perception, planning, guard, execution, storage, telemetry, ADK agent definitions, or runtime tests"
applyTo: "runtime-agent/**"
---
# Runtime Agent — Module Guidelines

## Architecture (ADK-based)
The runtime-agent is a FastAPI service on Cloud Run that hosts an ADK agent pipeline:
```
Event → POST /events/runtime → ADK Runner
  → Perception Tool (deterministic: BQ query + z-score + threshold)
  → Planning LlmAgent (Gemini: selects bounded action via tool call)
  → Guard (before_tool_callback: OPA re-check + PQC integrity)
  → Execution Tools (github_dispatch, hitl_issue, rollback)
  → BQ write (runtime_decisions) + CloudEvent ActionTrace
```

## Module Responsibilities

### Perception (`agent/tools/perception_tool.py`)
- DETERMINISTIC — no LLM here
- Queries `agent_metrics.runs` for historical baselines per scenario
- Z-score anomaly detection: |x - μ| > 2σ
- Threshold checks per metric (TTD, MTTD, CFR etc.)
- Outputs: severity (0-1), risk_score (0-1), anomaly_type

### Planning (`agent/cogniops_agent.py`)
- THE ONLY module that uses LLM (Gemini via ADK)
- Input: AnomalyOutput + episodic context (last N decisions)
- Output: tool call selecting one of the bounded actions
- System prompt in `agent/prompts/system.txt`
- Few-shot examples per scenario in `agent/prompts/`
- FALLBACK: if LLM fails → NO_OP (safe default)

### Guard (`agent/callbacks/guard_callback.py`)
- ADK `before_tool_callback` — runs before any execution tool
- DETERMINISTIC — no LLM here
- OPA policy re-check (call opa eval)
- PQC integrity verification (if applicable)
- If violation → block tool execution, log reason

### Execution (`agent/tools/execution_tools.py`)
- DETERMINISTIC — no LLM here
- GitHub workflow_dispatch (rollback, block)
- GitHub Issue creation (ESCALATE → HITL)
- Mode-gated: shadow (log only) → advisory (log + notify) → enforce (execute)

### Storage (`storage/bigquery_writer.py`)
- Write decision rows to `agent_metrics.runtime_decisions`
- Best-effort writes — failures logged, never block pipeline

### Telemetry (`telemetry/`)
- AgentOps: optional pipeline tracing
- LLM Logger: every Gemini call logged (prompt, response, latency, tokens)

## Key Constraints
- Never modify baseline code (baseline/, .github/workflows/)
- Never modify BQ schema for `agent_metrics.runs`
- All new Pydantic models go in `models/`
- All prompts go in `agent/prompts/` (version-controlled, never hardcoded)
- Every LLM response validated against Pydantic schema
- Every new module needs a test file in `tests/`
- Use ADK `InMemoryRunner` for deterministic agent tests

---
description: "Master orchestrator for CogniOps implementation. Run this to implement any phase/step of the thesis project with full governance, architecture constraints, and design decisions pre-loaded."
agent: "agent"
argument-hint: "Step number and feature, e.g. 'Step 2: real anomaly detection in Perception'"
---

# CogniOps Implementation Orchestrator

You are implementing the CogniOps MSc thesis project — an Autonomous Cognitive AI Agent for Resilient DevSecOps Environments.

## Pre-Implementation Checklist (ALWAYS do first)

1. Read [copilot-instructions.md](../copilot-instructions.md) for project governance
2. Read [README.md](../../README.md) for baseline architecture
3. Read [runtime-event-contract.md](../../docs/runtime-event-contract.md) for event schema
4. Read [phase0-runtime-ready-spec.md](./../../docs/phase0-runtime-ready-spec.md) for Phase 0 spec
5. Identify which Step (0–7) is being requested
6. Check current state: what exists, what's stub, what needs implementation

## Implementation Roadmap

### Step 0: Copilot Development Infrastructure ✅
Copilot customization files in `.github/` — instructions, prompts, agents.

### Step 1: ADK Bootstrap
Replace Phase 0 stubs with ADK skeleton (no LLM yet, but correct structure).
```
runtime-agent/
├── requirements.txt              ← add: google-adk, google-cloud-aiplatform
├── agent/
│   ├── __init__.py
│   ├── cogniops_agent.py         ← SequentialAgent orchestrator
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── perception_tool.py    ← ADK Tool: stub anomaly detection
│   │   ├── execution_tools.py    ← ADK Tools: no_action, rollback, block, escalate
│   │   └── memory_tools.py       ← ADK Tool: query recent decisions
│   ├── callbacks/
│   │   ├── __init__.py
│   │   └── guard_callback.py     ← before_tool_callback: stub (always pass)
│   └── prompts/
│       └── system.txt            ← System prompt with bounded action surface
├── main.py                       ← FastAPI + ADK Runner integration
└── tests/
    └── test_agent_pipeline.py    ← InMemoryRunner tests
```
Key decisions:
- ADK Agent wraps existing FastAPI app (coexistence, not replacement)
- Existing Pydantic schemas, BQ writer, AgentOps telemetry all preserved
- Phase 0 stub modules (perception/, planning/, guard/, execution/) remain for backward compatibility during migration
- New ADK code goes in `agent/` directory

### Step 2: Perception — Real Anomaly Detection
Make perception tool detect real anomalies. NO LLM — pure Python + BigQuery.
```
agent/tools/perception_tool.py:
  - query_baselines(): BQ query for historical averages per scenario
  - z_score_check(): |x - μ| > 2σ anomaly detection
  - threshold_check(): hard limits per metric per scenario
  - score_severity(): combine into severity (0-1) + risk_score (0-1)
```
Metric thresholds per scenario:
| Scenario | Metric | Warning | Critical |
|----------|--------|---------|----------|
| S1 | TTD | >180s | >300s |
| S1 | CFR | >10% | >25% |
| S3 | MTTD | >60s | >120s |
| S3 | MTTR | >120s | >300s |
| S2 | DSR | <95% | <85% |

Tests: mock BQ data → verify correct anomaly scoring.

### Step 3: Planning — LLM Integration via ADK
THE core AI engineering step. Gemini selects bounded actions via tool calling.
```
agent/cogniops_agent.py:
  - LlmAgent with model="gemini-2.0-flash"
  - instruction loaded from agent/prompts/system.txt
  - tools: [detect_anomaly, trigger_rollback, block_deployment, create_hitl_issue, no_action]
  - before_tool_callback: guard_check (OPA + PQC)

agent/prompts/:
  - system.txt: role, constraints, bounded actions, output format
  - few_shot_s1.txt: pipeline failure examples
  - few_shot_s3.txt: resilience degradation examples
  - few_shot_ss2.txt: adaptive threat examples

agent/tools/memory_tools.py:
  - Query last N decisions from runtime_decisions for episodic context
  - Inject into prompt as "Recent decisions" section
```
Key constraints:
- LLM ONLY selects which tool to call — never generates free text
- ADK validates tool call schema automatically
- If LLM produces invalid output → fallback to no_action tool (NO_OP)
- Every LLM call logged: prompt, response, latency, model version, token count

### Step 4: Guard + Execution — Real Actions
```
agent/callbacks/guard_callback.py:
  - opa_eval(): call OPA REST API or CLI with decision context
  - pqc_integrity_check(): verify PQC signatures (if applicable)
  - If violation → return blocked=True, reason logged

agent/tools/execution_tools.py:
  - trigger_rollback(): GitHub workflow_dispatch API
  - block_deployment(): emit block event via Pub/Sub
  - create_hitl_issue(): GitHub Issues API (ESCALATE decision)
  - no_action(): log NO_OP (safe default)

Mode gating (in each tool):
  - shadow: log intent, return success without executing
  - advisory: log + create GitHub Issue notification
  - enforce: log + execute real action
```

### Step 5: Telemetry + Explainability
```
telemetry/llm_logger.py:
  - Log every LLM call: prompt hash, response, latency, model, tokens
  - Write to Cloud Logging (structured JSON)

Explainability integration:
  - Every decision → CloudEvent ActionTrace (extend existing baseline kit)
  - Rationale includes ISO/NIST control mapping
  - ACR validation on agent decisions
  - ADK Session.state → exported to BQ for audit trail
```

### Step 6: Design-Time Agent
```
design-agent/
├── agent/
│   ├── design_agent.py          ← ADK Agent: structural synthesis
│   ├── tools/
│   │   ├── context_builder.py   ← Tool: read metrics, workflows, policies from BQ + GitHub
│   │   ├── proposal_gen.py      ← Tool: generate YAML diffs, policy patches
│   │   └── validator.py         ← Tool: OPA simulate, YAML lint, dry-run
│   └── prompts/
│       └── design_system.txt
├── main.py                      ← FastAPI or batch script
└── tests/
```
Output: JSON proposals → GCS + optional GitHub Issue. NEVER mutates main branch.

### Step 7: 2-Axis Evaluation
```
evaluation/
├── scripts/
│   ├── run_baseline.py          ← Scenarios without agent
│   ├── run_runtime.py           ← With runtime agent only
│   ├── run_design.py            ← With design agent only
│   ├── run_full.py              ← Both agents combined
│   └── compare_variants.py      ← Statistical comparison
├── queries/                     ← BQ SQL per metric per variant
└── eval_dataset.json            ← ADK built-in eval framework data
```

## Governance Rules (ALWAYS enforce)

1. **Baseline immutability**: NEVER modify baseline/, .github/workflows/, agent_metrics.runs schema
2. **LLM confinement**: LLM used ONLY in Planning agents — Perception, Guard, Execution are deterministic
3. **Bounded actions**: Only NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE — no other actions
4. **Fail-safe**: Any LLM/API failure → NO_OP (zero operational risk)
5. **Shadow first**: New capabilities start in shadow mode (log only, no execution)
6. **Prompts are code**: All prompts in `prompts/` dirs, version-controlled, never hardcoded strings
7. **Schema validation**: Every I/O boundary validated with Pydantic v2
8. **Test coverage**: Every new module must have tests. ADK InMemoryRunner for agent tests
9. **Security**: No secrets in code, IAM least-privilege, no --no-verify
10. **Additive only**: New files/resources. Never modify existing infrastructure
11. **Documentation**: After every step, update `README.md` (AI Architecture + Progress) and relevant `docs/` files

## How to Use This Prompt

Tell me which Step and feature to implement, e.g.:
- "Step 1: Set up ADK bootstrap with SequentialAgent"
- "Step 2: Implement z-score anomaly detection in perception tool"
- "Step 3: Create system prompt with bounded action surface for Gemini"
- "Step 4: Implement OPA guard callback"
- "Step 7: Create evaluation comparison script for S3 MTTD"

I will:
1. Read relevant existing code
2. Check what exists vs what needs implementation
3. Implement following all governance rules above
4. Write tests
5. Validate no baseline or immutable components were modified
6. Update `README.md` § "🤖 AI Agent Architecture" and § "📊 Implementation Progress"
7. Update relevant `docs/` files (guardrails, architecture, IAM)

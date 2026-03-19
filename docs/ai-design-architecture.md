# AI Design Engineering Architecture

> CogniOps — Autonomous Cognitive AI Agent for Resilient DevSecOps Environments  
> Version: 2.0 (Post-Implementation)  
> Last Updated: 2026-03-19  
> Status: All Steps (0–7) Implemented — Ready for Evaluation with Real Data

---

## 1. Design Philosophy

CogniOps follows a **Hybrid Cognitive-SOAR** architecture where:

- A **deterministic substrate** (baseline DevSecOps) runs autonomously and emits
  observable metrics
- A **cognitive control plane** (AI agents) perceives anomalies, reasons about
  them, and takes bounded actions — or proposes structural improvements

The system is designed around three principles:

1. **Fail-Safe by Default** — every AI component has a deterministic fallback
   that produces zero operational risk
2. **Observability Before Action** — the agent must observe and log before it
   may act; new capabilities always start in shadow mode
3. **Bounded Autonomy** — the AI operates within a pre-defined, enumerable
   action surface; it cannot invent new actions

---

## 2. Two-Layer Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    COGNITIVE CONTROL PLANE                        │
│                                                                  │
│  ┌─────────────────────┐      ┌─────────────────────────────┐   │
│  │   Runtime Agent      │      │   Design-Time Agent          │   │
│  │   (Operational)      │      │   (Structural)               │   │
│  │                      │      │                               │   │
│  │  Perception → Plan   │      │  Metrics → Context → Plan    │   │
│  │   → Guard → Execute  │      │   → Validate → Propose       │   │
│  │                      │      │                               │   │
│  │  Actions: bounded    │      │  Output: JSON proposals       │   │
│  │  Mode: shadow/adv/en │      │  Target: GCS + GitHub Issues  │   │
│  └────────┬─────────────┘      └──────────────┬────────────────┘   │
│           │                                    │                   │
│     Pub/Sub events                      BQ metric queries          │
│           │                                    │                   │
├───────────┼────────────────────────────────────┼───────────────────┤
│           ▼                                    ▼                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │               DETERMINISTIC SUBSTRATE                        │ │
│  │                                                              │ │
│  │   S1 (CI/CD) │ S2 (OTA) │ S3 (Resilience) │ S4 (PQC)      │ │
│  │   S5 (Explainability) │ SS1 (Policy) │ SS2 (Threat)         │ │
│  │                                                              │ │
│  │   GitHub Actions → Cloud Function → BigQuery (agent_metrics) │ │
│  │   OPA Policies │ PQC Verification │ Explainability Kit      │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 Layer Separation Rules

| Rule | Runtime Agent | Design-Time Agent |
|------|---------------|-------------------|
| Reads metrics from BQ | ✅ Runtime decisions + baselines | ✅ All metrics tables |
| Calls LLM (Gemini) | ✅ In Planning only | ✅ In Planning only |
| Executes operational actions | ✅ Mode-gated | ❌ Never |
| Modifies code / YAML / config | ❌ Never | ❌ Proposes only (JSON) |
| Writes to BQ | ✅ runtime_decisions | ✅ design_proposals (future) |
| Modifies baseline components | ❌ Never | ❌ Never |

---

## 3. Technology Decisions

### 3.1 ADK over Raw Vertex AI SDK

**Decision**: Use Google ADK (Agent Development Kit) as the agent orchestration
framework instead of calling the Vertex AI Gemini API directly.

**Rationale**:

| Capability | Raw Vertex AI SDK | Google ADK |
|------------|-------------------|------------|
| Agent orchestration | Manual implementation | Built-in `Agent`, `SequentialAgent` |
| Tool definitions | Manual JSON schema + dispatch | Declarative `@tool` decorator |
| Guard/callback pipeline | Manual pre/post hooks | `before_tool_callback`, `after_tool_callback` |
| Session/memory management | Manual state passing | `Session.state` with automatic context |
| Deterministic testing | Mock HTTP calls | `InMemoryRunner` with captured interactions |
| Evaluation framework | Manual metric computation | Built-in eval with dataset + scoring |
| Multi-agent composition | Custom routing logic | `SequentialAgent`, `ParallelAgent` |
| Structured output | Manual schema enforcement | Automatic via tool return types |

**Alternatives Considered**:

| Framework | Why Not |
|-----------|---------|
| LangChain | Over-abstraction, vendor-agnostic by design (we're committed to GCP) |
| CrewAI | Multi-agent focused, unnecessary complexity for 2-agent system |
| AutoGen | Conversational multi-agent, wrong paradigm for event-driven pipeline |
| Raw Vertex AI | Missing orchestration primitives, would duplicate what ADK provides |

### 3.2 Gemini as LLM

**Decision**: Vertex AI Gemini (via ADK, model `gemini-2.0-flash`) for all LLM reasoning.

**Rationale**:
- Native GCP integration (same project, same IAM, same billing)
- Function calling support (required for bounded action selection)
- Structured output via tool definitions (Pydantic-compatible)
- Low latency (`gemini-2.0-flash`) suitable for runtime pipeline
- Vertex AI endpoint (not consumer API) for enterprise SLA and data residency

### 3.3 LLM Confinement

**Decision**: LLM used exclusively in the Planning module. All other modules
(Perception, Guard, Execution, Storage, Telemetry) are deterministic Python.

**Rationale**:
- Minimizes attack surface for prompt injection and hallucination
- Makes pipeline behavior predictable and testable outside LLM calls
- Reduces cost (LLM called once per event, not per module)
- Ensures guard and execution logic is auditable and formally verifiable
- Matches SOAR pattern: only the "planning" step requires reasoning

### 3.4 Pydantic v2 for All Boundaries

**Decision**: Every I/O boundary (HTTP input, module output, LLM response, BQ row)
validated through Pydantic v2 models.

**Rationale**:
- Type-safe at runtime (not just static analysis)
- LLM structured output validated before any action taken
- Schema violations produce clear error messages for debugging
- Direct serialization to BQ rows, JSON responses, CloudEvents

---

## 4. Runtime Agent — ADK Architecture

### 4.1 Pipeline Mapping to ADK Concepts

```
CogniOps Concept     →    ADK Concept
─────────────────────────────────────────
Runtime Agent        →    SequentialAgent (orchestrator)
Planning Module      →    LlmAgent (with Gemini)
Perception           →    Tool (detect_anomaly)
Execution Actions    →    Tools (rollback, block, escalate, no_action)
Memory               →    Tool (query_recent_decisions) + Session.state
Guard                →    before_tool_callback
System Prompt        →    agent.instruction (loaded from file)
Few-Shot Examples    →    Prompt sections in instruction
Mode Gating          →    Tool implementation (shadow/advisory/enforce)
```

### 4.2 Agent Definition (Target)

```python
from google.adk import Agent
from google.adk.agents import SequentialAgent

# Planning agent — the ONLY component that uses LLM
planning_agent = Agent(
    name="cogniops_planner",
    model="gemini-2.0-flash",
    instruction=load_prompt("agent/prompts/system.txt"),
    tools=[
        detect_anomaly,        # Perception (deterministic)
        query_recent_decisions, # Memory (deterministic)
        no_action,             # NO_OP
        trigger_rollback,      # ROLLBACK
        block_deployment,      # BLOCK
        quarantine_artifact,   # QUARANTINE
        create_hitl_issue,     # ESCALATE
    ],
    before_tool_callback=guard_check,  # OPA + PQC (deterministic)
)
```

### 4.3 Tool Definitions (Target)

| Tool | ADK Role | Deterministic | Description |
|------|----------|---------------|-------------|
| `perceive_anomaly` | Perception | ✅ Yes | Z-score + threshold check against BQ baselines |
| `query_recent_decisions` | Memory | ✅ Yes | Last N decisions from `runtime_decisions` table |
| `no_action` | Execution | ✅ Yes | Safe default — log NO_OP (all modes) |
| `rollback_deployment` | Execution | ✅ Yes | GitHub workflow_dispatch for `s3_edge_rollback.yml` (mode-gated) |
| `block_deployment` | Execution | ✅ Yes | Block deployment + GitHub Issue (mode-gated) |
| `quarantine_artifact` | Execution | ✅ Yes | Quarantine issue via GitHub API (mode-gated) |
| `escalate_to_human` | Execution | ✅ Yes | HITL issue via GitHub Issues API (mode-gated) |

### 4.4 Guard Callback (Implemented)

```python
def guard_callback(*, tool, args, tool_context) -> Optional[dict]:
    """
    before_tool_callback — runs BEFORE every tool execution.
    Deterministic. No LLM.

    - Observation tools (perceive_anomaly, query_recent_decisions) → always pass
    - Unknown tools → always blocked (safety)
    - Execution tools → OPA check + PQC check (S4/SS2)
    """
    # 1. OPA policy evaluation (fail-closed: OPA down → deny)
    opa_result = await opa_eval(build_opa_input(action, args, session_state))
    if not opa_result.allowed:
        return {"action": "NO_OP", "guard_blocked": True, "guard_reason": "opa_violation"}

    # 2. PQC integrity check (S4/SS2 only, if artifact context present)
    if scenario in ("S4", "SS2") and has_artifact_context(session_state):
        verified, reason = verify_manifest(backend, algorithm, manifest, sig, pub_key)
        if not verified:
            return {"action": "NO_OP", "guard_blocked": True, "guard_reason": "pqc_failure"}

    return None  # Allow execution
```

**Guard Semantics:**
- Guard is **fail-closed**: OPA unreachable or PQC error → deny
- Execution tools are **fail-open**: GitHub API failure → log + NO_OP

### 4.5 Session State for Episodic Memory

Instead of creating new BQ tables, the agent uses ADK `Session.state`
combined with SQL views over existing `runtime_decisions`:

```python
# ADK Session.state carries per-invocation context
session.state["recent_decisions"] = query_last_n_decisions(n=10)
session.state["baseline_metrics"] = query_scenario_baselines(scenario_id)
session.state["current_mode"] = os.getenv("AGENT_MODE", "shadow")
```

**Decision**: Use ADK Session.state + SQL views over `runtime_decisions` instead
of creating dedicated `agent_memory.*` tables.

**Rationale**: Simpler, avoids schema proliferation, existing BQ data is sufficient
for episodic context, and Session.state handles per-request transient memory.

### 4.6 FastAPI Coexistence

**Decision**: ADK Agent wraps the existing FastAPI app — coexistence, not replacement.

```
POST /events/runtime → FastAPI endpoint
    → Parse Pub/Sub envelope (existing code)
    → Validate RuntimeEvent (existing Pydantic)
    → Create ADK Session with event context
    → runner.run(session) → ADK pipeline
    → Build BQ DecisionRow from session result
    → Write to BigQuery (existing writer)
    → Return HTTP response
```

Existing Phase 0 modules (`perception/`, `planning/`, `guard/`, `execution/`)
are preserved for backward compatibility during migration. New ADK code resides in
the `agent/` subdirectory.

---

## 5. Design-Time Agent — ADK Architecture

### 5.1 Purpose

The Design-Time Agent analyzes accumulated metrics across all scenarios and produces
**structural improvement proposals** — configuration changes, policy updates, threshold
adjustments — as validated JSON documents.

### 5.2 Separation from Runtime

| Aspect | Runtime Agent | Design-Time Agent |
|--------|---------------|-------------------|
| Trigger | Real-time Pub/Sub events | Batch/scheduled (daily or on-demand) |
| Latency | Sub-second response required | Minutes acceptable |
| Actions | Operational (block, rollback) | Structural (propose config change) |
| Output | BQ decision row | JSON proposal in GCS |
| Risk | Can affect production traffic | Cannot affect production |
| Service Account | `runtime-agent-sa` | `design-agent-sa` (separate) |
| Infrastructure | Cloud Run + Pub/Sub | Cloud Run Job or batch script |

### 5.3 Pipeline

```
Scheduled Trigger or Manual Invocation
         │
         ▼
  Context Builder (Tool)
  ├── Query BQ: metric trends (last 7/30 days)
  ├── Read: current workflows via GitHub API
  ├── Read: current OPA policies
  └── Read: current Terraform config
         │
         ▼
  Intent Processor (Deterministic)
  ├── Detect metric regression patterns
  ├── Identify policy coverage gaps
  └── Map to improvement categories
         │
         ▼
  Planning Agent (LlmAgent + Gemini)
  ├── Generate improvement proposals
  ├── Structured output: JSON schema
  └── Reference ISO/NIST controls
         │
         ▼
  Validator (Deterministic)
  ├── OPA policy simulation (opa eval --dry-run)
  ├── YAML lint (if YAML output)
  ├── Schema validation (Pydantic)
  └── Consistency check against current config
         │
         ▼
  Output
  ├── GCS: proposals/{date}/{proposal_id}.json
  └── Optional: GitHub Issue with summary
```

### 5.4 Implemented Directory Structure

```
design-agent/
├── agent/
│   ├── __init__.py
│   ├── design_agent.py          # ADK LlmAgent (Gemini 2.0 Flash)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── context_builder.py   # BQ metrics (30-day trends, percentiles)
│   │   ├── proposal_generator.py # Structured DesignProposal assembly
│   │   └── validator.py         # Schema + YAML lint + path traversal guard
│   └── prompts/
│       ├── design_system.txt    # System prompt for design reasoning
│       ├── few_shot_optimize.txt # Few-shot: metric optimization proposals
│       └── few_shot_policy.txt  # Few-shot: policy update proposals
├── models/
│   ├── __init__.py
│   └── schemas.py               # Pydantic v2: MetricContext, DesignProposal
├── main.py                      # FastAPI /run + /healthz endpoints
├── requirements.txt
├── Dockerfile
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_context_builder.py
    ├── test_design_pipeline.py  # End-to-end + FastAPI endpoint tests
    ├── test_proposal_generator.py
    ├── test_schemas.py
    └── test_validator.py        # 97 tests total
```

---

## 6. Data Architecture

### 6.1 Data Flow Diagram

```
                    ┌─────────────────────────────────────┐
                    │          BigQuery Dataset            │
                    │         agent_metrics                │
                    │                                      │
 S1–SS2 Workflows  │  ┌───────────────────────────────┐  │
 ──────────────────►│  │ runs (IMMUTABLE)              │  │◄── Design-Time Agent
                    │  │ All scenario stage events      │  │       reads metrics
 Cloud Function     │  └───────────────────────────────┘  │
 (ingest)           │                                      │
                    │  ┌───────────────────────────────┐  │
                    │  │ s1_pipeline_runs (IMMUTABLE)   │  │
                    │  │ S1 fine-grained pipeline data  │  │
                    │  └───────────────────────────────┘  │
                    │                                      │
 Runtime Agent      │  ┌───────────────────────────────┐  │
 ──────────────────►│  │ runtime_decisions (EXTENDABLE) │  │◄── Runtime Agent
  writes decisions  │  │ Agent decisions + rationale     │  │     reads (episodic)
                    │  └───────────────────────────────┘  │
                    │                                      │
                    │  ┌───────────────────────────────┐  │
                    │  │ Views (computed, not stored)   │  │
                    │  │ • baseline_averages            │  │
                    │  │ • anomaly_thresholds           │  │
                    │  │ • decision_history             │  │
                    │  └───────────────────────────────┘  │
                    └─────────────────────────────────────┘
```

### 6.2 Schema Governance

| Table | Owner | Mutability | AI Access |
|-------|-------|------------|-----------|
| `runs` | Baseline (Cloud Function) | IMMUTABLE schema | Read-only (both agents) |
| `s1_pipeline_runs` | Baseline (S1 workflow) | IMMUTABLE schema | Read-only (both agents) |
| `runtime_decisions` | Runtime Agent | EXTENDABLE (additive fields) | Read-write (runtime), read-only (design) |

---

## 7. Prompt Engineering Architecture

### 7.1 Prompts Are Code

All LLM prompts are version-controlled files, not embedded strings.

```
runtime-agent/agent/prompts/
├── system.txt                # Core system prompt (role, constraints, decision criteria)
├── few_shot_s1.txt           # Pipeline failure: high CFR → ROLLBACK, normal → NO_OP
├── few_shot_s3.txt           # Resilience: moderate MTTD → ESCALATE, critical MTTR → ROLLBACK
├── few_shot_s5.txt           # Explainability: low ACR → ESCALATE
├── few_shot_ss2.txt          # Adaptive threat: integrity → QUARANTINE, degradation → BLOCK
└── (loaded by _build_instruction() in cogniops_agent.py)

design-agent/agent/prompts/
└── design_system.txt         # Design-time reasoning prompt (Step 6)
```

### 7.2 System Prompt Structure (Runtime — Implemented)

The system prompt (`system.txt`) contains:

1. **Role definition**: CogniOps Runtime Planning Agent, only LLM component in pipeline
2. **Input format**: Structured anomaly data from Perception (scenario, severity, risk_score)
3. **Decision criteria matrix** (priority order):
   - PQC / integrity failure → `QUARANTINE`
   - Policy violation → `BLOCK`
   - severity > 0.8 → `ROLLBACK`
   - severity 0.6–0.8 + active failure → `BLOCK` or `ROLLBACK`
   - severity 0.3–0.6 → `ESCALATE`
   - severity < 0.3 → `NO_OP`
4. **Process**: perceive_anomaly → query_recent_decisions (optional) → one action tool
5. **Rationale requirements**: must cite severity, criterion, scenario
6. **Constraints**: tool-only output, no free text, no multiple actions

Few-shot examples are loaded from `few_shot_*.txt` files (sorted alphabetically)
and appended to the system prompt under a `## Few-Shot Examples` section.

Assembly is handled by `_build_instruction()` in `cogniops_agent.py`:
```python
instruction = _load_prompt("system.txt") + "\n\n## Few-Shot Examples\n\n" + _load_few_shots()
```

### 7.3 LLM Call Flow

```
                                      ┌──────────────────────┐
                                      │   Prompt Assembly     │
                                      │                       │
                   system.txt ───────►│  1. Load system prompt │
                   few_shot_*.txt ───►│  2. Inject few-shot   │
                   Session.state ────►│  3. Inject context     │
                   RuntimeEvent ─────►│  4. Inject event       │
                                      └──────────┬────────────┘
                                                  │
                                                  ▼
                                      ┌──────────────────────┐
                                      │   Vertex AI Gemini    │
                                      │   (gemini-2.0-flash)  │
                                      │                       │
                                      │   Function Calling    │
                                      │   → tool_name + args  │
                                      └──────────┬────────────┘
                                                  │
                                                  ▼
                                      ┌──────────────────────┐
                                      │   ADK Validation      │
                                      │                       │
                                      │  1. Schema check      │
                                      │  2. Tool exists?      │
                                      │  3. Args valid?       │
                                      └──────────┬────────────┘
                                                  │
                                                  ▼
                                      ┌──────────────────────┐
                                      │   before_tool_callback│
                                      │   (Guard)             │
                                      │                       │
                                      │  OPA + PQC + Mode     │
                                      └──────────┬────────────┘
                                                  │
                                          ┌───────┴───────┐
                                          │               │
                                       allowed         blocked
                                          │               │
                                          ▼               ▼
                                    Execute Tool     Log + NO_OP
```

---

## 8. Testing Architecture

### 8.1 Test Strategy

| Layer | Framework | Scope | External Services |
|-------|-----------|-------|-------------------|
| Unit (modules) | pytest | Individual functions, schemas | All mocked |
| Unit (agent) | ADK InMemoryRunner | Full ADK pipeline | No LLM calls (captured) |
| Integration (local) | pytest + httpx | HTTP endpoint + pipeline | BQ, Pub/Sub mocked |
| Integration (GCP) | Shell scripts | Real Pub/Sub → Cloud Run → BQ | Real GCP |
| Evaluation | ADK eval framework | LLM quality assessment | Real Gemini |

### 8.2 ADK InMemoryRunner Tests

```python
from google.adk.testing import InMemoryRunner

async def test_pipeline_failure_triggers_rollback():
    """Given a critical pipeline failure, agent should select ROLLBACK."""
    runner = InMemoryRunner(agent=cogniops_agent)
    session = runner.create_session()

    # Inject perception context
    session.state["current_event"] = mock_critical_pipeline_failure()
    session.state["recent_decisions"] = []
    session.state["current_mode"] = "enforce"

    result = await runner.run(session, input="Analyze the current event")

    assert result.tool_calls[-1].name == "trigger_rollback"
    assert result.tool_calls[0].name == "detect_anomaly"
```

### 8.3 Mocking Strategy

| External Service | Mock Method | Scope |
|------------------|-------------|-------|
| BigQuery | `unittest.mock.patch` on client | Unit tests |
| Pub/Sub | Not called directly by agent | N/A |
| Vertex AI Gemini | ADK InMemoryRunner (captured) | Agent tests |
| OPA | Mock HTTP response | Guard tests |
| GitHub API | Mock responses | Execution tests |
| GCP Secret Manager | Environment variables | All tests |

---

## 9. Deployment Architecture

### 9.1 Runtime Agent Deployment

```
Source (GitHub)
    │
    ├── Push to main → GHA workflow
    │       │
    │       ├── Build Docker image
    │       ├── Run tests (pytest)
    │       ├── Push to Artifact Registry
    │       └── Deploy to Cloud Run
    │
    └── Pub/Sub push subscription → OIDC auth → POST /events/runtime
```

### 9.2 Environment Configuration

| Variable | Source | Purpose |
|----------|--------|---------|
| `GCP_PROJECT_ID` | Terraform | Project identification |
| `BQ_DATASET` | Terraform (`agent_metrics`) | BigQuery target |
| `AGENT_MODE` | Cloud Run env var | shadow / advisory / enforce |
| `LOG_LEVEL` | Cloud Run env var | Logging verbosity |
| `AGENTOPS_API_KEY` | Secret Manager | Telemetry key (optional) |
| `AGENTOPS_ENABLED` | Cloud Run env var | Telemetry toggle |
| `OPA_ENDPOINT` | Cloud Run env var | OPA policy server URL |

### 9.3 Infrastructure Requirements (Terraform)

All infrastructure is defined in `infra/runtime.tf` (additive to `main.tf`):

| Resource | Purpose | Status |
|----------|---------|--------|
| `runtime-agent-sa` | Service account | ✅ Deployed |
| IAM bindings (6) | Least-privilege roles | ✅ Deployed |
| `runtime-events-v1` | Pub/Sub topic | ✅ Deployed |
| `runtime-events-v1-dlq` | Dead letter queue | ✅ Deployed |
| Push subscription | OIDC-auth to Cloud Run | ✅ Deployed |
| `runtime_decisions` | BQ table (12 fields) | ✅ Deployed |
| Cloud Run v2 | Agent service | ✅ Deployed |
| Design-Time infra | SA, BQ, GCS, Cloud Scheduler | ✅ `infra/design.tf` |

---

## 10. Implementation Roadmap

```
Phase 0 ✅ ──── Phase 1 ✅ ────────────────── Phase 2 ✅ ── Phase 3 ✅
                │                              │              │
           Step 1: ADK Bootstrap ✅       Step 6: Design ✅  Step 7: Eval ✅
           Step 2: Perception ✅              Agent (97 tests)
           Step 3: Planning (LLM) ✅     Step 7: 2-Axis ✅
           Step 4: Guard + Execution ✅       (59 tests)
           Step 5: Telemetry ✅
           Step 5b: Deploy & Wire ✅
           Step 6b: Security Agent ✅
```

### Step Dependencies

```
Step 0 (Copilot governance) ✅
    └── Step 1 (ADK bootstrap)
            ├── Step 2 (Perception) ← independent of Step 3
            └── Step 3 (Planning LLM)
                    └── Step 4 (Guard + Execution)
                            └── Step 5 (Telemetry)
                                    └── Step 6 (Design Agent) ← can start after Step 3
                                            └── Step 7 (Evaluation) ← requires all Steps
```

### Milestone Criteria

| Step | Exit Criteria |
|------|---------------|
| Step 1 | ADK LlmAgent runs in InMemoryRunner, FastAPI coexists, 38 tests pass | ✅ |
| Step 2 | Perception detects anomalies against real BQ baselines (mocked in tests) | ✅ |
| Step 3 | Gemini selects correct tool for 90%+ of test cases, fallback works | ✅ |
| Step 4 | OPA guard blocks invalid actions, mode gating works for all 3 modes | ✅ |
| Step 5 | Every LLM call logged, ActionTraces emitted, ACR validated | ✅ |
| Step 5b | Deploy & Wire: IaC, CI/CD, OPA bundle, config store (231 tests) | ✅ |
| Step 6 | Design agent produces valid JSON proposals, validator passes (97 tests) | ✅ |
| Step 6b | Security compliance agent: NIST feed → diff → propose (propose-only) | ✅ |
| Step 7 | Statistical comparison: Mann-Whitney U, Cohen's d, Bootstrap CI (59 tests) | ✅ |

---

## 11. VS Code Copilot Development Architecture

### 11.1 Two-Tool System

The project uses a **two-tool AI architecture**:

| Layer | Tool | Role |
|-------|------|------|
| **Development Tool** | VS Code Copilot | Assists in writing CogniOps code with governance guardrails |
| **Runtime System** | CogniOps (ADK + Gemini) | The AI agent being built — runs in production |

Copilot **helps build** CogniOps. CogniOps **is** the AI system. They are separate.

### 11.2 Copilot Governance Files

```
.github/
├── copilot-instructions.md              # Workspace-wide governance (always loaded)
├── instructions/
│   ├── runtime-agent.instructions.md    # Auto-loads for runtime-agent/** files
│   ├── baseline.instructions.md         # Auto-loads for baseline/** files
│   └── terraform.instructions.md        # Auto-loads for infra/** files
├── prompts/
│   ├── implement-cogniops.prompt.md     # Master orchestrator (Step selection)
│   ├── step1-adk-bootstrap.prompt.md    # Step 1 implementation prompt
│   ├── step2-perception.prompt.md       # Step 2 implementation prompt
│   ├── step3-planning-llm.prompt.md     # Step 3 prompt (→ @llm-specialist)
│   ├── step4-guard-execution.prompt.md  # Step 4 implementation prompt
│   ├── step5-telemetry.prompt.md        # Step 5 implementation prompt
│   ├── step6-design-agent.prompt.md     # Step 6 implementation prompt
│   └── step7-evaluation.prompt.md       # Step 7 prompt (→ @evaluator)
└── agents/
    ├── llm-specialist.agent.md          # ADK/Gemini/prompt engineering expert
    ├── evaluator.agent.md               # BQ metrics/statistical analysis expert
    └── security-reviewer.agent.md       # OPA/PQC/IAM/secrets reviewer
```

### 11.3 How Copilot Governance Enforces Architecture

| Governance Rule | Enforced By |
|----------------|-------------|
| Baseline immutability | `baseline.instructions.md` (forbidden actions list) |
| LLM confinement | `copilot-instructions.md` + `runtime-agent.instructions.md` |
| Bounded actions | `copilot-instructions.md` (enum list) + all step prompts |
| Fail-safe NO_OP | Every step prompt includes fallback requirement |
| Shadow-first mode | `copilot-instructions.md` + `step4-guard-execution.prompt.md` |
| Additive-only infra | `terraform.instructions.md` (explicit rules) |
| Security review | `@security-reviewer` agent (read-only, audit checklist) |

---

## 12. Cross-References

| Document | Purpose | Location |
|----------|---------|----------|
| AI Audit Report | Pre-implementation baseline state | [docs/ai-audit-report.md](ai-audit-report.md) |
| System Guardrails | Safety constraints and invariants | [docs/system-guardrails.md](system-guardrails.md) |
| Runtime Event Contract | Event schema and scenario mapping | [docs/runtime-event-contract.md](runtime-event-contract.md) |
| Phase 0 Spec | Runtime-ready infrastructure spec | [docs/phase0-runtime-ready-spec.md](phase0-runtime-ready-spec.md) |
| Phase 0 Implementation | Commit history and notes | [docs/phase0-implementation-notes.md](phase0-implementation-notes.md) |
| Runtime Agent IAM | Service account roles | [docs/runtime_agent_iam.md](runtime_agent_iam.md) |
| Copilot Governance | Development-time guardrails | [.github/copilot-instructions.md](../.github/copilot-instructions.md) |

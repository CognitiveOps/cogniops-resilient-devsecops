# CogniOps — Project Governance & AI Engineering Standards

## Project Identity
MSc Thesis: "Autonomous Cognitive AI Agent for Resilient DevSecOps Environments"
Repository: cogniops-resilient-devsecops
Architecture: Hybrid Cognitive-SOAR pattern with 2-Axis Evaluation Model

## Architecture Overview

### Two-Layer System
1. **Deterministic Substrate** — Baseline DevSecOps scenarios S1–S5, SS1–SS2
   - GitHub Actions pipelines, OPA policies, PQC validation, OTA deployment
   - IMMUTABLE — never add AI/LLM logic to baseline components
   - Emits metrics to BigQuery `agent_metrics.runs`

2. **Cognitive Control Plane** — AI-driven reasoning (runtime + design-time)
   - Runtime Agent: operational mitigation (anomaly → bounded action)
   - Design-Time Agent: structural synthesis (metrics → improvement proposals)
   - Both use Google ADK (Agent Development Kit) + Vertex AI Gemini

### Runtime Agent Pipeline (ADK-based)
```
Event → Perception (deterministic tool) → Planning (LlmAgent + Gemini)
      → Guard (before_tool_callback: OPA + PQC) → Execution (tools)
```

### Design-Time Agent Pipeline (ADK-based)
```
Metrics → Context Builder → Intent Processor → Planning (LlmAgent)
        → Validation (OPA sim + YAML lint + dry-run) → Output (JSON proposal)
```

### Critical Separation
- Runtime NEVER edits structure (no PR, no YAML changes)
- Design-Time NEVER executes mitigation (no rollback, no block)
- LLM used ONLY in Planning agents — all other modules deterministic
- Every LLM call must have: fallback to NO_OP, audit logging, schema validation

## Code Conventions

### Python
- Python 3.12, type hints on all public functions
- Pydantic v2 for all schemas (I/O validation, LLM structured output)
- FastAPI for HTTP endpoints
- `from __future__ import annotations` in all modules

### AI/LLM
- Google ADK (`google-adk`) for agent orchestration
- Vertex AI Gemini for LLM reasoning (via ADK, not raw SDK)
- Structured output via ADK tool definitions — never free-text generation
- Prompts are code: version-controlled in `prompts/` directories
- Every LLM response validated against Pydantic schema before use
- Fallback on any LLM failure: NO_OP (safe default, zero operational risk)

### Security
- No secrets in code — use GCP Secret Manager
- PQC validation via liboqs (FIPS 203–205: Dilithium, SPHINCS+)
- OPA policies for deployment guardrails
- IAM least-privilege for all service accounts
- No `--no-verify`, no force-push, no bypassing safety checks

### Testing
- `pytest` for unit tests, `httpx` for async endpoint tests
- Mock all external services (BQ, Pub/Sub, LLM, OPA) in unit tests
- ADK `InMemoryRunner` for deterministic agent pipeline tests
- Integration tests with real GCP only via `scripts/`
- Every new module must have corresponding test file

## Project Structure
```
baseline/            — Deterministic substrate (IMMUTABLE for AI changes)
runtime-agent/       — Phase 1+ Cognitive Runtime System (ADK-based)
design-agent/        — Phase 2 Design-Time Agent (ADK-based)
security-agent/      — Step 6b Security Compliance Agent (ADK-based, propose-only)
evaluation/          — Phase 4 2-Axis evaluation framework
infra/               — Terraform IaC (additive only for new phases)
functions/           — Cloud Functions (ingest endpoints)
security/            — OPA policies
docs/                — Architecture specs, event contracts
.github/workflows/   — GitHub Actions (S1–SS2 baseline pipelines)
```

## Bounded Action Surface (Runtime Agent)
The Planning agent may ONLY select from these actions:
- `NO_OP` — No action (safe default)
- `BLOCK` — Block a deployment
- `ROLLBACK` — Trigger rollback workflow
- `QUARANTINE` — Quarantine suspect artifact
- `ESCALATE` — Create HITL issue for human review

No other actions may be generated or executed.

## Mode Progression
- `shadow` — Decisions logged only (no execution)
- `advisory` — Decisions logged + human notified
- `enforce` — Decisions logged + executed

Always start new capabilities in `shadow` mode.

## BigQuery Tables
- `agent_metrics.runs` — Baseline scenario metrics (IMMUTABLE schema)
- `agent_metrics.s1_pipeline_runs` — S1 specific (IMMUTABLE schema)
- `agent_metrics.runtime_decisions` — Agent decisions (extendable)

## Scenario → Metric Matrix
| Scenario | Metrics |
|---|---|
| S1 (CI/CD) | TTD, CFR, DF |
| S2 (Edge OTA) | TDL, DSR, TTD_edge |
| S3 (Resilience) | MTTD, MTTR |
| S4 (PQC) | TTV, VSR, FDR |
| S5 (Explainability) | AL, ACR |
| SS1 (Policy Audit) | CFR, DF, FDR, ACR |
| SS2 (Adaptive Threat) | MTTD, AL, ACR |

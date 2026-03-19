---
description: "Use when modifying design-agent modules: context builder, proposal generator, validator, design agent, or design-agent tests"
applyTo: "design-agent/**"
---
# Design-Time Agent — Module Guidelines

## Architecture (ADK-based)
The design-agent is a FastAPI batch service on Cloud Run triggered by Cloud Scheduler:
```
Cloud Scheduler → POST /run → Context Builder (BQ + GCS)
  → Design Planner (LlmAgent + Gemini) → Proposal Generator → Validator
  → GCS proposal JSON + GitHub Issue
```

## Module Responsibilities

### Context Builder (`agent/tools/context_builder.py`)
- DETERMINISTIC — no LLM here
- Queries BQ `agent_metrics.runs` for scenario metric trends (30-day window)
- Queries BQ `agent_metrics.runtime_decisions` for decision patterns
- Reads thresholds from GCS config bucket
- Classifies trends: improving (>10% decrease), degrading (>10% increase), stable
- Fail-safe: BQ/GCS errors → empty results + warning log (never raises)

### Design Planner (`agent/design_agent.py`)
- THE ONLY module that uses LLM (Gemini via ADK)
- Input: AnalysisContext (metrics, decisions, thresholds)
- Output: tool call to `generate_proposal` or `no_proposal_needed`
- System prompt in `agent/prompts/design_system.txt`
- 2 few-shot examples: MTTR optimization, FDR policy improvement

### Proposal Generator (`agent/tools/proposal_generator.py`)
- DETERMINISTIC — no LLM here
- Assembles `DesignProposal` with unique ID, changes, impact estimates
- Normalizes and clamps confidence scores to [0.0, 1.0]
- `no_proposal_needed()`: logs reason, returns status dict

### Validator (`agent/tools/validator.py`)
- DETERMINISTIC — no LLM here
- Checks: required fields, change type validity, path traversal guard
- Checks: intent quality (≥10 chars), analysis quality (≥20 chars)
- Checks: confidence bounds, `requires_human_review=True` enforced
- YAML lint for workflow/config changes
- Invalid proposals → discarded, errors logged

### Entry Point (`main.py`)
- FastAPI: POST /run (trigger analysis), GET /healthz, GET /agent/info
- ADK InMemoryRunner with auto_create_session
- Writes validated proposals to GCS + creates GitHub Issue
- LLM failure → no proposal (zero operational risk)

## Critical Constraints
- **NEVER** execute mitigation actions (no rollback, block, quarantine)
- **NEVER** modify live infrastructure, create branches, or PRs
- **NEVER** write to BigQuery — read-only access (dataViewer)
- All proposals must pass validation before GCS storage
- `requires_human_review` is `Literal[True]` — Pydantic rejects any other value
- Separate SA from runtime-agent and compliance-agent

## Schemas (`models/schemas.py`)
All I/O validated via Pydantic v2:
- `AnalysisContext`: metrics, decisions, thresholds, window
- `DesignProposal`: intent, changes, impact, validation, human review flag
- `ProposedChange`: type, target file, description, proposed value, rationale
- `ValidationResult`: valid, checks_passed, errors, warnings

## Testing
- Mock all BQ/GCS/LLM calls in tests
- Use `unittest.mock.patch` for external dependencies
- Test validator exhaustively (path traversal, confidence bounds, YAML lint)
- Every new module must have a corresponding test file

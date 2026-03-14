---
description: "Use when modifying security-agent modules: feed ingestion, diff engine, proposal builder, validator, compliance agent, or security-agent tests"
applyTo: "security-agent/**"
---
# Security Compliance Agent — Module Guidelines

## Architecture (ADK-based)
The security-agent is a FastAPI batch service on Cloud Run triggered by Cloud Scheduler:
```
Cloud Scheduler → POST /run → Feed Ingestion → Diff Engine → Enrich
  → Compliance Planner (LlmAgent + Gemini) → Validator → GCS + GitHub Issue
```

## Module Responsibilities

### Feed Ingestion (`agent/tools/nist_feed.py`)
- DETERMINISTIC — no LLM here
- NIST NVD API v2: CVE updates filtered by tracked controls
- NIST SP 800-53 CPRT: control definition revisions
- `fetch_control_detail()`: full text fetch for enrichment (Stage 2)
- Fail-safe: API errors → empty list + warning log (never raises)
- Rate limit aware: 5 req/30s (no key), 50 req/30s (with NIST_API_KEY)

### Diff Engine (`agent/tools/diff_engine.py`)
- DETERMINISTIC — no LLM here
- Compares feed entries against current `control-mappings.yaml`
- Classifies: updated (revision change) vs new (not in YAML)
- `enrich_diff()`: fetches full control text only for changed entries
- Produces `DiffReport` with `EnrichedEntry` objects

### Compliance Planner (`agent/compliance_agent.py`)
- THE ONLY module that uses LLM (Gemini via ADK)
- Input: EnrichedDiffReport (full control text + guidance + related controls)
- Output: tool call to `evaluate_and_propose` or `no_proposal_needed`
- System prompt in `agent/prompts/compliance_system.txt`
- FALLBACK: if LLM fails → fallback proposal (confidence 0.3)

### Proposal Builder (`agent/tools/proposal_builder.py`)
- DETERMINISTIC — no LLM here
- Assembles `ComplianceProposal` from diff report + LLM output
- YAML patch construction: ref entries with revision updates
- Unique proposal IDs: `comp-{date}-{uuid8}`

### Validator (`agent/tools/validator.py`)
- DETERMINISTIC — no LLM here
- YAML schema: valid decision types, non-empty refs
- Superset-only: proposals can only add/update, never remove refs
- Confidence threshold: below 0.3 → warning
- `requires_human_review = True`: enforced by Literal[True] in schema

## Key Constraints
- NEVER execute changes — propose-only (JSON in GCS + GitHub Issues)
- NEVER modify baseline code (baseline/, .github/workflows/s*.yml)
- All Pydantic models in `models/schemas.py`
- System prompt in `agent/prompts/` (version-controlled)
- Every LLM response validated against Pydantic schema
- Every new module needs a test file in `tests/`
- Mock all external APIs (NIST, GCS, GitHub) in unit tests
- Separate service account: `compliance-agent-sa` (never share with runtime-agent)

## Bounded Output Surface
The compliance agent may ONLY produce:
- `ComplianceProposal` JSON → GCS
- GitHub Issue → human-readable summary
- `no_op` → no changes detected
No other outputs may be generated or stored.

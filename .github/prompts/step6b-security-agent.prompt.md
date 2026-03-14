---
description: "Security Compliance Agent: NIST feed ingestion, diff engine, LLM-based compliance analysis, proposal generation, and deterministic validation."
agent: "agent"
---

# Step 6b: Security Compliance Agent

Read first:
- [Project governance](../copilot-instructions.md)
- [Security-agent instructions](../instructions/security-agent.instructions.md)
- [Terraform instructions](../instructions/terraform.instructions.md)
- [Runtime agent instructions](../instructions/runtime-agent.instructions.md) (reference pattern)
- [Existing control-mappings.yaml](../../config/control-mappings.yaml) (NIST/ISO/IMO refs)
- [Existing OPA policies](../../security/policies/cogniops_runtime.rego) (runtime guardrails)
- [Step 5b prompt](step5b-deploy-wire.prompt.md) (GCS config store, live config architecture)
- [AI design architecture](../../docs/ai-design-architecture.md) (Design-Time Agent spec §5)

## Task

Build a Security Compliance Agent that automatically monitors NIST regulatory feeds and proposes updates to CogniOps compliance configuration. **Propose-only — never executes changes.**

## Pipeline

```
Cloud Scheduler (weekly Mon 06:00 UTC)
         │
         ▼
  Feed Ingestion (deterministic)         ← nist_feed.py
  ├── NIST NVD API v2 → CVE updates
  ├── NIST SP 800-53 CPRT → control revisions
  └── Fail-safe: API down → skip cycle
         │
         ▼
  Diff Engine (deterministic)            ← diff_engine.py
  ├── Compare feed vs current control-mappings.yaml
  ├── 2-stage: fast diff → full text fetch (only relevant)
  └── Output: EnrichedDiffReport
         │
         ▼
  Compliance Planner (LlmAgent)          ← compliance_agent.py (ONLY LLM step)
  ├── Analyze full control text
  ├── Map to decision types + scenarios
  └── Structured output: evaluate_and_propose tool call
         │
         ▼
  Validator (deterministic)              ← validator.py
  ├── YAML schema + superset-only check
  ├── Confidence threshold + Pydantic
  └── requires_human_review = always True
         │
         ▼
  Output (deterministic)
  ├── GCS: proposals/compliance/{date}/{id}.json
  └── GitHub Issue: summary + proposed diff
```

## Implementation

### 1. Models — `security-agent/models/schemas.py`

| Schema | Purpose |
|--------|---------|
| `FeedEntry` | Single NIST feed update (NVD or SP 800-53) |
| `ControlDetail` | Full text from CPRT (element_text, guidance, related_controls) |
| `EnrichedEntry` | Feed entry + full control text for LLM analysis |
| `DiffReport` | Updated + new entries, affected decision types |
| `YAMLPatch` / `YAMLPatchEntry` | Proposed changes to control-mappings.yaml |
| `ComplianceProposal` | Full proposal: diff + patch + impact + confidence |
| `ValidationResult` | Pass/fail with errors and warnings |
| `FeedSnapshot` / `LastCheckRecord` | GCS caching for feed state |

### 2. Feed Ingestion — `security-agent/agent/tools/nist_feed.py`

- `fetch_nvd_updates(since)`: NVD API v2, filtered by tracked control keywords
- `fetch_sp800_53_controls()`: CPRT catalog, filtered to tracked IDs (CM-3, CP-10, SI-3, IR-6)
- `fetch_control_detail(control_id)`: Full text fetch for enrichment (Stage 2)
- `ingest_feeds(since)`: Combined concurrent fetch + deduplication
- All fail-safe: API errors → empty list, never raises

### 3. Diff Engine — `security-agent/agent/tools/diff_engine.py`

- `compute_diff(feed_entries, current_yaml)`: Deterministic comparison
- `enrich_diff(diff)`: Fetches full control text only for changed entries
- Regex-based ref extraction: `SP 800-53 CM-3` → `CM-3`
- Superset-safe: only flags additions and updates

### 4. Compliance Planner — `security-agent/agent/compliance_agent.py`

ADK `LlmAgent` with Gemini. Two tools:
- `evaluate_and_propose(impact_assessment, confidence, decision_type_assignments, rego_suggestions)`
- `no_proposal_needed(reason)`

System prompt: scenario-metric matrix, control mapping context, output rules.

### 5. Validator — `security-agent/agent/tools/validator.py`

Deterministic checks:
- Decision type validity (only BLOCK, ROLLBACK, QUARANTINE, ESCALATE, NO_OP)
- Non-empty refs, impact assessment length ≥ 20 chars
- Confidence ≥ 0.3 (warning below)
- Superset-only: cannot remove existing refs
- `requires_human_review` must be True

### 6. Entry Point — `security-agent/main.py`

FastAPI with ADK InMemoryRunner:
- `POST /run` — Full pipeline (Cloud Scheduler trigger)
- `GET /healthz` — Liveness/readiness probe
- `GET /agent/info` — ADK agent metadata

### 7. IaC — `infra/compliance.tf`

| Resource | Purpose |
|----------|---------|
| `compliance-agent-sa` | Separate SA, least-privilege |
| Cloud Run `security-compliance-agent` | Internal-only, max 1 instance |
| Cloud Scheduler `compliance-agent-weekly` | Monday 06:00 UTC |
| Secret `compliance-agent-nist-api-key` | Optional NIST API key |
| IAM bindings | GCS read/write, secrets, AR, logging |

Variable: `compliance_agent_image` in `variables.tf`.

### 8. CI/CD — `.github/workflows/compliance_agent_deploy.yml`

4-job pipeline: test → build-push → deploy (main only) → smoke-test

### 9. Tests — 68 total

| File | Count | Covers |
|------|------:|--------|
| `test_schemas.py` | 15 | Pydantic model validation, Literal[True] enforcement |
| `test_nist_feed.py` | 13 | Mocked NVD + CPRT APIs, fail-safe, deduplication |
| `test_diff_engine.py` | 14 | Revision detection, new controls, empty cases, sorting |
| `test_proposal_builder.py` | 10 | Patch construction, confidence clamping, unique IDs |
| `test_validator.py` | 11 | Schema checks, superset rule, confidence threshold |
| `test_compliance_pipeline.py` | 9 | E2E pipeline, ADK tools, LLM fallback |

## Design Rules

- **Propose-only**: Never modify files — only GCS JSON + GitHub Issues
- **LLM only in Planning**: Feed, diff, validator = deterministic Python
- **2-stage fetch**: Fast diff first, full text only for changed controls (2-4 API calls vs hundreds)
- **Fail-safe**: NIST down → skip; LLM down → fallback proposal (confidence 0.3)
- **`requires_human_review = True`**: Literal[True] in Pydantic — cannot be False
- **Separate SA**: `compliance-agent-sa`, never shares IAM with runtime-agent
- **No baseline changes**: Never modify `baseline/`, `.github/workflows/s*.yml`

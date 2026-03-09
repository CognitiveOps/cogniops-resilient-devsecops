# System Design Guardrails

> CogniOps — Autonomous Cognitive AI Agent for Resilient DevSecOps Environments  
> Version: 1.0  
> Last Updated: 2026-03-09  
> Status: Binding — All implementation MUST comply with these constraints

---

## 1. Purpose

This document defines the **safety invariants, security constraints, and design
boundaries** that govern the CogniOps AI system. These guardrails are non-negotiable
during implementation and must be verifiable through automated checks, code review,
or runtime enforcement.

Every guardrail maps to a **threat model** (what could go wrong) and an **enforcement
mechanism** (how we prevent it).

---

## 2. Guardrail Classification

| Category | Scope | Enforcement |
|----------|-------|-------------|
| **Safety** (S) | Prevent AI from causing operational harm | Code constraints + runtime checks |
| **Security** (Sec) | Prevent unauthorized access and data compromise | IAM + OPA + PQC |
| **Integrity** (I) | Prevent corruption of baseline or data | Immutability rules + schema locks |
| **Accountability** (A) | Ensure every action is traceable | Logging + explainability kit |
| **Correctness** (C) | Ensure AI outputs are valid | Schema validation + testing |

---

## 3. Safety Guardrails

### S-1: Bounded Action Surface

**Threat**: LLM generates arbitrary actions beyond the designed set, causing
unpredictable operational effects.

**Guardrail**: The Planning agent may ONLY select from exactly five actions:

| Action | Enum Value | Description |
|--------|------------|-------------|
| No Operation | `NO_OP` | Safe default — log only |
| Block Deployment | `BLOCK` | Prevent a deployment from proceeding |
| Trigger Rollback | `ROLLBACK` | Revert to last known-good state |
| Quarantine Artifact | `QUARANTINE` | Isolate suspect artifact |
| Escalate to Human | `ESCALATE` | Create HITL issue for review |

**Enforcement**:
- `DecisionType` is a Python `enum.Enum` with exactly 5 values
  ([models/schemas.py](../runtime-agent/models/schemas.py))
- ADK tools map 1:1 to these actions — no other tools exist
- LLM uses function calling — can only select defined tools
- Any output not matching a tool → rejected by ADK automatically
- Pydantic validation on `PlanningDecision.decision` field

**Verification**: Unit test asserts `len(DecisionType) == 5`.

---

### S-2: Fail-Safe Default (NO_OP)

**Threat**: LLM fails (timeout, error, malformed response), and the system takes
an uncontrolled action or crashes.

**Guardrail**: Any failure in the AI pipeline defaults to `NO_OP` (zero operational risk).

**Failure Scenarios and Responses**:

| Failure | Response | Risk |
|---------|----------|------|
| LLM timeout | Return `NO_OP` with rationale "LLM timeout" | Zero |
| LLM returns invalid tool call | Reject, return `NO_OP` | Zero |
| LLM returns empty response | Return `NO_OP` | Zero |
| OPA check fails (network) | Block execution, return `NO_OP` | Zero |
| BQ query fails (perception) | Return `severity=0.5` (neutral), `NO_OP` | Zero |
| PQC verification fails | Block execution, return `NO_OP` | Zero |
| Guard exception | Catch, log, return `NO_OP` | Zero |
| Unhandled exception | FastAPI error handler returns 500, Pub/Sub retries | Events may replay |

**Enforcement**:
- `try/except` around all LLM calls with `NO_OP` in except block
- Default values in Pydantic schemas are all safe (NO_OP, approved=True for stubs)
- ADK error callback configured to return NO_OP
- BQ write is best-effort (failure logged, doesn't block pipeline)

**Verification**: Integration test injects LLM timeout, asserts NO_OP returned.

---

### S-3: Mode Progression (Shadow → Advisory → Enforce)

**Threat**: AI agent executes destructive actions before its decision quality is validated.

**Guardrail**: Three operational modes, always starting at shadow:

| Mode | Decisions Logged | Human Notified | Actions Executed |
|------|-----------------|----------------|-----------------|
| `shadow` | ✅ | ❌ | ❌ |
| `advisory` | ✅ | ✅ (GitHub Issue) | ❌ |
| `enforce` | ✅ | ✅ | ✅ |

**Progression Rules**:
1. Every new capability starts in `shadow` mode
2. Promotion to `advisory` requires: ≥100 shadow decisions reviewed, <5% unexpected
3. Promotion to `enforce` requires: ≥100 advisory decisions with human approval rate >90%
4. Mode is set via `AGENT_MODE` environment variable — never auto-escalated
5. Mode changes require human review and explicit deployment

**Enforcement**:
- Every execution tool checks `AGENT_MODE` before acting
- Shadow mode: log intent → return success without executing
- Advisory mode: log + create GitHub Issue notification
- Enforce mode: log + execute + verify
- Cloud Run env var `AGENT_MODE` set via Terraform (not runtime-configurable)

**Verification**: Unit test for each tool in each mode. Integration test: shadow
mode event → verify BQ row shows `decision_executed=False`.

---

### S-4: LLM Confinement

**Threat**: LLM reasoning spreads to modules beyond Planning, making the system
unpredictable and hard to audit.

**Guardrail**: LLM is used **exclusively** in the Planning module. All other modules
are deterministic Python code.

| Module | LLM Allowed | Rationale |
|--------|-------------|-----------|
| Perception | ❌ | Anomaly detection is mathematical (z-score, thresholds) |
| **Planning** | **✅** | Action selection requires reasoning about context |
| Guard | ❌ | Policy check is rule-based (OPA evaluation) |
| Execution | ❌ | Action dispatch is mechanical (API calls) |
| Storage | ❌ | BQ writes are deterministic |
| Telemetry | ❌ | Logging is deterministic |

**Enforcement**:
- Code review: no `google.adk`, `vertexai`, or LLM imports outside `agent/cogniops_agent.py`
- `.github/instructions/runtime-agent.instructions.md` instructs Copilot to reject LLM code
  in non-Planning modules
- Grep check in CI: `grep -r "vertexai\|genai\|LlmAgent" --include="*.py" | grep -v agent/`
  must return empty

**Verification**: CI step or pre-commit hook that scans for LLM imports outside `agent/`.

---

### S-5: Runtime/Design-Time Separation

**Threat**: Runtime agent modifies infrastructure or code; Design-time agent executes
operational actions — both violate their intended scope.

**Guardrail**:

| Capability | Runtime Agent | Design-Time Agent |
|------------|---------------|-------------------|
| Execute BLOCK / ROLLBACK | ✅ | ❌ |
| Create HITL issue | ✅ | ❌ |
| Generate config proposals | ❌ | ✅ |
| Read BQ metrics | ✅ | ✅ |
| Write to BQ | ✅ (runtime_decisions) | ✅ (design_proposals) |
| Modify files / YAML / config | ❌ | ❌ (propose only) |
| Push to Git | ❌ | ❌ |

**Enforcement**:
- Separate service accounts with distinct IAM roles
- Separate Cloud Run services (no shared execution context)
- ADK tool sets are disjoint — Runtime has execution tools, Design-time has proposal tools
- Design-time output is JSON to GCS — no write access to production resources

---

## 4. Security Guardrails

### Sec-1: No Secrets in Code

**Threat**: API keys, tokens, or credentials committed to the repository.

**Guardrail**: All secrets stored in GCP Secret Manager, accessed via IAM at runtime.

**Enforcement**:
- `runtime-agent-sa` has `roles/secretmanager.secretAccessor`
- Secrets referenced by name, never by value
- `.gitignore` excludes sensitive files
- No `key.json` usage in production (OIDC tokens only)
- Code review: reject any PR containing literal keys or tokens

---

### Sec-2: IAM Least-Privilege

**Threat**: Over-privileged service accounts allow lateral movement or data exfiltration.

**Guardrail**: Every service account has the minimum roles required for its function.

| Service Account | Roles | Scope |
|-----------------|-------|-------|
| `runtime-agent-sa` | logWriter, metricWriter | Project |
| `runtime-agent-sa` | bqEditor | `agent_metrics` dataset only |
| `runtime-agent-sa` | secretAccessor | Specific secrets |
| `runtime-agent-sa` | arReader | Project (pull images) |
| `runtime-agent-sa` | run.invoker | Self (Pub/Sub push) |
| `design-agent-sa` | bqViewer | `agent_metrics` dataset only |
| `design-agent-sa` | storage.objectCreator | Proposals bucket only |
| `gha-app` | pubsub.publisher | `runtime-events-v1` topic only |

**Enforcement**: Defined in `infra/runtime.tf`, reviewed in `@security-reviewer` agent.

---

### Sec-3: OPA Policy Enforcement

**Threat**: Agent takes actions that violate organizational policies (deploys to
wrong region, uses unauthorized service account, etc.).

**Guardrail**: OPA policies evaluate every execution action before it proceeds.

**Enforcement**:
- `guard_callback` calls OPA with the action context
- OPA policies defined in `security/policies/` (version-controlled)
- Deny reasons are logged and included in BQ decision row
- Guard blocks execution if any OPA `deny` rule fires

---

### Sec-4: Post-Quantum Cryptography (PQC) Integrity

**Threat**: Artifacts are tampered with between build and deployment, and the
agent acts on compromised data.

**Guardrail**: PQC signature verification (Dilithium2, FIPS 204) for artifact integrity.

**Enforcement**:
- `baseline/security/pqc/verify.py` validates signatures using liboqs
- Guard callback includes PQC check when artifact context is present
- Failed PQC verification → block execution, log reason, return NO_OP

---

### Sec-5: Prompt Injection Defense

**Threat**: Malicious data in runtime events contains instructions that manipulate
the LLM's reasoning.

**Guardrail**: Multi-layer defense:

| Layer | Defense | Implementation |
|-------|---------|----------------|
| Input | Schema validation | Pydantic rejects unexpected fields |
| Context | Sanitization | Event data injected as structured context, not raw text |
| LLM | System prompt hardening | Role and constraints defined in system prompt |
| Output | Tool-only output | LLM can only call predefined tools (no free text) |
| Guard | OPA evaluation | Actions validated against policy regardless of LLM reasoning |
| Fallback | Bounded surface | Even if injected, LLM can only select from 5 safe actions |

---

## 5. Data Integrity Guardrails

### I-1: Baseline Immutability

**Threat**: AI integration accidentally modifies baseline scenarios, metrics schemas,
or workflows, invalidating the before/after evaluation.

**Guardrail**: The following components are **IMMUTABLE** after baseline completion:

| Component | Location | Protected By |
|-----------|----------|-------------|
| Scenario workflows | `.github/workflows/` | Code review, `baseline.instructions.md` |
| BQ `runs` schema | `infra/main.tf` | Terraform state, `main.tf` is never edited |
| BQ `s1_pipeline_runs` schema | `infra/main.tf` | Terraform state |
| Ingestion function | `functions/ingest_runs/` | Separate deployment, not modified |
| OPA baseline policies | `security/policies/ss1.rego` | Version-controlled, additive changes only |
| PQC implementation | `baseline/security/pqc/` | No AI logic permitted |
| Explainability kit | `baseline/explainability/` | Extended (not modified) by agent |

**Enforcement**:
- `baseline.instructions.md` tells Copilot: "NEVER modify baseline components"
- `terraform.instructions.md` tells Copilot: "NEVER edit main.tf"
- Phase 1+ code goes in `runtime-agent/agent/` (new directory)
- Design-Time code goes in `design-agent/` (new directory)

**Verification**: `git diff --name-only main..HEAD | grep -E "^baseline/|^.github/workflows/"` must be empty.

---

### I-2: Additive-Only Infrastructure

**Threat**: Terraform changes destroy or modify existing resources, breaking the baseline.

**Guardrail**: All new infrastructure is **additive** — new files, new resources.

**Rules**:
1. Never modify `infra/main.tf` — add new `.tf` files instead
2. Reference existing resources by data source or resource name
3. No `terraform destroy` without explicit approval
4. No resource renaming (causes destroy+create)
5. Lifecycle `prevent_destroy = true` on critical resources

**Enforcement**: `terraform.instructions.md` + code review.

---

### I-3: Schema Validation at Every Boundary

**Threat**: Invalid data propagates through the pipeline, causing incorrect decisions
or corrupt BQ rows.

**Guardrail**: Pydantic v2 validation at every I/O boundary:

```
HTTP Input → PubSubPushEnvelope (validated)
         → RuntimeEvent (validated)
              → AnomalyOutput (validated)
                   → PlanningDecision (validated, LLM output)
                        → GuardVerdict (validated)
                             → ExecutionResult (validated)
                                  → DecisionRow (validated → BQ)
```

Every transition between modules is a Pydantic model boundary.

---

## 6. Accountability Guardrails

### A-1: Decision Audit Trail

**Threat**: Agent makes decisions that cannot be explained or reviewed after the fact.

**Guardrail**: Every decision is recorded with full context:

| Field | Content | Storage |
|-------|---------|---------|
| `event_id` | Source event UUID | BQ `runtime_decisions` |
| `event_type` | Event classification | BQ |
| `decision` | Action selected | BQ |
| `rationale` | Human-readable explanation | BQ |
| `policy_refs` | ISO/NIST controls referenced | BQ |
| `guard_approved` | Guard verdict | BQ |
| `decision_executed` | Whether action was taken | BQ |
| `mode` | shadow / advisory / enforce | BQ |
| `processed_at` | Processing timestamp | BQ (partition key) |

---

### A-2: LLM Call Logging

**Threat**: LLM behavior is opaque — no way to debug incorrect decisions.

**Guardrail**: Every LLM call is logged with:

| Field | Content |
|-------|---------|
| Prompt hash | SHA-256 of assembled prompt |
| Model version | e.g. `gemini-2.0-flash` |
| Response | Full tool call response |
| Latency | Wall-clock time (ms) |
| Token count | Input + output tokens |
| Fallback triggered | Boolean |
| Error | Error message if failed |

**Storage**: Cloud Logging (structured JSON) + optional AgentOps.

---

### A-3: Explainability Integration

**Threat**: Agent decisions don't have proper audit traces for compliance.

**Guardrail**: Every agent decision generates a CloudEvent ActionTrace compatible
with the existing explainability kit (`baseline/explainability/`).

**Fields**:
- `action_type`: decision enum value
- `rationale`: LLM-generated explanation
- `policy_refs`: ISO 27001, NIST SP 800-53, IMO MSC.428(98) control mappings
- `acr_valid`: audit completeness rate validation result

---

## 7. Correctness Guardrails

### C-1: Test Requirements

**Guardrail**: Every new module must have a corresponding test file.

| Module Type | Test Framework | Mocking |
|-------------|----------------|---------|
| Python function | pytest | unittest.mock |
| Pydantic schema | pytest | Direct instantiation |
| FastAPI endpoint | pytest + httpx | TestClient |
| ADK agent pipeline | ADK InMemoryRunner | Captured LLM interactions |
| Terraform resource | `terraform plan` | Dry-run |
| OPA policy | OPA test framework | `opa test` |

---

### C-2: LLM Output Validation

**Guardrail**: Every LLM response is validated against a Pydantic schema before
any action is taken.

```python
# Pseudocode for LLM output validation
try:
    llm_response = await agent.run(session)
    decision = PlanningDecision.model_validate(llm_response)
except ValidationError as e:
    logger.error(f"LLM output validation failed: {e}")
    decision = PlanningDecision(
        decision=DecisionType.NO_OP,
        rationale=f"LLM output validation failed: {e}",
    )
```

---

### C-3: ADK Evaluation Dataset

**Guardrail**: An evaluation dataset with expected outcomes is maintained and
run periodically to detect LLM quality regression.

```json
{
  "test_cases": [
    {
      "input": "Critical pipeline failure, CFR > 25%",
      "expected_tool": "trigger_rollback",
      "expected_rationale_contains": "critical"
    },
    {
      "input": "Normal metrics, all within baseline",
      "expected_tool": "no_action",
      "expected_rationale_contains": "within"
    }
  ]
}
```

---

## 8. Guardrail Enforcement Matrix

Summary of how each guardrail is enforced:

| ID | Guardrail | Design-Time | Code-Time | Runtime |
|----|-----------|-------------|-----------|---------|
| S-1 | Bounded Actions | Architecture doc | Enum type, ADK tools | Tool validation |
| S-2 | Fail-Safe NO_OP | Architecture doc | try/except, defaults | Exception handlers |
| S-3 | Mode Progression | Architecture doc | Mode check in tools | Env var + logging |
| S-4 | LLM Confinement | Architecture doc | Import scan, instructions | N/A (code-level) |
| S-5 | Agent Separation | Architecture doc | Separate repos/dirs | Separate SAs |
| Sec-1 | No Secrets | Policy | .gitignore, review | Secret Manager |
| Sec-2 | Least Privilege | IAM design | Terraform code | GCP IAM |
| Sec-3 | OPA Policies | Policy rules | Rego files | OPA evaluation |
| Sec-4 | PQC Integrity | Architecture doc | liboqs integration | Signature verification |
| Sec-5 | Prompt Injection | Threat model | Schema + sanitization | Bounded surface |
| I-1 | Baseline Immutability | Architecture doc | Instructions.md | CI check |
| I-2 | Additive Infra | Architecture doc | Instructions.md | Terraform plan |
| I-3 | Schema Validation | Architecture doc | Pydantic models | Runtime validation |
| A-1 | Decision Audit | Architecture doc | BQ writer | BQ table |
| A-2 | LLM Logging | Architecture doc | Logger module | Cloud Logging |
| A-3 | Explainability | Architecture doc | CloudEvents kit | ActionTrace |
| C-1 | Test Coverage | Architecture doc | pytest + InMemoryRunner | CI pipeline |
| C-2 | Output Validation | Architecture doc | Pydantic validation | Exception → NO_OP |
| C-3 | Eval Dataset | Architecture doc | JSON test cases | Periodic eval runs |

---

## 9. Compliance Mapping

### ISO 27001:2022

| Control | Guardrail(s) | Evidence |
|---------|-------------|----------|
| A.8.9 Configuration management | I-1, I-2 | Terraform IaC, baseline immutability |
| A.8.24 Use of cryptography | Sec-4 | PQC (Dilithium2, FIPS 204) |
| A.8.25 Secure development lifecycle | C-1, C-2 | pytest, schema validation, InMemoryRunner |
| A.5.23 Information security for cloud services | Sec-1, Sec-2 | Secret Manager, IAM least-privilege |
| A.8.16 Monitoring activities | A-1, A-2 | BQ audit trail, LLM call logging |

### NIST SP 800-53 Rev. 5

| Control | Guardrail(s) | Evidence |
|---------|-------------|----------|
| AC-6 Least Privilege | Sec-2 | IAM scoped roles per SA |
| AU-3 Content of Audit Records | A-1, A-2, A-3 | Decision rows, LLM logs, ActionTraces |
| CM-3 Configuration Change Control | I-1, I-2 | Immutability rules, additive infra |
| IA-7 Cryptographic Module Authentication | Sec-4 | liboqs / Dilithium2 (FIPS 204) |
| SI-10 Information Input Validation | I-3, C-2 | Pydantic schemas, LLM output validation |
| SA-15 Development Process | S-1–S-5, C-1 | Bounded actions, testing, instructions |

---

## 10. Cross-References

| Document | Relationship |
|----------|-------------|
| [AI Audit Report](ai-audit-report.md) | Baseline state these guardrails protect |
| [AI Design Architecture](ai-design-architecture.md) | Architecture these guardrails constrain |
| [Runtime Event Contract](runtime-event-contract.md) | Input schema for guardrail I-3 |
| [Runtime Agent IAM](runtime_agent_iam.md) | IAM design for guardrail Sec-2 |
| [Copilot Governance](../.github/copilot-instructions.md) | Development-time enforcement of all guardrails |
| [OPA Policies](../security/policies/ss1.rego) | Policy rules for guardrail Sec-3 |
| [PQC Backend](../baseline/security/pqc/backends.py) | Crypto implementation for guardrail Sec-4 |
| [Pydantic Schemas](../runtime-agent/models/schemas.py) | Validation models for guardrails I-3, C-2 |

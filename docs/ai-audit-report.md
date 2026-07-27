# AI System Audit Report

> CogniOps — Autonomous Cognitive AI Agent for Resilient DevSecOps Environments  
> Audit Date: 2026-03-09  
> Scope: Full repository assessment prior to AI/LLM integration  
> Auditor: AI Engineering Review (automated + human-directed)

---

## 1. Executive Summary

This audit assesses the CogniOps repository at the completion of Phase 0 (Runtime-Ready
Infrastructure) to establish a verified baseline before introducing AI/LLM capabilities.
The repository implements a deterministic DevSecOps substrate (scenarios S1–SS2) and a
shadow-mode runtime agent skeleton — all functional, tested, and deployed.

**Verdict**: Phase 0 is **complete and production-ready**. The codebase is structurally
sound, well-separated, and prepared for incremental AI integration starting with
Phase 1 (ADK Bootstrap).

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Baseline Scenarios | ✅ Fully Operational | 18 GitHub Actions workflows, BQ ingestion, PQC, OPA |
| Runtime Agent Skeleton | ✅ Complete | FastAPI service, 4 modules, Pub/Sub integration, BQ writer |
| Test Coverage | ✅ 20/20 passing | Unit tests for all modules + endpoint integration |
| Infrastructure | ✅ Deployed | Terraform: Cloud Run, Pub/Sub, BQ, IAM (least-privilege) |
| AI/LLM Integration | ⬜ Not Started | Zero LLM imports, all modules return hardcoded stubs |
| Design-Time Agent | ⬜ Not Started | No directory, no code, no infrastructure |
| Evaluation Framework | ⬜ Not Started | No comparison scripts, no variant labeling |

---

## 2. Audit Methodology

### 2.1 Scope

Every file in the repository was examined across these dimensions:

1. **Code Inventory** — module-by-module analysis of all source files
2. **Architecture Verification** — pipeline flow, separation of concerns, data paths
3. **Dependency Analysis** — libraries, GCP services, external integrations
4. **Security Posture** — IAM roles, secrets management, PQC implementation, OPA policies
5. **Test Coverage** — unit tests, integration scripts, mocking strategy
6. **Infrastructure Audit** — Terraform resources, service accounts, networking
7. **AI Readiness** — gaps between current state and target AI architecture

### 2.2 Files Examined

| Category | Files | Count |
|----------|-------|-------|
| Runtime Agent | `main.py`, `models/schemas.py`, perception, planning, guard, execution, storage, telemetry | 8 |
| Runtime Tests | `conftest.py`, `test_endpoint.py`, `test_perception.py`, `test_playbook.py`, `test_guard.py`, `test_executor.py` | 6 |
| Baseline | `explainability/` (5 files), `security/pqc/` (3 files), `services/` (2 apps), `scripts/` (10 files) | 20 |
| Infrastructure | `main.tf`, `runtime.tf`, `variables.tf` | 3 |
| Security | `ss1.rego` | 1 |
| Functions | `ingest_runs/main.py` | 1 |
| CI/CD | `.github/workflows/*.yml` | 18 |
| Documentation | `docs/` (5 files), `README.md` | 6 |
| **Total** | | **63** |

---

## 3. Baseline Substrate Assessment

### 3.1 Scenario Implementation Status

| Scenario | Workflow | BQ Ingestion | Metrics | Status |
|----------|----------|--------------|---------|--------|
| S1 (CI/CD Pipeline) | `s1_ci.yml` | ✅ `runs` | TTD, CFR, DF | ✅ Production |
| S2 (Edge OTA) | `s2_edge.yml` | ✅ `runs` | TDL, DSR, TTD_edge | ✅ Production |
| S3 (Resilience) | `s3_rollback.yml`, `s3_edge_rollback.yml` | ✅ `runs` | MTTD, MTTR | ✅ Production |
| S4 (PQC Security) | `s4_pqc.yml` | ✅ `runs` | TTV, VSR, FDR | ✅ Production |
| S5 (Explainability) | `s5_explainability.yml` | ✅ `runs` | AL, ACR | ✅ Production |
| SS1 (Policy Audit) | `ss1_ci.yml` | ✅ `runs` | CFR, DF, FDR, ACR | ✅ Production |
| SS2 (Adaptive Threat) | `ss2_adaptive_threat_mitigation.yml` | ✅ `runs` | MTTD, AL, ACR | ✅ Production |

### 3.2 Data Pipeline

```
GitHub Actions (S1–SS2) → HTTPS POST → Cloud Function (scenario-runs-ingest)
                                                 │
                                                 ▼
                                    BigQuery: agent_metrics.runs
                                    BigQuery: agent_metrics.s1_pipeline_runs
```

- **Ingestion**: Cloud Function Gen2 (`functions/ingest_runs/main.py`) handles both
  stage metric events and CloudEvents ActionTraces
- **Schema**: `agent_metrics.runs` — immutable, all scenarios write here
- **Partitioning**: By `occurred_at` timestamp
- **S1 Specific**: Dedicated `s1_pipeline_runs` table for fine-grained pipeline metrics

### 3.3 Security Components

| Component | Location | Implementation | Status |
|-----------|----------|----------------|--------|
| PQC Signing | `baseline/security/pqc/sign.py` | liboqs, Dilithium2 (FIPS 204) | ✅ Functional |
| PQC Verification | `baseline/security/pqc/verify.py` | liboqs, Dilithium2 | ✅ Functional |
| PQC Backend | `baseline/security/pqc/backends.py` | `OQSBackend` class, pluggable | ✅ Functional |
| OPA Policies | `security/policies/ss1.rego` | Naming, region, IAM, ingress, immutability | ✅ Functional |

### 3.4 Explainability Kit

| Module | Purpose | Status |
|--------|---------|--------|
| `schema.py` | ActionTrace CloudEvents schema, ACR computation | ✅ |
| `emit.py` | Emit structured explainability events | ✅ |
| `report.py` | Render explainability reports (Markdown/PDF) | ✅ |
| `approval.py` | HITL approval latency measurement | ✅ |
| `cloudevents.py` | CloudEvents helper utilities | ✅ |

---

## 4. Runtime Agent Assessment

### 4.1 Architecture

```
POST /events/runtime (Pub/Sub push)
         │
         ▼
    Parse Pub/Sub Envelope
         │
         ▼
    Validate RuntimeEvent (Pydantic)
         │
    ┌────┴────────────────────────────┐
    ▼                                 ▼
Perception ──▶ Planning ──▶ Guard ──▶ Execution
    │              │           │          │
    │              │           │          ▼
    │              │           │     Cloud Logging
    │              │           │
    └──────────────┴───────────┴──▶ BigQuery (runtime_decisions)
```

### 4.2 Module Analysis

| Module | File | Phase 0 Behavior | AI Target (Phase 1+) |
|--------|------|-------------------|----------------------|
| **Perception** | `perception/handler.py` | Hardcoded `severity=0.5`, `risk_score=0.5` | Z-score anomaly detection against BQ baselines |
| **Planning** | `planning/playbook.py` | Always returns `NO_OP` | LLM-driven action selection via ADK + Gemini |
| **Guard** | `guard/policy_check.py` | Always returns `approved=True` | OPA policy evaluation + PQC integrity check |
| **Execution** | `execution/executor.py` | Logs only, `decision_executed=False` | Mode-gated real actions (shadow/advisory/enforce) |
| **Storage** | `storage/bigquery_writer.py` | Writes to `runtime_decisions` | Unchanged (already production) |
| **Telemetry** | `telemetry/agentops_client.py` | Optional AgentOps tracing | Extended with LLM call logging |

### 4.3 Schema Inventory (Pydantic v2)

All schemas defined in `runtime-agent/models/schemas.py`:

| Schema | Fields | Validated At |
|--------|--------|--------------|
| `RuntimeEvent` | event_id, event_type, occurred_at, source, context | Endpoint input |
| `EventContext` | run_id, scenario_id, stage, status, severity, commit_sha | Nested in event |
| `PubSubPushEnvelope` | message (data, messageId), subscription | HTTP body |
| `AnomalyOutput` | scenario, anomaly_type, severity, risk_score, source_event_id | Perception output |
| `DecisionType` | NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE | Enum (bounded) |
| `PlanningDecision` | decision, rationale, policy_refs | Planning output |
| `GuardVerdict` | approved, reason | Guard output |
| `ExecutionResult` | decision_executed, log_message | Execution output |
| `DecisionRow` | 12 fields mirroring BQ schema | BQ write |

### 4.4 Test Coverage

| Test File | Tests | Scope |
|-----------|-------|-------|
| `test_endpoint.py` | 6 | HTTP endpoint, Pub/Sub parsing, error handling |
| `test_perception.py` | 4 | AnomalyOutput construction, field defaults |
| `test_playbook.py` | 4 | DecisionType enum, NO_OP default |
| `test_guard.py` | 3 | GuardVerdict construction, approved=True stub |
| `test_executor.py` | 3 | ExecutionResult, decision_executed=False |
| **Total** | **20** | All passing ✅ |

### 4.5 Dependencies

```
# Current (Phase 0)
fastapi>=0.111,<1.0
uvicorn[standard]>=0.30,<1.0
pydantic>=2.7,<3.0
google-cloud-bigquery>=3.25,<4.0
agentops>=0.3,<1.0
pytest>=8.0,<9.0
httpx>=0.27,<1.0

# Required for Phase 1+ (not yet added)
google-adk>=1.0,<2.0
google-cloud-aiplatform>=1.60,<2.0
```

---

## 5. Infrastructure Assessment

### 5.1 Terraform Resources

| Resource | File | Purpose |
|----------|------|---------|
| `google_service_account.runtime_agent` | `runtime.tf` | runtime-agent-sa |
| IAM bindings (5) | `runtime.tf` | logWriter, metricWriter, bqEditor, secretAccessor, arReader |
| `google_pubsub_topic.runtime_events` | `runtime.tf` | runtime-events-v1 |
| `google_pubsub_topic.runtime_events_dlq` | `runtime.tf` | DLQ for failed deliveries |
| `google_pubsub_subscription.runtime_agent_push` | `runtime.tf` | OIDC-authenticated push to Cloud Run |
| `google_bigquery_table.runtime_decisions` | `runtime.tf` | 12-field schema, partitioned by processed_at |
| `google_cloud_run_v2_service.runtime_agent` | `runtime.tf` | Cloud Run v2 service |

### 5.2 IAM Least-Privilege Verification

| Principal | Roles | Scope | Assessment |
|-----------|-------|-------|------------|
| `runtime-agent-sa` | logWriter | Project | ✅ Necessary |
| `runtime-agent-sa` | metricWriter | Project | ✅ Necessary |
| `runtime-agent-sa` | bqEditor | `agent_metrics` dataset only | ✅ Scoped correctly |
| `runtime-agent-sa` | secretAccessor | Project | ⚠️ Could be scoped to specific secret |
| `runtime-agent-sa` | arReader | Project | ✅ Necessary for image pull |
| `runtime-agent-sa` | run.invoker | Self (Cloud Run service) | ✅ Self-invoke for Pub/Sub push |
| `gha-app` | pubsub.publisher | `runtime-events-v1` topic | ✅ Scoped correctly |

### 5.3 Separation Verification

| Constraint | Status | Evidence |
|------------|--------|----------|
| `runtime.tf` does NOT modify `main.tf` resources | ✅ | Only references via `google_bigquery_dataset.metrics` etc. |
| Baseline workflows unchanged | ✅ | 18 workflow files untouched |
| BQ `runs` schema untouched | ✅ | Only `runtime_decisions` table added |
| No cross-contamination | ✅ | Runtime agent has own SA, own Pub/Sub, own BQ table |

---

## 6. AI Readiness Gap Analysis

### 6.1 What Exists (Strengths)

| Asset | Value for AI Integration |
|-------|--------------------------|
| Clean pipeline architecture | Direct mapping to ADK SequentialAgent |
| Pydantic v2 schemas | Ready for LLM structured output validation |
| Bounded action enum | Constrains LLM to safe action space |
| BQ runtime_decisions table | Episodic memory source (recent decisions) |
| BQ agent_metrics.runs | Historical baselines for anomaly detection |
| OPA policies | Guard callback enforcement |
| PQC verification | Integrity checking in guard pipeline |
| ActionTrace/CloudEvents kit | Explainability for agent decisions |
| AgentOps integration | LLM call tracing infrastructure |
| Shadow mode architecture | Safe rollout path for AI capabilities |

### 6.2 What's Missing (Gaps)

| Gap | Impact | Resolution |
|-----|--------|------------|
| **No LLM integration** | Core thesis contribution absent | Phase 1 Step 3: ADK + Gemini in Planning |
| **No real anomaly detection** | Perception returns hardcoded 0.5 | Phase 1 Step 2: Z-score + BQ baselines |
| **No OPA runtime check** | Guard always approves | Phase 1 Step 4: Real OPA evaluation |
| **No execution actions** | Agent never acts | Phase 1 Step 4: Mode-gated execution |
| **No episodic memory** | Agent has no context of prior decisions | Phase 1 Step 3: BQ query for recent decisions |
| **No design-time agent** | Structural synthesis not implemented | Phase 2 Step 6: Separate ADK agent |
| **No evaluation framework** | Cannot compare baseline vs. agent performance | Phase 3 Step 7: 2-Axis framework |
| **No ADK dependency** | `google-adk` not in requirements.txt | Phase 1 Step 1: Add to dependencies |

### 6.3 Import Analysis

A grep scan of the entire codebase confirms **zero LLM/AI imports**:

```
❌ No google.adk imports
❌ No google.cloud.aiplatform imports
❌ No vertexai imports
❌ No openai / anthropic / langchain imports
❌ No LLM-related code anywhere
```

This confirms a clean separation — AI integration will be purely additive.

---

## 7. Risk Assessment

### 7.1 Technical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| ADK SDK stability (pre-1.0 at time of selection) | Medium | Pin versions, InMemoryRunner tests, fallback to NO_OP |
| LLM latency in critical path | Medium | Async processing, timeout enforcement, latency logging |
| Gemini structured output reliability | Medium | Pydantic validation on every response, fallback to NO_OP |
| BQ query cost for perception baselines | Low | Query caching, pre-aggregated views |
| OPA sidecar vs REST API latency | Low | Evaluate both options in Step 4 |

### 7.2 Architectural Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Baseline contamination during AI integration | High | `.instructions.md` guardrails, CI checks, code review |
| Mode escalation (shadow → enforce) without validation | High | Explicit mode flag, no auto-escalation |
| Design-Time agent producing invalid proposals | Medium | OPA simulation, YAML lint, dry-run validation |
| Evaluation bias (same data for training and testing) | Medium | Time-based splits, separate evaluation dataset |

---

## 8. Recommendations

### Immediate (Pre-Phase 1)
1. Add `google-adk>=1.0,<2.0` and `google-cloud-aiplatform>=1.60,<2.0` to requirements.txt
2. Create `runtime-agent/agent/` directory structure (ADK skeleton)
3. Scope `secretmanager.secretAccessor` to specific secret resources
4. Document this audit report in `docs/` (this file)

### Phase 1 Priorities
1. **Step 1**: ADK Bootstrap — SequentialAgent wrapping existing FastAPI pipeline
2. **Step 2**: Perception — real z-score anomaly detection against BQ baselines
3. **Step 3**: Planning — LLM integration (Gemini via ADK), structured output, few-shot prompts
4. **Step 4**: Guard + Execution — real OPA checks, mode-gated actions

### Phase 2 Priorities
1. **Step 5**: Telemetry — LLM logger, ActionTrace integration, session export
2. **Step 6**: Design-Time Agent — separate ADK agent for structural synthesis

### Phase 3 Priorities
1. **Step 7**: 2-Axis Evaluation — baseline vs runtime vs design vs full comparison

---

## Appendix A: File Inventory

```
runtime-agent/
├── main.py                          # FastAPI app (190 lines)
├── Dockerfile                       # Python 3.12-slim, uvicorn
├── requirements.txt                 # 7 dependencies
├── models/schemas.py                # 9 Pydantic schemas (160 lines)
├── perception/handler.py            # Phase 0 stub
├── planning/playbook.py             # Phase 0 stub
├── guard/policy_check.py            # Phase 0 stub
├── execution/executor.py            # Phase 0 stub
├── storage/bigquery_writer.py       # Production BQ writer
├── telemetry/agentops_client.py     # Optional AgentOps
└── tests/ (6 files, 20 tests)

baseline/
├── explainability/ (5 modules)
├── security/pqc/ (3 modules)
├── services/ (2 apps: app, edge_cv_app)
└── scripts/ (10 utility scripts)

infra/
├── main.tf                          # Baseline infra (~200 lines, IMMUTABLE)
├── runtime.tf                       # Phase 0 runtime infra (~280 lines)
└── variables.tf

.github/workflows/ (18 files)
security/policies/ss1.rego
functions/ingest_runs/main.py
```

## Appendix B: BigQuery Schema Reference

### agent_metrics.runtime_decisions

| Field | Type | Description |
|-------|------|-------------|
| event_id | STRING | Source event UUID |
| event_type | STRING | Event classification |
| occurred_at | TIMESTAMP | Event timestamp |
| source | STRING | Publisher identity |
| context | JSON | Event context payload |
| decision | STRING | Agent decision (bounded) |
| rationale | STRING | Human-readable rationale |
| mode | STRING | shadow / advisory / enforce |
| decision_executed | BOOLEAN | Whether action was taken |
| policy_refs | STRING (REPEATED) | ISO/NIST control references |
| guard_approved | BOOLEAN | Guard verdict |
| processed_at | TIMESTAMP | Processing timestamp (partition key) |

---

## Appendix C: Post-Implementation Status (2026-03-19)

This addendum records the current implementation status. All gaps identified in
Section 6.2 have been resolved.

| Gap (Section 6.2) | Resolution | Evidence |
|----|----|----|
| No LLM integration | ADK LlmAgent + Gemini 2.0 Flash | `runtime-agent/agent/cogniops_agent.py` |
| No real anomaly detection | Z-score + BQ baselines | `runtime-agent/agent/tools/perception_tool.py` |
| No OPA runtime check | OPA REST (fail-closed) + PQC guard | `runtime-agent/agent/callbacks/guard_callback.py` |
| No execution actions | Mode-gated GitHub API actions | `runtime-agent/agent/tools/execution_tools.py` |
| No episodic memory | BQ query for recent decisions | ADK Session.state + `memory_tool.py` |
| No design-time agent | ADK LlmAgent, propose-only | `design-agent/` (97 tests) |
| No evaluation framework | 2-Axis statistical comparison | `evaluation/` (59 tests) |
| No ADK dependency | `google-adk` in requirements.txt | `runtime-agent/requirements.txt` |

### Test Coverage Summary

| Component | Tests |
|-----------|-------|
| Runtime Agent (Steps 1–5b) | 231 |
| Security Agent (Step 6b) | Included in runtime |
| Design-Time Agent (Step 6) | 97 |
| 2-Axis Evaluation (Step 7) | 59 |

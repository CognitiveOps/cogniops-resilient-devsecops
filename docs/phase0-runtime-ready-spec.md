# Phase 0 – Runtime-Ready Specification  
CogniOps MSc Thesis – Agentic DevSecOps System

---

## 1. Purpose

This document defines the Phase 0 Runtime-Ready Subset of the CogniOps system.

Phase 0 introduces the minimal additive infrastructure required to support a future Runtime Agent (Phase 1), while preserving the deterministic baseline system (S1–S5, SS1–SS2).

No baseline components may be modified in Phase 0.

---

## 2. Baseline Integrity

The following components are considered stable and immutable:

- Baseline DevSecOps scenarios S1–S5
- Composite scenarios SS1–SS2
- Unified BigQuery ingestion into `agent_metrics.runs`
- OTA deployment flow
- OPA policy validation
- PQC validation stage
- Baseline explainability kit

Phase 0 must not alter:

- GitHub Actions workflows
- BigQuery ingestion schema
- Existing metrics contracts
- Baseline execution semantics

---

## 3. Scope of Phase 0

Phase 0 includes:

- Pub/Sub runtime event channel
- Cloud Run runtime-agent service (skeleton only)
- Bounded playbook interface (stub execution only)
- AgentOps telemetry integration (optional, LLM trace only)  
  AgentOps is a third-party observability platform for LLM-based agents.  
  It traces agent reasoning calls, not baseline metrics.  
  API key stored in Secret Manager; referenced by runtime-agent-sa.  
  If AgentOps is not configured, the runtime-agent operates without tracing.
- Dedicated runtime decisions logging table

### Runtime Agent Internal Structure (Phase 0 → Phase 1)

The runtime-agent skeleton prepares the module boundaries for
the four internal agents defined in the Runtime Orchestration System:

| Module              | Phase 0 (skeleton)           | Phase 1 (active)                      |
|---------------------|------------------------------|---------------------------------------|
| Perception Agent    | Receives event, logs it      | Anomaly detection (z-score, threshold)|
| Risk/Planning Agent | Returns hardcoded decision   | LLM-scored bounded playbook selection |
| Policy Guard        | Always passes                | OPA re-check + PQC verification       |
| Execution Agent     | Logs decision, does nothing  | Workflow dispatch, HITL, rollback     |

In Phase 0, the agent pipeline is:

    Event → [Perception: log] → [Risk: hardcoded] → [Guard: pass] → [Exec: log only]

This ensures the Cloud Run service has the correct modular structure
before LLM reasoning is introduced in Phase 1.

Phase 0 excludes:

- Design-time agent (Architectural Synthesis System)
- PR synthesis
- Structural refactoring
- Advanced anomaly detection
- Execution of destructive mitigation actions
- Episodic memory writes

---

## 4. Runtime Event Lane Architecture

### Phase 0: Event-Driven Ingest

External publishers send structured events to the agent:

    Publisher → Pub/Sub (runtime-events-v1) → Cloud Run (runtime-agent)
             → agent_metrics.runtime_decisions

The agent receives events, makes a stub decision, and logs it.

### Phase 1: Metric-Driven Reaction (future)

The agent will also react to anomalies detected in baseline metrics:

    agent_metrics.runs (anomaly) → Pub/Sub → runtime-agent → mitigation

This second trigger path is out of scope for Phase 0.
Phase 0 validates the event envelope, decision logging, and
Pub/Sub delivery infrastructure that both paths will share.

A Dead Letter Topic must handle failed deliveries.
Infrastructure is provisioned in `infra/runtime.tf` (additive).

---

## 5. Bounded Action Surface

Allowed decisions (stub only):

- NO_OP
- BLOCK
- ROLLBACK
- QUARANTINE
- ESCALATE

No operational actions are executed in Phase 0.

---

## 6. Telemetry & Explainability

A new BigQuery table must be created:

`agent_metrics.runtime_decisions`

### Schema

| Field              | Type      | Mode     | Description                                    |
|--------------------|-----------|----------|------------------------------------------------|
| event_id           | STRING    | REQUIRED | UUID from runtime event envelope               |
| event_type         | STRING    | REQUIRED | pipeline_failure, policy_violation, etc.       |
| occurred_at        | TIMESTAMP | REQUIRED | When the event occurred (from envelope)        |
| source             | STRING    | REQUIRED | Publisher identity                             |
| context            | JSON      | NULLABLE | Full context object from event envelope        |
| decision           | STRING    | REQUIRED | NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE  |
| decision_executed  | BOOLEAN   | REQUIRED | Always false in Phase 0 (shadow mode)          |
| rationale          | STRING    | NULLABLE | Human-readable explanation of the decision     |
| policy_refs        | JSON      | NULLABLE | NIST/ISO/IMO control references                |
| mode               | STRING    | REQUIRED | shadow (Phase 0), advisory, enforce (future)   |
| agentops_trace_id  | STRING    | NULLABLE | AgentOps trace ID (if enabled)                 |
| processed_at       | TIMESTAMP | REQUIRED | When the runtime-agent processed the event     |

Each processed event must generate:

- Structured decision record (one row per event)
- AgentOps trace ID (if enabled)
- Deterministic audit row

No secrets, PQC artifacts, or full policy files may be sent to AgentOps.

---

## 7. Infrastructure Requirements

Resources required:

- Pub/Sub topic
- Dead-letter topic
- Push subscription with OIDC
- Cloud Run service
- Service account with minimal IAM
- BigQuery explainability table

All infrastructure must be additive.

---

## 8. Definition of Done

Phase 0 is complete when:

- A test runtime event can be published.
- The runtime-agent receives it.
- An AgentOps trace is generated (if enabled).
- A row is written to the explainability table.
- Baseline behavior remains unchanged.

---

## 9. Change Control Rules

Any modification to:

- Baseline ingestion
- Existing workflows
- Core metrics schema

Is out of scope and requires separate architectural review.
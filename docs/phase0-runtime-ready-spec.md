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
- AgentOps telemetry (LLM trace only)
- Dedicated runtime explainability logging table

Phase 0 excludes:

- Design-time agent
- PR synthesis
- Structural refactoring
- Advanced anomaly detection
- Execution of destructive mitigation actions

---

## 4. Runtime Event Lane Architecture

Event flow:

External Publisher / Test Publisher  
→ Pub/Sub Topic `runtime-events-v1`  
→ Push Subscription (OIDC authenticated)  
→ Cloud Run Service `runtime-agent`  
→ BigQuery `agent_metrics.runtime_explainability_logs`  
→ 2xx acknowledgement  

A Dead Letter Topic must be configured.

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

`agent_metrics.runtime_explainability_logs`

Each processed event must generate:

- Structured decision record
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
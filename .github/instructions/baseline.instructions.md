---
description: "Use when viewing or discussing baseline code: scenarios S1-SS2, explainability kit, PQC security, edge services, or metrics scripts"
applyTo: "baseline/**"
---
# Baseline — IMMUTABLE Deterministic Substrate

## Critical Rule
The baseline is the **deterministic execution substrate** for the thesis.
It must NEVER contain AI/LLM logic, stochastic behavior, or agent code.

## What Lives Here
- `services/app/` — Baseline web app (Cloud Run, health check)
- `services/edge_cv_app/` — Edge CV app (MODE=real / MODE=twin for fault injection)
- `explainability/` — ActionTrace schema, ACR computation, approval latency, CloudEvents, reports
- `security/pqc/` — PQC signing/verification (liboqs, Dilithium2)
- `scripts/` — Metric writers, backfill scripts, calibration tools
- `metrics/` — Generated artifacts (CSV, manifests)

## What You May Do
- Fix bugs in existing code
- Add new baseline scenarios (following existing patterns)
- Improve test coverage for existing modules
- Update documentation

## What You Must NOT Do
- Add AI/LLM/agent imports or logic
- Modify the metrics emission contract (BigQuery schema)
- Change the CloudEvents ActionTrace schema (specversion 1.0)
- Alter fault injection behavior in edge_cv_app
- Modify explainability validation (ACR computation)

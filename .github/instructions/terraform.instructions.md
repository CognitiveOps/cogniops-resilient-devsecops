---
description: "Use when modifying Terraform infrastructure: main.tf, runtime.tf, variables.tf, or adding new GCP resources"
applyTo: "infra/**"
---
# Terraform — Infrastructure as Code Guidelines

## Architecture
- `main.tf` — Baseline infrastructure (IMMUTABLE: AR, BQ dataset, SAs, WIF, Cloud Run, Cloud Function)
- `runtime.tf` — Phase 0+ runtime agent infra (Pub/Sub, Cloud Run, BQ runtime_decisions)
- `variables.tf` — All variable definitions

## Key Rules
- **NEVER modify main.tf** — baseline infrastructure is frozen
- All new resources go in **new .tf files** or **runtime.tf** (additive only)
- Use `depends_on` to reference main.tf resources (read-only)
- IAM: always least-privilege, always scoped (dataset-level, not project-level where possible)
- Service accounts: one per service, never share SAs across services

## Existing Resources (reference only, do not recreate)
- `google_bigquery_dataset.metrics` → dataset_id = "agent_metrics"
- `google_service_account.gha_infra` → Terraform deployments
- `google_service_account.gha_app` → CI/CD pipelines
- `google_artifact_registry_repository.docker` → "apps" registry
- `google_project_service.services` → baseline API enables
- `data.google_project.current` → project metadata

## Phase 0 Resources (in runtime.tf)
- `google_service_account.runtime_agent` → runtime-agent-sa
- `google_pubsub_topic.runtime_events` → runtime-events-v1
- `google_pubsub_topic.runtime_events_dlq` → DLQ
- `google_pubsub_subscription.runtime_agent_push` → push to Cloud Run
- `google_bigquery_table.runtime_decisions` → decision audit log
- `google_cloud_run_v2_service.runtime_agent` → agent service

## Adding New Phases
For Phase 2 (design-time agent), create `infra/design.tf` with:
- New service account (design-agent-sa)
- New Cloud Run service or batch job
- BQ read access to agent_metrics (not write to runs)
- GCS access for proposal storage

# Phase 0 — Implementation Notes

> Auto-generated from Phase 0 execution. Supplements `phase0-runtime-ready-spec.md`.

## 1. Commit History

| # | Scope | SHA | Key files |
|---|-------|-----|-----------|
| 0 | Docs baseline | `0b5c6d9` | docs/ (spec, event contract, IAM, prompts) |
| 1 | Infrastructure | `3f7a84f` | infra/runtime.tf |
| 2 | Agent skeleton | `dfe43cd` | runtime-agent/ (main, models, 4 modules) |
| 3 | BQ writer + AgentOps | `5563274` | storage/bigquery_writer.py, telemetry/agentops_client.py |
| 4 | Unit tests | `0dfcca7` | runtime-agent/tests/ (20 tests, all green) |
| 5 | Integration scripts | `40b9176` | scripts/test_publish_runtime_event.sh, scripts/verify_runtime_decision.sh |
| 6 | Documentation | — | docs/phase0-implementation-notes.md (this file) |

## 2. Architecture Overview

```
gcloud / GHA workflow
        │
        ▼
 Pub/Sub: runtime-events-v1  ──(push OIDC)──▶  Cloud Run: runtime-agent
                                                     │
                                         ┌───────────┼────────────┐
                                         ▼           ▼            ▼
                                    Perception   Planning     Guard
                                         │           │            │
                                         └─────┬─────┘            │
                                               ▼                  │
                                           Execution ◄────────────┘
                                               │
                                    ┌──────────┼────────────┐
                                    ▼                       ▼
                             BigQuery                  Cloud Logging
                       (runtime_decisions)          (structured JSON)
```

### Event Flow

1. An event is published to `runtime-events-v1` (e.g., by a GHA workflow or the manual test script).
2. The Pub/Sub push subscription delivers the event as an HTTP POST to the Cloud Run service endpoint `POST /events/runtime`.
3. The service base64-decodes and validates the envelope against `RuntimeEvent` (Pydantic).
4. Pipeline: **Perception → Planning → Guard → Execution**.
5. A decision row is written to `agent_metrics.runtime_decisions`.
6. A `200 OK` is returned to acknowledge the Pub/Sub message.

Invalid payloads receive `400` (non-retryable) so they are not redelivered.

## 3. Terraform Resources (infra/runtime.tf)

| Resource | Name | Purpose |
|----------|------|---------|
| `google_service_account` | `runtime-agent-sa` | Runtime Agent identity |
| `google_project_iam_member` × 2 | `logging.logWriter`, `monitoring.metricWriter` | Observability |
| `google_bigquery_dataset_iam_member` | `bigquery.dataEditor` on `agent_metrics` | Write decisions |
| `google_pubsub_topic` | `runtime-events-v1` | Event ingress |
| `google_pubsub_topic` | `runtime-events-v1-dlq` | Dead-letter queue |
| `google_pubsub_subscription` | `runtime-agent-push` | Push to Cloud Run (OIDC), max 5 attempts |
| `google_bigquery_table` | `runtime_decisions` | Decision audit log (12 fields) |
| `google_cloud_run_v2_service` | `runtime-agent` | Containerised agent |
| `google_cloud_run_service_iam_member` | `run.invoker` | Pub/Sub → Cloud Run auth |
| `google_pubsub_topic_iam_member` | `pubsub.publisher` | GHA → Pub/Sub |

All resources are **additive** — `infra/main.tf` is unchanged.

## 4. Runtime Agent Modules

| Module | Key function | Phase 0 behaviour |
|--------|-------------|-------------------|
| `perception/handler.py` | `perceive(event)` | severity=0.5, risk=0.5, scenario from context |
| `planning/playbook.py` | `select_playbook(anomaly)` | Always `NO_OP` |
| `guard/policy_check.py` | `check_policy(decision)` | Always `approved=True` |
| `execution/executor.py` | `execute(decision, verdict)` | `executed=False`, log only |
| `storage/bigquery_writer.py` | `write_decision(row)` | Best-effort insert, failures logged |
| `telemetry/agentops_client.py` | `trace_pipeline(event_id)` | Context manager; skipped if `AGENTOPS_ENABLED≠true` |

## 5. Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `GCP_PROJECT_ID` | yes | — | From Terraform `var.project_id` |
| `GCP_REGION` | yes | — | From Terraform `var.region` |
| `BIGQUERY_DATASET` | yes | `agent_metrics` | — |
| `BIGQUERY_TABLE` | yes | `runtime_decisions` | — |
| `AGENTOPS_ENABLED` | no | `false` | Set to `true` + provide API key to enable |
| `AGENTOPS_API_KEY` | no | — | Future: inject via Secret Manager |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

## 6. Phase 0 Invariants

Every processed event **must** produce a decision row that satisfies:

- `decision = "NO_OP"`
- `decision_executed = false`
- `mode = "shadow"`

The `verify_runtime_decision.sh` script enforces these assertions automatically.

## 7. Testing

### Unit Tests (offline, no GCP)

```bash
source 3_12_7_venv/bin/activate
cd runtime-agent && python -m pytest tests/ -v
```

20 tests covering perception, planning, guard, execution, and the full endpoint.

### Integration Tests (requires deployed infra)

```bash
# 1. Publish a test event
./scripts/test_publish_runtime_event.sh

# 2. Verify the decision row appears in BigQuery
./scripts/verify_runtime_decision.sh <event_id>
```

The publish script prints the generated `event_id`; pass it to the verify script.

## 8. Known Gaps / Phase 1 Prep

| Gap | Severity | Resolution plan |
|-----|----------|-----------------|
| `AGENTOPS_API_KEY` not wired to Secret Manager in TF | Low | Add `google_secret_manager_secret_version` ref in Phase 1 |
| Perception hardcoded (severity=0.5) | By design | Replace with anomaly-detection model in Phase 1 |
| Planning always returns NO_OP | By design | Introduce risk-based playbook selection in Phase 1 |
| Guard always approves | By design | Integrate OPA/Rego evaluation in Phase 1 |
| Execution never acts | By design | Enable controlled actions in Phase 1+ |
| Cloud Run image is placeholder | Expected | First real image built after `docker build` + push to Artifact Registry |

## 9. Deployment Sequence (first time)

```bash
# 1. Apply infrastructure
cd infra && terraform init && terraform apply

# 2. Build & push the agent image
cd ../runtime-agent
docker build -t REGION-docker.pkg.dev/PROJECT/docker/runtime-agent:v0.1.0 .
docker push REGION-docker.pkg.dev/PROJECT/docker/runtime-agent:v0.1.0

# 3. Update Cloud Run to the real image
# (update runtime.tf image reference and re-apply, or use gcloud run deploy)

# 4. Smoke test
../scripts/test_publish_runtime_event.sh
../scripts/verify_runtime_decision.sh <event_id>
```

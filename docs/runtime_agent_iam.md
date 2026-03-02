# Runtime Agent IAM Specification
Phase 0 – CogniOps

---

## Service Account: runtime-agent-sa (NEW)

Required roles:

- roles/logging.logWriter
- roles/monitoring.metricWriter
- roles/bigquery.dataEditor (scoped to `agent_metrics` dataset)
- roles/secretmanager.secretAccessor (if AgentOps key stored there)

---

## Pub/Sub Push Configuration

The push subscription uses OIDC with `runtime-agent-sa` as the
push-auth-service-account.

`runtime-agent-sa` must also have:

- roles/run.invoker on the `runtime-agent` Cloud Run service

This is a self-invoke pattern: the SA authenticates the Pub/Sub push
to the Cloud Run service it also runs as.

---

## Authorized Publishers (Phase 0)

| Principal | Use Case | Required Role |
|-----------|----------|---------------|
| `gha-app` (existing) | Publish pipeline_failure events from CI/CD | roles/pubsub.publisher on runtime-events-v1 |
| Manual test (gcloud auth) | Publish manual_test_event | roles/pubsub.publisher on runtime-events-v1 |

No new service accounts are needed for publishing.
Existing `gha-app` SA (already used by S1–S5 workflows) gets one
additional role binding.

---

## Relationship to Existing SAs

| Existing SA | Phase 0 Impact |
|-------------|----------------|
| gha-infra   | None — infra only |
| gha-app     | +roles/pubsub.publisher on runtime-events-v1 |
| run-exec    | None — baseline Cloud Run only |
| cf-ingest   | None — baseline ingest only |

---

## Principle of Least Privilege

- No editor/owner roles
- runtime-agent-sa has NO access to `agent_metrics.runs` (baseline table)
- runtime-agent-sa has NO access to `scenario-runs-ingest` Cloud Function
- gha-app gets pubsub.publisher ONLY, not subscriber or admin
- No access to production secrets unrelated to runtime-agent
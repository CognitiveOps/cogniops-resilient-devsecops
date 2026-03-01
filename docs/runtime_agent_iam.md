# Runtime Agent IAM Specification
Phase 0 – CogniOps

---

## Service Account: runtime-agent-sa

Required roles:

- roles/logging.logWriter
- roles/monitoring.metricWriter
- roles/bigquery.dataEditor (scoped to runtime_explainability_logs table)
- roles/secretmanager.secretAccessor (if AgentOps key stored there)

---

## Pub/Sub Push Configuration

Push subscription must:

- Use OIDC authentication
- Specify push-auth-service-account
- Set token audience to Cloud Run service URL
- Grant roles/run.invoker to push service account

---

## Event Publisher

Publisher principals require:

- roles/pubsub.publisher on runtime-events-v1

---

## Principle of Least Privilege

- No editor/owner roles
- No access to baseline ingestion
- No access to production secrets unrelated to runtime-agent
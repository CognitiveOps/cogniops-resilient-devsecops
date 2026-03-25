Implement Phase 0 Runtime-Ready infrastructure for the CogniOps system.

READ FIRST (in order):
1. README.md — baseline architecture (what exists and must NOT be modified)
2. docs/phase0-runtime-ready-spec.md — Phase 0 specification (what to build)
3. docs/runtime-event-contract.md — event envelope, scenario mapping, perception schema
4. docs/runtime_agent_iam.md — IAM roles and service account specification

CONSTRAINTS:
- Do not modify baseline workflows (S1–S5, SS1–SS2)
- Do not modify BigQuery schema for agent_metrics.runs
- Do not modify Cloud Function scenario-runs-ingest
- Do not modify infra/main.tf — add infra/runtime.tf instead
- Additive changes only — new files, new resources
- No destructive action execution (all decisions are stubs in Phase 0)
- Mode is always "shadow" in Phase 0

IMPLEMENTATION STEPS:

### Infrastructure (Terraform)
1. Create infra/runtime.tf with:
   - google_project_service for pubsub.googleapis.com (if not already enabled)
   - google_service_account.runtime_agent (runtime-agent-sa)
   - google_project_iam_member for roles/logging.logWriter (runtime-agent-sa)
   - google_project_iam_member for roles/monitoring.metricWriter (runtime-agent-sa)
   - google_bigquery_dataset_iam_member for roles/bigquery.dataEditor scoped to agent_metrics (runtime-agent-sa)
   - google_pubsub_topic.runtime_events (runtime-events-v1)
   - google_pubsub_topic.runtime_events_dlq (runtime-events-v1-dlq)
   - google_pubsub_subscription.runtime_agent_push (OIDC with runtime-agent-sa, max 5 delivery attempts, DLQ)
   - google_bigquery_table.runtime_decisions (schema per spec §6, partitioned by processed_at)
   - google_cloud_run_v2_service.runtime_agent (image from Artifact Registry, SA = runtime-agent-sa)
   - google_cloud_run_service_iam_member: runtime-agent-sa gets roles/run.invoker on runtime-agent (self-invoke for Pub/Sub push)
   - google_pubsub_topic_iam_member: gha-app gets roles/pubsub.publisher on runtime-events-v1

   Reference existing resources from main.tf (do not recreate):
   - google_bigquery_dataset.metrics (dataset_id = agent_metrics)
   - google_service_account.gha_app
   - google_artifact_registry_repository.docker

### Runtime Agent Service (Cloud Run)
2. Create runtime-agent/ directory with modular structure:
   ```
   runtime-agent/
   ├── Dockerfile
   ├── requirements.txt
   ├── main.py                  # FastAPI app, POST /events/runtime
   ├── perception/
   │   ├── __init__.py
   │   └── handler.py           # Receive event, validate, produce anomaly stub
   ├── planning/
   │   ├── __init__.py
   │   └── playbook.py          # Hardcoded decision selection (always NO_OP)
   ├── guard/
   │   ├── __init__.py
   │   └── policy_check.py      # Always passes in Phase 0
   ├── execution/
   │   ├── __init__.py
   │   └── executor.py          # Logs decision, does nothing
   ├── models/
   │   ├── __init__.py
   │   └── schemas.py           # Pydantic models for event envelope + perception output
   ├── telemetry/
   │   ├── __init__.py
   │   └── agentops_client.py   # AgentOps integration (optional, trace only)
   ├── storage/
   │   ├── __init__.py
   │   └── bigquery_writer.py   # Write to agent_metrics.runtime_decisions
   └── tests/
       ├── __init__.py
       ├── test_perception.py
       ├── test_playbook.py
       ├── test_guard.py
       ├── test_executor.py
       └── test_endpoint.py
   ```

3. Implement POST /events/runtime endpoint:
   - Unwrap Pub/Sub push message (base64 decode)
   - Validate payload against runtime-event-contract envelope schema
   - Reject invalid payloads with 400 + structured error (non-retryable)
   - Return 200 on success (acknowledges Pub/Sub message)

4. Implement Perception module:
   - Extract event fields
   - Produce hardcoded anomaly object:
     { scenario, anomaly_type, severity: 0.5, risk_score: 0.5, source_event_id }
   - scenario extracted from context.scenario_id or "unknown"
   - anomaly_type copied from event_type

5. Implement Risk/Planning module:
   - Receive anomaly object
   - Return hardcoded decision: NO_OP (Phase 0)
   - Generate rationale string: "Phase 0 shadow mode — no action taken"
   - policy_refs: empty list []

6. Implement Policy Guard:
   - Receive decision
   - Always return approved: true (Phase 0)
   - reason: "Phase 0 — guard bypassed"

7. Implement Execution module:
   - Receive approved decision
   - Set decision_executed = false (always in Phase 0)
   - Log to stdout (Cloud Logging captures this)

8. Implement BigQuery writer:
   - Write one row to agent_metrics.runtime_decisions per event
   - Schema fields: event_id, event_type, occurred_at, source, context,
     decision, decision_executed, rationale, policy_refs, mode,
     agentops_trace_id, processed_at
   - processed_at = server-side UTC timestamp

9. Integrate AgentOps (optional):
   - If AGENTOPS_API_KEY is set, trace the perception→planning→guard→exec pipeline
   - Redact: no secrets, no PQC keys, no full policy files
   - If not set, skip silently (no error)

### Environment Variables (Cloud Run service)
10. Configure the following environment variables:
    - GCP_PROJECT_ID (required)
    - GCP_REGION (required)
    - BIGQUERY_DATASET = "agent_metrics" (required)
    - BIGQUERY_TABLE = "runtime_decisions" (required)
    - AGENTOPS_API_KEY (optional — from Secret Manager)
    - AGENTOPS_ENABLED = "false" (optional — default false)
    - LOG_LEVEL = "INFO" (optional)

### Testing
11. Create runtime-agent/tests/ with unit tests:
    - test_perception.py: valid event → correct anomaly output
    - test_playbook.py: anomaly → NO_OP decision
    - test_guard.py: decision → approved=true
    - test_executor.py: decision → executed=false
    - test_endpoint.py: full Pub/Sub push message → 200 + correct pipeline

12. Create scripts/test_publish_runtime_event.sh:
    - Publishes a manual_test_event to runtime-events-v1 via gcloud
    - Uses the event envelope from runtime-event-contract.md

13. Create scripts/verify_runtime_decision.sh:
    - Queries agent_metrics.runtime_decisions for the test event
    - Verifies row exists with correct decision and mode=shadow

### Documentation
14. Update docs/ with any implementation notes
15. Do NOT modify README.md baseline sections

DEFINITION OF DONE:
- [ ] infra/runtime.tf applies cleanly (terraform plan shows only additions)
- [ ] terraform plan on main.tf shows zero changes
- [ ] runtime-agent-sa created with correct IAM roles
- [ ] Pub/Sub topic and DLQ created
- [ ] Push subscription configured with OIDC auth
- [ ] runtime_decisions BigQuery table created with correct schema
- [ ] runtime-agent Docker image builds successfully
- [ ] runtime-agent deploys to Cloud Run
- [ ] Test event published to Pub/Sub
- [ ] Pub/Sub pushes to runtime-agent endpoint
- [ ] Event validated against contract schema
- [ ] Invalid events return 400 (non-retryable)
- [ ] Perception → Planning → Guard → Execution pipeline runs
- [ ] Decision logged to agent_metrics.runtime_decisions
- [ ] Row contains: event_id, decision=NO_OP, mode=shadow, decision_executed=false
- [ ] AgentOps trace emitted (if configured)
- [ ] No AgentOps error when disabled
- [ ] No baseline workflows triggered or modified
- [ ] No rows added to agent_metrics.runs
- [ ] DLQ receives messages on repeated failure
- [ ] All new files are in additive paths (runtime-agent/, infra/runtime.tf, scripts/)
- [ ] Unit tests pass for all 4 modules

Work incrementally. Commit logically grouped changes:
1. Infrastructure (Terraform)
2. Agent skeleton (FastAPI + modules)
3. BigQuery writer + AgentOps
4. Unit tests
5. Integration test scripts
6. Documentation
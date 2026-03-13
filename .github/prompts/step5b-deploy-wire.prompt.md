---
description: "Deploy Runtime Agent to Cloud Run: IaC (Terraform), CI/CD (GitHub Actions), OPA CaC, ADK runner wiring, smoke test validation."
agent: "agent"
---

# Step 5b: Deploy & Wire Runtime Agent

Read first:
- [Project governance](../copilot-instructions.md)
- [Terraform instructions](../instructions/terraform.instructions.md)
- [Existing runtime.tf](../../infra/runtime.tf) (Cloud Run, Pub/Sub, BQ, IAM — already provisioned)
- [Existing infra_apply.yml](../../.github/workflows/infra_apply.yml) (reference workflow pattern)
- [Existing s1_ci.yml](../../.github/workflows/s1_ci.yml) (reference CI/CD pattern)
- [Runtime agent main.py](../../runtime-agent/main.py) (Phase 0 stubs — to be replaced with ADK runner)
- [ADK agent definition](../../runtime-agent/agent/cogniops_agent.py)
- [OPA policies](../../security/policies/ss1.rego)

## Task

Deploy the Runtime Agent end-to-end: extend Terraform IaC, create a CI/CD workflow,
bundle OPA policies, wire the ADK runner into `main.py`, and validate with a smoke test.

## Pre-Implementation Notes

### What already exists in `infra/runtime.tf`
- ✅ `google_cloud_run_v2_service.runtime_agent` — deployed with placeholder image
- ✅ `google_service_account.runtime_agent` — `runtime-agent-sa` with logging, BQ, secrets, AR reader
- ✅ `google_pubsub_topic.runtime_events` + DLQ + push subscription → `/events/runtime`
- ✅ `google_bigquery_table.runtime_decisions` — schema matches `DecisionRow`
- ✅ Env vars: `GCP_PROJECT_ID`, `GCP_REGION`, `BIGQUERY_DATASET`, `BIGQUERY_TABLE`, `AGENTOPS_ENABLED`, `LOG_LEVEL`

### What's missing
- ❌ Real container image (currently `us-docker.pkg.dev/cloudrun/container/hello`)
- ❌ Env vars: `COGNIOPS_MODE`, `COGNIOPS_MODEL`, `METRICS_INGEST_URL`, `COMMIT_SHA`, `OPA_URL`
- ❌ Secret Manager resources for `GITHUB_TOKEN`, `AGENTOPS_API_KEY`
- ❌ OPA service (Cloud Run sidecar or standalone)
- ❌ CI/CD workflow for runtime-agent (test → build → deploy)
- ❌ ADK runner wired into POST endpoint (still uses Phase 0 stubs)
- ❌ Smoke test script

## Implementation

### 1. IaC — Extend `infra/runtime.tf`

#### 1a. Add missing environment variables to Cloud Run container

```hcl
# Add to the existing containers {} block in google_cloud_run_v2_service.runtime_agent:
env {
  name  = "COGNIOPS_MODE"
  value = "shadow"
}
env {
  name  = "COGNIOPS_MODEL"
  value = "gemini-2.0-flash"
}
env {
  name  = "METRICS_INGEST_URL"
  value = ""  # Set after ingest function is deployed, or use google_cloudfunctions2_function.ingest_runs.uri
}
env {
  name  = "COMMIT_SHA"
  value = "managed-by-ci"  # Overridden at deploy time by CI/CD
}
env {
  name  = "OPA_URL"
  value = ""  # Set after OPA service is deployed
}
```

#### 1b. Add Secret Manager resources

```hcl
resource "google_secret_manager_secret" "runtime_github_token" {
  secret_id = "runtime-agent-github-token"
  replication { auto {} }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "runtime_agentops_key" {
  secret_id = "runtime-agent-agentops-key"
  replication { auto {} }
  depends_on = [google_project_service.secretmanager]
}
```

Mount as env vars in the Cloud Run container using `value_source`:
```hcl
env {
  name = "GITHUB_TOKEN"
  value_source {
    secret_key_ref {
      secret  = google_secret_manager_secret.runtime_github_token.secret_id
      version = "latest"
    }
  }
}
env {
  name = "AGENTOPS_API_KEY"
  value_source {
    secret_key_ref {
      secret  = google_secret_manager_secret.runtime_agentops_key.secret_id
      version = "latest"
    }
  }
}
```

#### 1c. Add image tag variable to `infra/variables.tf`

```hcl
variable "runtime_agent_image" {
  description = "Full container image URI for the runtime-agent (set by CI/CD)"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
```

Update the Cloud Run image reference:
```hcl
image = var.runtime_agent_image
```

#### 1d. OPA Cloud Run service (optional — can use sidecar instead)

Create a lightweight OPA service:
```hcl
resource "google_cloud_run_v2_service" "opa" {
  name     = "opa-server"
  location = var.region
  template {
    containers {
      image   = "openpolicyagent/opa:latest-static"
      args    = ["run", "--server", "--addr=:8181"]
      ports { container_port = 8181 }
      resources {
        limits = { cpu = "0.5", memory = "256Mi" }
      }
    }
    scaling { min_instance_count = 0; max_instance_count = 1 }
  }
}
```

Then set `OPA_URL` in the runtime-agent container to `google_cloud_run_v2_service.opa.uri`.

### 2. CI/CD — GitHub Actions Workflow

Create `.github/workflows/runtime_agent_deploy.yml`:

```yaml
name: Runtime Agent — Test, Build & Deploy

on:
  push:
    branches: [runtime_agent_dev, main]
    paths:
      - "runtime-agent/**"
      - ".github/workflows/runtime_agent_deploy.yml"
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

env:
  PROJECT_ID: ${{ vars.GCP_PROJECT_ID }}
  REGION: ${{ vars.GCP_REGION }}
  REPO_LOCATION: ${{ vars.GCP_REPO_LOCATION || 'europe' }}
  AR_REPO: "apps"
  SERVICE: "runtime-agent"

concurrency:
  group: runtime-agent-${{ github.ref }}
  cancel-in-progress: true
```

#### Jobs:

**Job 1: test**
```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.12" }
    - run: pip install -r runtime-agent/requirements.txt
    - run: cd runtime-agent && python -m pytest tests/ -v
```

**Job 2: build-push**
```yaml
build-push:
  needs: test
  runs-on: ubuntu-latest
  outputs:
    image: ${{ steps.meta.outputs.image }}
  steps:
    - uses: actions/checkout@v4
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
        service_account: ${{ vars.GCP_SA_APP_EMAIL }}
    - uses: google-github-actions/setup-gcloud@v2
    - run: gcloud auth configure-docker ${REPO_LOCATION}-docker.pkg.dev
    - id: meta
      run: |
        IMAGE="${REPO_LOCATION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}:${GITHUB_SHA}"
        echo "image=$IMAGE" >> "$GITHUB_OUTPUT"
    - run: |
        docker build -t ${{ steps.meta.outputs.image }} runtime-agent/
        docker push ${{ steps.meta.outputs.image }}
```

**Job 3: deploy**
```yaml
deploy:
  needs: build-push
  runs-on: ubuntu-latest
  steps:
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
        service_account: ${{ vars.GCP_SA_APP_EMAIL }}
    - uses: google-github-actions/deploy-cloudrun@v2
      with:
        service: runtime-agent
        region: ${{ env.REGION }}
        image: ${{ needs.build-push.outputs.image }}
        env_vars: |
          COMMIT_SHA=${{ github.sha }}
```

**Job 4: smoke-test**
```yaml
smoke-test:
  needs: deploy
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
        service_account: ${{ vars.GCP_SA_APP_EMAIL }}
    - run: |
        URL=$(gcloud run services describe runtime-agent --region=$REGION --format='value(status.url)')
        TOKEN=$(gcloud auth print-identity-token --audiences=$URL)
        # Health check
        curl -sf -H "Authorization: Bearer $TOKEN" "$URL/healthz"
        # Agent info
        curl -sf -H "Authorization: Bearer $TOKEN" "$URL/agent/info"
```

### 3. CaC — OPA Policy Bundling

OPA policies already exist at `security/policies/ss1.rego`.

Options (choose one during implementation):
- **Option A**: Mount policies via GCS bucket into OPA container
- **Option B**: Embed policies in a custom OPA Docker image
- **Option C**: Side-load policies via OPA REST API at startup

Whichever option: the guard callback's `OPA_URL` must resolve to the running OPA instance.

### 4. Wire ADK Runner into `main.py`

Replace Phase 0 stubs with the real ADK agent in the `POST /events/runtime` endpoint:

```python
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from agent.cogniops_agent import cogniops_agent

session_service = InMemorySessionService()
runner = InMemoryRunner(agent=cogniops_agent, session_service=session_service)
```

In the endpoint:
1. Create a session: `session = await session_service.create_session(app_name=...)`
2. Build user message with event context (JSON)
3. Run: `async for event in runner.run_async(session_id=..., user_id=..., new_message=...)`
4. Extract final tool call result → `decision`, `rationale`, `policy_refs`
5. Continue with guard verdict extraction, BQ write, ActionTrace emission

**Constraints:**
- Fallback: if ADK runner fails or times out, fall back to Phase 0 stubs (NO_OP)
- The ADK runner replaces steps 4–7 of the pipeline; steps 1–3 (Pub/Sub decode) remain
- `COGNIOPS_MODEL` env var controls which model the agent uses

### 5. Smoke Test Script

Create `scripts/smoke_test_runtime.sh`:
```bash
#!/usr/bin/env bash
# Publish a test event to Pub/Sub and verify the runtime agent processes it.
# Usage: ./scripts/smoke_test_runtime.sh

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
TOPIC="runtime-events-v1"

EVENT_ID="smoke-$(date +%s)"
EVENT=$(cat <<EOF
{
  "event_id": "$EVENT_ID",
  "event_type": "manual_test_event",
  "occurred_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source": "smoke-test",
  "context": {"status": "testing", "scenario_id": "S1", "run_id": "$EVENT_ID"}
}
EOF
)

echo "Publishing test event: $EVENT_ID"
gcloud pubsub topics publish "$TOPIC" \
  --project="$PROJECT_ID" \
  --message="$EVENT"

echo "Waiting 15s for pipeline..."
sleep 15

echo "Querying BQ for decision row..."
bq query --use_legacy_sql=false --project_id="$PROJECT_ID" \
  "SELECT event_id, decision, mode, decision_executed, trace_valid
   FROM agent_metrics.runtime_decisions
   WHERE event_id = '$EVENT_ID'
   LIMIT 1"
```

### 6. Tests

- Extend `tests/test_endpoint.py` with ADK runner integration test (mock LLM)
- `tests/test_adk_runner.py`: verify ADK runner wiring with `InMemoryRunner`
  - Test: event → ADK pipeline → decision extracted correctly
  - Test: ADK failure → fallback to Phase 0 stubs (NO_OP)
  - Test: session creation and cleanup

## Constraints

- **Terraform**: additive changes only to `runtime.tf` — NEVER modify `main.tf`
- **CI/CD**: follow existing workflow patterns (WIF auth, permissions, concurrency)
- **Secrets**: values set manually via `gcloud secrets versions add` — never in code
- **OPA**: fail-closed — if OPA is unreachable, guard blocks (already implemented)
- **ADK fallback**: if runner fails, emit NO_OP (zero operational risk)
- **Mode**: start in `shadow` — all decisions logged, none executed

## Post-Implementation (MANDATORY)

After completing the code changes:
1. Run `python -m pytest tests/ -v` — all tests must pass
2. Run `terraform plan` in `infra/` — verify no destructive changes
3. Replace the **Deployment & Wiring Checklist** section in `README.md` with a confirmation
   that Step 5b automates it via IaC + CI/CD
4. Update `README.md` § "📊 Implementation Progress" — mark Step 5b as ✅
5. Commit with message: `Step 5b: Deploy & Wire — IaC, CI/CD, OPA, ADK runner, smoke test`

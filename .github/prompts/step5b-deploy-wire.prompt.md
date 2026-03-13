---
description: "Deploy Runtime Agent to Cloud Run: IaC (Terraform), CI/CD (GitHub Actions), live OPA bundle polling, externalized config store, ADK runner wiring, smoke test."
agent: "agent"
---

# Step 5b: Deploy & Wire Runtime Agent

Read first:
- [Project governance](../copilot-instructions.md)
- [Terraform instructions](../instructions/terraform.instructions.md)
- [Existing runtime.tf](../../infra/runtime.tf) (Cloud Run, Pub/Sub, BQ, IAM — already provisioned)
- [Existing infra_apply.yml](../../.github/workflows/infra_apply.yml) (reference workflow pattern)
- [Existing s1_ci.yml](../../.github/workflows/s1_ci.yml) (reference CI/CD pattern)
- [SS1 OPA usage](../../.github/workflows/ss1_ci.yml) (baseline OPA eval pattern — CLI, not server)
- [Runtime agent main.py](../../runtime-agent/main.py) (Phase 0 stubs — to be replaced with ADK runner)
- [ADK agent definition](../../runtime-agent/agent/cogniops_agent.py)
- [OPA client](../../runtime-agent/agent/callbacks/opa_client.py) (REST API, path `/v1/data/cogniops/runtime/deny`)
- [OPA policies](../../security/policies/ss1.rego) (package `app.policy` — baseline only)
- [Control mapping](../../runtime-agent/telemetry/policy_refs.py) (currently hardcoded dict)

## Task

Deploy the Runtime Agent end-to-end with **live-updatable security configuration**:
- OPA policies via **bundle polling** (never baked into images)
- NIST/ISO/IMO control mappings via **externalized config store** (GCS + TTL cache)
- CI/CD workflow with policy bundle publishing
- ADK runner wiring into `main.py`
- End-to-end smoke test validation

## Design Principle: No Stale Security Config

Security-related configuration MUST be live-updatable without redeploying the agent:

| Component | Current (stale) | Target (live) |
|---|---|---|
| OPA policies | N/A (no server) | OPA bundle polling from GCS (30-120s) |
| NIST/ISO control refs | Hardcoded `policy_refs.py` | GCS YAML + TTL cache (5min) |
| Decision thresholds | Hardcoded `anomaly_detection.py` | GCS YAML + TTL cache (future) |
| PQC algorithm registry | Hardcoded `pqc/backends.py` | GCS YAML + TTL cache (future) |

**Update flow (zero redeploy):**
```
Security team pushes change → CI validates + uploads to GCS → OPA/Agent polls → fresh config
```

## Pre-Implementation Notes

### What already exists in `infra/runtime.tf`
- ✅ `google_cloud_run_v2_service.runtime_agent` — deployed with placeholder image
- ✅ `google_service_account.runtime_agent` — `runtime-agent-sa` with logging, BQ, secrets, AR reader
- ✅ `google_pubsub_topic.runtime_events` + DLQ + push subscription → `/events/runtime`
- ✅ `google_bigquery_table.runtime_decisions` — schema matches `DecisionRow`
- ✅ Env vars: `GCP_PROJECT_ID`, `GCP_REGION`, `BIGQUERY_DATASET`, `BIGQUERY_TABLE`, `AGENTOPS_ENABLED`, `LOG_LEVEL`

### What's missing
- ❌ Real container image (currently `us-docker.pkg.dev/cloudrun/container/hello`)
- ❌ Env vars: `COGNIOPS_MODE`, `COGNIOPS_MODEL`, `METRICS_INGEST_URL`, `COMMIT_SHA`, `OPA_URL`, `CONFIG_BUCKET`
- ❌ Secret Manager resources for `GITHUB_TOKEN`, `AGENTOPS_API_KEY`
- ❌ GCS bucket for config store (`cogniops-config`)
- ❌ OPA Cloud Run service with bundle polling config
- ❌ Runtime Rego policy (`security/policies/cogniops_runtime.rego` — package `cogniops.runtime`)
- ❌ Externalized control mapping store (`telemetry/config_store.py`)
- ❌ CI/CD workflow for runtime-agent (test → build → bundle → deploy → smoke)
- ❌ ADK runner wired into POST endpoint (still uses Phase 0 stubs)
- ❌ Smoke test script

## Implementation

### 1. IaC — Extend `infra/runtime.tf`

#### 1a. GCS Config Bucket (live-updatable config store)

```hcl
resource "google_storage_bucket" "cogniops_config" {
  name          = "${var.project_id}-cogniops-config"
  location      = var.bucket_location
  force_destroy = false

  versioning { enabled = true }

  uniform_bucket_level_access = true
}

# OPA bundle path: gs://<bucket>/bundles/runtime/bundle.tar.gz
# Config paths:
#   gs://<bucket>/control-mappings/v1.yaml
#   gs://<bucket>/thresholds/v1.yaml       (future)
#   gs://<bucket>/pqc-algorithms/v1.yaml   (future)

# runtime-agent-sa needs objectViewer to poll config
resource "google_storage_bucket_iam_member" "runtime_agent_config_reader" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime_agent.email}"
}

# gha-app SA needs objectCreator to upload bundles/config from CI
resource "google_storage_bucket_iam_member" "gha_app_config_writer" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.gha_app.email}"
}
```

#### 1b. Add missing environment variables to Cloud Run container

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
  value = ""  # Set after ingest function is deployed
}
env {
  name  = "COMMIT_SHA"
  value = "managed-by-ci"  # Overridden at deploy time by CI/CD
}
env {
  name  = "OPA_URL"
  value = ""  # Set to OPA Cloud Run service URI after deploy
}
env {
  name  = "CONFIG_BUCKET"
  value = google_storage_bucket.cogniops_config.name
}
```

#### 1c. Add Secret Manager resources

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

#### 1d. Add image tag variable to `infra/variables.tf`

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

#### 1e. OPA Cloud Run service with bundle polling

OPA MUST poll bundles from GCS — policies are NEVER baked into the image.
This ensures security policy updates propagate without redeploying the agent.

```hcl
resource "google_service_account" "opa" {
  account_id   = "opa-server-sa"
  display_name = "OPA Server (Cloud Run)"
}

# OPA SA needs objectViewer to poll bundles from GCS
resource "google_storage_bucket_iam_member" "opa_config_reader" {
  bucket = google_storage_bucket.cogniops_config.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.opa.email}"
}

resource "google_cloud_run_v2_service" "opa" {
  name     = "opa-server"
  location = var.region

  template {
    service_account = google_service_account.opa.email

    containers {
      image = "openpolicyagent/opa:latest-static"
      args  = [
        "run", "--server", "--addr=:8181",
        "--config-file=/config/opa-config.yaml",
      ]
      ports { container_port = 8181 }
      resources {
        limits = { cpu = "0.5", memory = "256Mi" }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }
}
```

OPA config file (`security/opa-config.yaml`) — must be mounted or baked minimally:
```yaml
services:
  gcs:
    url: https://storage.googleapis.com/BUCKET_NAME
    credentials:
      gcp_metadata: {}

bundles:
  runtime:
    service: gcs
    resource: bundles/runtime/bundle.tar.gz
    polling:
      min_delay_seconds: 30
      max_delay_seconds: 120

decision_logs:
  console: true
```

The OPA service polls `gs://<bucket>/bundles/runtime/bundle.tar.gz` every 30-120s.
Policy updates are live within 2 minutes — zero redeploy.

Then set in the runtime-agent container:
```hcl
env {
  name  = "OPA_URL"
  value = google_cloud_run_v2_service.opa.uri
}
```

### 2. CI/CD — GitHub Actions Workflow

Create `.github/workflows/runtime_agent_deploy.yml`:

```yaml
name: Runtime Agent — Test, Build, Bundle & Deploy

on:
  push:
    branches: [runtime_agent_dev, main]
    paths:
      - "runtime-agent/**"
      - "security/policies/**"
      - "config/**"
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
  CONFIG_BUCKET: "${{ vars.GCP_PROJECT_ID }}-cogniops-config"

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

**Job 2: bundle-policies** (OPA + config upload to GCS)
```yaml
bundle-policies:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
        service_account: ${{ vars.GCP_SA_APP_EMAIL }}
    - uses: google-github-actions/setup-gcloud@v2

    # Install OPA CLI
    - run: |
        curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64
        chmod +x opa && sudo mv opa /usr/local/bin/opa

    # Validate policies
    - run: opa check security/policies/

    # Build OPA bundle
    - run: |
        opa build -b security/policies/ -o bundle.tar.gz
        gsutil cp bundle.tar.gz gs://${CONFIG_BUCKET}/bundles/runtime/bundle.tar.gz

    # Upload control mappings
    - run: |
        gsutil cp config/control-mappings.yaml gs://${CONFIG_BUCKET}/control-mappings/v1.yaml
```

**Job 3: build-push**
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

**Job 4: deploy**
```yaml
deploy:
  needs: [build-push, bundle-policies]
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

**Job 5: smoke-test**
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

### 3. CaC — Live Policy & Config Management

#### 3a. Runtime OPA Policy

Create `security/policies/cogniops_runtime.rego`:
```rego
package cogniops.runtime

# Runtime agent decision guardrails.
# Input: { action, scenario, severity, risk_score, event_type, mode, args }

# Block high-severity actions in shadow mode
deny contains "enforce-only action in shadow mode" if {
    input.mode == "shadow"
    input.action != "NO_OP"
    # In shadow mode, only NO_OP is truly "executed"
}

# Require minimum severity for ROLLBACK
deny contains sprintf("ROLLBACK requires severity >= 0.7, got %v", [input.severity]) if {
    input.action == "ROLLBACK"
    input.severity < 0.7
}

# Require minimum severity for BLOCK
deny contains sprintf("BLOCK requires severity >= 0.6, got %v", [input.severity]) if {
    input.action == "BLOCK"
    input.severity < 0.6
}

# QUARANTINE only for S4/SS2 scenarios
deny contains sprintf("QUARANTINE only for S4/SS2, got %v", [input.scenario]) if {
    input.action == "QUARANTINE"
    not input.scenario in {"S4", "SS2"}
}
```

This policy is **bundled and uploaded to GCS** by the CI workflow — OPA polls it live.
The `opa_client.py` already queries `/v1/data/cogniops/runtime/deny` matching this package path.

#### 3b. Externalized Control Mapping

Create `config/control-mappings.yaml`:
```yaml
schema_version: "1.0"
updated_at: "2026-03-13T00:00:00Z"
description: "ISO/NIST/IMO control references per decision type"
mappings:
  BLOCK:
    - ref: "NIST SP 800-53 CM-3"
      title: "Configuration Change Control"
      revision: "Rev. 5"
    - ref: "ISO 27001:2022 A.12.1.2"
      title: "Change Management"
    - ref: "IMO MSC.428(98) §4.1"
      title: "Identify — risk assessment"
  ROLLBACK:
    - ref: "NIST SP 800-53 CP-10"
      title: "System Recovery and Reconstitution"
      revision: "Rev. 5"
    - ref: "ISO 27001:2022 A.17.1.2"
      title: "Implementing Information Security Continuity"
    - ref: "IMO MSC.428(98) §4.4"
      title: "Respond — contingency plans"
  QUARANTINE:
    - ref: "NIST SP 800-53 SI-3"
      title: "Malicious Code Protection"
      revision: "Rev. 5"
    - ref: "ISO 27001:2022 A.12.2.1"
      title: "Controls Against Malware"
    - ref: "IMO MSC.428(98) §4.3"
      title: "Detect — anomaly detection"
  ESCALATE:
    - ref: "NIST SP 800-53 IR-6"
      title: "Incident Reporting"
      revision: "Rev. 5"
    - ref: "ISO 27001:2022 A.16.1.2"
      title: "Reporting Information Security Events"
    - ref: "IMO MSC.428(98) §4.5"
      title: "Recover — lessons learned"
  NO_OP: []
```

#### 3c. Config Store Module

Create `runtime-agent/telemetry/config_store.py`:
```python
"""Live-loading config store with GCS fetch + TTL cache.

Replaces hardcoded policy_refs.py with externalized YAML
from GCS. Falls back to built-in defaults if GCS is unavailable.
"""

import logging
import os
import time
import yaml
from typing import Any

logger = logging.getLogger("runtime-agent.config")

CONFIG_BUCKET = os.getenv("CONFIG_BUCKET", "")
CONTROL_MAPPINGS_PATH = "control-mappings/v1.yaml"
REFRESH_INTERVAL_SEC = int(os.getenv("CONFIG_REFRESH_SEC", "300"))  # 5 min default

class ConfigStore:
    """TTL-cached config fetcher from GCS."""

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._last_fetch: float = 0.0

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._last_fetch) > REFRESH_INTERVAL_SEC

    def _fetch_from_gcs(self, path: str) -> dict | None:
        """Fetch YAML config from GCS. Returns None on failure."""
        if not CONFIG_BUCKET:
            return None
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(CONFIG_BUCKET)
            blob = bucket.blob(path)
            content = blob.download_as_text()
            return yaml.safe_load(content)
        except Exception as exc:
            logger.warning("GCS config fetch failed (%s): %s", path, exc)
            return None

    def get_control_mappings(self) -> dict[str, list[str]]:
        """Return decision→refs mapping, refreshing if stale.
        
        Falls back to built-in defaults (policy_refs.py) if GCS unavailable.
        """
        if self._is_stale():
            data = self._fetch_from_gcs(CONTROL_MAPPINGS_PATH)
            if data and "mappings" in data:
                # Flatten to simple ref strings for backward compat
                result = {}
                for decision, entries in data["mappings"].items():
                    result[decision] = [e["ref"] for e in entries if "ref" in e]
                self._cache = result
                self._last_fetch = time.monotonic()
                logger.info("Control mappings refreshed from GCS (version=%s)",
                           data.get("schema_version", "?"))

        if self._cache:
            return self._cache

        # Fallback to built-in hardcoded defaults
        from telemetry.policy_refs import get_policy_refs as _builtin
        from models.schemas import DecisionType
        return {dt.value: _builtin(dt) for dt in DecisionType}

# Singleton instance
config_store = ConfigStore()
```

Update `telemetry/policy_refs.py` to use the store:
```python
def get_policy_refs(decision: DecisionType) -> list[str]:
    """Return control references — live from GCS, fallback to built-in."""
    try:
        from telemetry.config_store import config_store
        mappings = config_store.get_control_mappings()
        refs = mappings.get(decision.value, [])
        if refs:
            return list(refs)
    except Exception:
        pass  # Fall through to built-in
    return list(_CONTROL_MAP.get(decision, []))
```

#### 3d. OPA Config File

Create `security/opa-config.yaml` (template — BUCKET_NAME replaced by CI):
```yaml
services:
  gcs:
    url: https://storage.googleapis.com/BUCKET_NAME
    credentials:
      gcp_metadata: {}

bundles:
  runtime:
    service: gcs
    resource: bundles/runtime/bundle.tar.gz
    polling:
      min_delay_seconds: 30
      max_delay_seconds: 120

decision_logs:
  console: true
```

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
- `tests/test_config_store.py`: verify config store behavior
  - Test: GCS unavailable → falls back to built-in `_CONTROL_MAP`
  - Test: GCS returns valid YAML → cache populated, refs returned
  - Test: TTL expiry → re-fetch triggered
  - Test: malformed YAML → graceful fallback
- `tests/test_runtime_rego.py`: verify `cogniops_runtime.rego` policy
  - Test: `opa eval` with valid/invalid inputs (using OPA CLI in test)
  - Test: shadow mode blocks non-NO_OP actions
  - Test: ROLLBACK requires severity >= 0.7
  - Test: QUARANTINE restricted to S4/SS2

## Constraints

- **Terraform**: additive changes only to `runtime.tf` — NEVER modify `main.tf`
- **CI/CD**: follow existing workflow patterns (WIF auth, permissions, concurrency)
- **Secrets**: values set manually via `gcloud secrets versions add` — never in code
- **OPA**: fail-closed — if OPA is unreachable, guard blocks (already implemented)
- **OPA bundles**: policies MUST be fetched live via bundle polling — NEVER baked into image
- **Config store**: GCS fetch with TTL cache — MUST fall back to built-in defaults on failure
- **ADK fallback**: if runner fails, emit NO_OP (zero operational risk)
- **Mode**: start in `shadow` — all decisions logged, none executed
- **Security config update flow**: push to repo → CI validates → GCS upload → OPA/agent polls (zero redeploy)

## Post-Implementation (MANDATORY)

After completing the code changes:
1. Run `python -m pytest tests/ -v` — all tests must pass
2. Run `opa check security/policies/` — all Rego files valid
3. Run `terraform plan` in `infra/` — verify no destructive changes
4. Update `README.md` § "Step 5b" section with implementation confirmation
5. Update `README.md` § "📊 Implementation Progress" — mark Step 5b as ✅
6. Commit with message: `Step 5b: Deploy & Wire — IaC, CI/CD, live OPA bundles, config store, ADK runner`

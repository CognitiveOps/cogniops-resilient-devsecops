# Local Development Setup

Run the CogniOps agent stack locally with Docker Compose — no GCP project required.
BigQuery and GCS writes are skipped gracefully when credentials are absent; the
agents run against a local OPA server and a real Gemini API key.

## Prerequisites

- Docker + Docker Compose
- A [Google AI Studio](https://aistudio.google.com/app/apikey) or Vertex AI API key

## Quick start

```bash
# 1. Copy the placeholder env file and add your Gemini API key
cp local.env .env
# Edit .env and set: GEMINI_API_KEY=your-key-here

# 2. Start the stack
docker compose up --build

# 3. Verify services are healthy
curl http://localhost:8080/health   # runtime-agent
curl http://localhost:8081/health   # design-agent
curl http://localhost:8082/health   # security-agent
curl http://localhost:8181/health   # OPA
```

## Test a runtime decision

```bash
curl -X POST http://localhost:8080/decide \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "local-test-001",
    "event_type": "manual_test_event",
    "occurred_at": "2026-07-30T10:00:00Z",
    "source": "local-test",
    "context": {
      "run_id": "run-local-001",
      "scenario_id": "S3",
      "stage": "deploy",
      "status": "fail",
      "severity": "high"
    }
  }'
```

Expected response:

```json
{
  "status": "accepted",
  "event_id": "local-test-001",
  "decision": "ESCALATE",
  "decision_executed": false,
  "mode": "shadow",
  ...
}
```

## What runs locally

| Service | Port | Notes |
|---|---|---|
| OPA | 8181 | Loads `security/policies/cogniops_runtime.rego` from a local volume via `docker/opa-config.dev.yaml` |
| runtime-agent | 8080 | Full ADK pipeline: perception → planning → guard → execution |
| design-agent | 8081 | Trigger `/run` manually; GCS/BQ writes skipped locally |
| security-agent | 8082 | Trigger `/run` manually; NIST feeds require outbound internet |

## Limitations

- **BigQuery**: decision rows are not persisted locally (no local emulator).
- **GCS**: proposals/configs are not persisted locally.
- **GitHub Issues**: skipped when `GITHUB_TOKEN` is empty.
- **Security agent**: NIST API calls require internet; mocked feeds are not included.

For full production deployment on GCP, see `infra/` and `.github/workflows/`.

# Runtime Agent — ADK Cognitive Pipeline

Cloud Run micro-service that receives runtime events via Pub/Sub,
runs a bounded-autonomy decision pipeline, and logs every decision to BigQuery.

The active path is the **ADK cognitive agent** (`agent/cogniops_agent.py`):
Gemini-based planning via ADK tool calling, with the LLM confined to the
Planning module. Deterministic guardrails enforce the boundary:

- **OPA + PQC guard** (`agent/callbacks/guard_callback.py`) — fail-closed,
  runs before every execution tool.
- **Mode-gated execution** (`agent/tools/execution_tools.py`) —
  `shadow` / `advisory` / `enforce`.
- **Explainability telemetry** — ISO/NIST control mapping + CloudEvent ActionTraces.

> **Default mode:** `shadow` — decisions are logged but not executed.

---

## Directory Layout

```
runtime-agent/
├── main.py                     # FastAPI app (/events/runtime, /decide, /health, /agent/info)
├── Dockerfile                  # python:3.12-slim + uvicorn
├── requirements.txt
│
├── agent/                      # ── ADK Cognitive Agent ──
│   ├── cogniops_agent.py       # Root LlmAgent "cogniops_planning"
│   ├── tools/
│   │   ├── perception_tool.py  # ADK FunctionTool — z-score + threshold anomaly detection
│   │   ├── anomaly_detection.py # Z-score & threshold scoring engine
│   │   ├── baseline_reader.py  # BQ 7-day rolling baseline queries
│   │   ├── execution_tools.py  # Mode-gated bounded actions
│   │   ├── github_client.py    # GitHub API: workflow_dispatch, issue creation
│   │   └── memory_tools.py     # Episodic memory: query recent decisions from BQ
│   ├── callbacks/
│   │   ├── guard_callback.py   # before_tool_callback (OPA + PQC guard)
│   │   └── opa_client.py       # OPA REST API client
│   └── prompts/
│       ├── system.txt          # System prompt with decision criteria matrix
│       ├── few_shot_s1.txt     # Pipeline failure: high CFR → ROLLBACK
│       ├── few_shot_s3.txt     # Resilience: high MTTD → ESCALATE / ROLLBACK
│       ├── few_shot_s5.txt     # Explainability: low ACR → ESCALATE
│       └── few_shot_ss2.txt    # Adaptive threat: integrity → QUARANTINE
│
├── perception/                 # Deterministic event scoring (shared with inline/detect.py)
│   ├── handler.py              # perceive(event) → AnomalyOutput
│   └── scoring.py              # score_raw_metrics() model
│
├── planning/                   # Fallback stub: hardcoded NO_OP if ADK path fails
│   └── playbook.py
│
├── guard/                      # Fallback stub: pass-through if ADK guard is bypassed
│   └── policy_check.py
│
├── execution/                  # Fallback stub: logs decision, no action
│   └── executor.py
│
├── models/
│   └── schemas.py              # Pydantic v2 models (event envelope, pipeline stages, BQ row)
│
├── storage/
│   └── bigquery_writer.py      # write_decision(row) → bool  (best-effort)
│
├── telemetry/
│   ├── agentops_client.py      # trace_pipeline(event_id) context manager
│   ├── llm_logger.py           # LLM call logging (prompt hash, latency, tokens)
│   ├── config_store.py         # GCS config fetch + TTL cache
│   ├── policy_refs.py          # ISO/NIST/IMO control mapping per DecisionType
│   └── trace_emitter.py        # ActionTrace CloudEvent builder + emitter
│
├── inline/                     # GitHub Actions inline sensors
│   ├── detect.py               # Polls service /status, scores with perception.scoring
│   └── risk.py                 # Classifies S5 recommendations for auto-approve
│
└── tests/                      # pytest unit tests
    ├── conftest.py
    ├── test_agent_pipeline.py  # ADK agent structure, tools, guard
    ├── test_planning_llm.py    # LLM planning, few-shots, fallback
    ├── test_guard_opa.py       # OPA guard, PQC check, mode gating
    ├── test_execution_modes.py # shadow/advisory/enforce mode gating
    ├── test_github_client.py   # GitHub API mock tests
    ├── test_explainability.py  # ActionTrace validation
    ├── test_policy_refs.py     # Control mapping tests
    ├── test_adk_runner.py      # ADK runner wiring, fallback
    ├── test_config_store.py    # GCS config store, TTL cache
    ├── test_runtime_rego.py    # OPA Rego policy evaluation
    ├── test_perception.py      # perception.handler tests
    ├── test_perception_real.py # z-score, threshold, combined scoring
    ├── test_playbook.py        # fallback stub
    ├── test_guard.py           # fallback stub
    ├── test_executor.py        # fallback stub
    ├── test_endpoint.py
    └── fixtures/
        └── mock_bq_baselines.json
```

---

## Pipeline

```
Pub/Sub push  →  POST /events/runtime
                       │
               ┌───────▼────────┐
               │  ADK Runner    │   InMemoryRunner + cogniops_agent
               │  (LlmAgent)    │   Gemini 2.0 Flash
               │                │
               │  perceive_anomaly → LLM planning → guard_callback → execution tool
               └───────┬────────┘
                       │  tool result = {action, rationale, executed}
                       │
               Fallback: ADK/LLM failure → NO_OP (zero risk)
                       │
              ┌────────┴─────────┐
              ▼                  ▼
         BigQuery           Cloud Logging
   (runtime_decisions)    (structured JSON)
              │
              ▼
       ActionTrace CE
   (explainability kit)
```

### Live-Updatable Security Config

```
Security team pushes → CI validates + uploads to GCS → OPA/Agent polls → fresh config
```

| Component | Mechanism | Update Latency |
|---|---|---|
| OPA policies | Bundle polling from GCS | 30-120s |
| Control mappings | GCS YAML + TTL cache | 5 min |

---

## Perception — Anomaly Detection

The perception layer uses **deterministic** anomaly detection — no LLM involved.
The same scoring model lives in `perception/scoring.py` and is reused by the
inline sensor (`inline/detect.py`) so that detection and assessment share one
cognitive model.

### Detection Methods

| Method | Source | Trigger |
|--------|--------|---------|
| Z-score | BQ 7-day rolling average | \|z\| > 1σ (severity 0.1–1.0) |
| Threshold | Per-scenario rules | Warning / Critical bounds |

### Scenario Thresholds

| Scenario | Metric | Warning | Critical | Direction |
|----------|--------|---------|----------|-----------|
| S1 | `ttd_sec` | 180s | 300s | above |
| S1 | `cfr` | 10% | 25% | above |
| S2 | `dsr` | 95% | 85% | below |
| S3 | `mttd_sec` | 60s | 120s | above |
| S3 | `mttr_sec` | 120s | 300s | above |
| S4 | `fdr` | 90% | 70% | below |

### Graceful Degradation

- BQ unavailable → threshold-only detection
- No thresholds for scenario → severity = 0.5 (neutral → NO_OP)
- Invalid metrics → silently ignored, safe default

---

## Guard — OPA + PQC

`agent/callbacks/guard_callback.py` is registered as `before_tool_callback` on
the ADK agent. It is invoked before every tool call the LLM requests:

- **Observation tools** (`perceive_anomaly`, `query_recent_decisions`) are always allowed.
- **Execution tools** (`no_action`, `block_deployment`, `rollback_deployment`,
  `quarantine_artifact`, `escalate_to_human`) are evaluated against:
  1. OPA policy `cogniops.runtime` — fail-closed.
  2. PQC integrity check — for S4/SS2 when artifact context is present.

If the guard denies a tool, ADK receives a synthetic tool result and the
original tool never runs.

---

## Telemetry & Explainability

Every pipeline decision generates a **CloudEvent ActionTrace** validated
against the baseline explainability kit (`baseline/explainability/schema.py`).

### ISO/NIST Control Mapping

| Decision | NIST SP 800-53 | ISO 27001:2022 | IMO MSC.428(98) |
|----------|---------------|----------------|-----------------|
| `BLOCK` | CM-3 | A.12.1.2 | §4.1 |
| `ROLLBACK` | CP-10 | A.17.1.2 | §4.4 |
| `QUARANTINE` | SI-3 | A.12.2.1 | §4.3 |
| `ESCALATE` | IR-6 | A.16.1.2 | §4.5 |
| `NO_OP` | — | — | — |

### ActionTrace CloudEvent

```json
{
  "specversion": "1.0",
  "type": "cogniops.runtime.decision",
  "source": "cogniops/runtime-agent",
  "data": {
    "schema_version": "1.0",
    "scenario_id": "S3",
    "action": "ROLLBACK",
    "rationale": "High severity anomaly ...",
    "risk": {"score": 0.85, "level": "high"},
    "policy_refs": ["NIST SP 800-53 CP-10", "ISO 27001:2022 A.17.1.2", "IMO MSC.428(98) §4.4"],
    "timestamps": {"t_recommend_epoch": 1719945600.0},
    "provenance": {"commit_sha": "abc123"}
  }
}
```

Every trace passes `validate_action_trace()` and is emitted to the metrics
ingest endpoint when `METRICS_INGEST_URL` is configured.

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/events/runtime` | Pub/Sub push receiver — decodes envelope, runs pipeline, writes to BQ |
| `POST` | `/decide` | Synchronous decision endpoint for agent-in-the-loop workflows |
| `GET`  | `/health` | Liveness / readiness probe (`{"status":"ok","mode":"shadow","version":"0.3.0"}`) |
| `GET`  | `/agent/info` | ADK agent metadata — tools, model, guard status |

### Response Codes

| Code | Meaning | Pub/Sub behaviour |
|------|---------|-------------------|
| `200` | Accepted — pipeline ran successfully | Message acknowledged |
| `400` | Invalid envelope / schema | **Non-retryable** — message is NOT redelivered |
| `500` | Unexpected server error | Retryable — Pub/Sub will redeliver (up to 5 times before DLQ) |

---

## Models (schemas.py)

| Model | Description |
|-------|-------------|
| `RuntimeEvent` | Event envelope per `runtime-event-contract.md` |
| `EventContext` | Nested context block (`run_id`, `scenario_id`, `stage`, `status`, …) |
| `PubSubPushEnvelope` | Wraps the base64-encoded message from Pub/Sub push |
| `AnomalyOutput` | Perception result (scenario, anomaly_type, severity, risk_score) |
| `PlanningDecision` | Selected decision + rationale + policy refs (fallback stub) |
| `GuardVerdict` | Approved boolean + reason string (fallback stub) |
| `ExecutionResult` | Whether the decision was executed + log message (fallback stub) |
| `DecisionRow` | BigQuery row (mirrors `runtime_decisions` table schema) |
| `DecisionType` | Enum: `NO_OP`, `BLOCK`, `ROLLBACK`, `QUARANTINE`, `ESCALATE` |

### Allowed Event Types

```
pipeline_failure  ·  policy_violation  ·  resilience_degradation  ·  manual_test_event
```

Unknown types are logged as warnings but still processed.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `GCP_PROJECT_ID` | ✅ | — | GCP project ID |
| `GCP_REGION` | ✅ | — | Deployment region |
| `BIGQUERY_DATASET` | ✅ | `agent_metrics` | Target BQ dataset |
| `BIGQUERY_TABLE` | ✅ | `runtime_decisions` | Target BQ table |
| `AGENTOPS_ENABLED` | — | `false` | Enable AgentOps telemetry |
| `AGENTOPS_API_KEY` | — | — | AgentOps API key (from Secret Manager) |
| `COGNIOPS_MODEL` | — | `gemini-2.0-flash` | ADK agent LLM model |
| `COGNIOPS_MODE`  | — | `shadow` | Execution mode: `shadow`, `advisory`, `enforce` |
| `OPA_URL` | — | `http://localhost:8181` | OPA server URL for policy evaluation |
| `CONFIG_BUCKET` | — | — | GCS bucket for live config (control mappings, thresholds) |
| `CONFIG_REFRESH_SEC` | — | `300` | TTL for config store cache (seconds) |
| `METRICS_INGEST_URL` | — | — | Endpoint for ActionTrace CloudEvent emission |
| `COMMIT_SHA` | — | `unknown` | Git commit SHA for provenance field |
| `LOG_LEVEL` | — | `INFO` | Python logging level |

---

## Local Development

```bash
# Create / activate venv
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run locally
cd runtime-agent
uvicorn main:app --reload --port 8080

# Send a test request (simulates Pub/Sub push)
python -c "
import base64, json, requests
event = {
    'event_id': 'test-001',
    'event_type': 'manual_test_event',
    'occurred_at': '2026-03-02T12:00:00Z',
    'source': 'local-dev',
    'context': {'status': 'testing', 'scenario_id': 'S1'}
}
body = {'message': {'data': base64.b64encode(json.dumps(event).encode()).decode()}}
r = requests.post('http://localhost:8080/events/runtime', json=body)
print(r.status_code, r.json())
"
```

> **Note:** BQ writes will fail locally unless `GOOGLE_APPLICATION_CREDENTIALS`
> points to a valid service account key. Failures are logged but not fatal.

---

## Unit Tests

```bash
cd runtime-agent
python -m pytest tests/ -v
```

Tests run offline (no GCP credentials or Gemini API required).
ADK pipeline tests use `InMemoryRunner` with mocked model callbacks.
Perception tests mock `query_baseline` — no BQ required.
Rego tests use OPA CLI (`opa eval`) and are skipped if OPA is not installed.
Endpoint tests mock the ADK runner and BQ writer via ASGI transport.

---

## Docker Build

```bash
cd runtime-agent
docker build -t runtime-agent:v0.1.0 .
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID=my-project \
  -e GCP_REGION=europe-west1 \
  -e BIGQUERY_DATASET=agent_metrics \
  -e BIGQUERY_TABLE=runtime_decisions \
  runtime-agent:v0.1.0
```

---

## Shadow Mode Invariants

In `shadow` mode, every decision row written to BigQuery satisfies:

| Field | Value | Reason |
|-------|-------|--------|
| `decision_executed` | `false` | OPA blocks all non-NO_OP actions in shadow mode |
| `mode` | `shadow` | Set via `COGNIOPS_MODE` env var |

The OPA policy `cogniops.runtime` enforces shadow mode restrictions.
These invariants are verified by `.local/scripts/verify_runtime_decision.sh`.

---

## Related Docs

- [Runtime Event Contract](../docs/runtime-event-contract.md) — event envelope and scenario mapping
- [System Guardrails](../docs/system-guardrails.md) — architecture invariants
- [IAM Specification](../docs/runtime_agent_iam.md) — service account roles
- [AI Design Architecture](../docs/ai-design-architecture.md) — full system design

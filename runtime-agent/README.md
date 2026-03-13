# Runtime Agent – Phase 0 + ADK Bootstrap + Guard & Execution + Telemetry (Shadow Mode)

Cloud Run micro-service that receives runtime events via Pub/Sub,
runs a four-stage decision pipeline, and logs every decision to BigQuery.

Includes the **ADK cognitive agent** (`agent/` module) with Gemini-based
planning via ADK tool calling (LLM confined to Planning module only),
**OPA + PQC guard** (fail-closed), **mode-gated execution** (shadow/advisory/enforce),
and **explainability telemetry** (ISO/NIST control mapping + CloudEvent ActionTraces).

> **Current constraint:** all decisions default to `shadow` mode —
> decisions are logged but not executed.

---

## Directory Layout

```
runtime-agent/
├── main.py                     # FastAPI app (POST /events/runtime, GET /healthz, GET /agent/info)
├── Dockerfile                  # python:3.12-slim + uvicorn
├── requirements.txt
│
├── models/
│   └── schemas.py              # Pydantic v2 models (event envelope, pipeline stages, BQ row)
│
├── agent/                      # ── ADK Cognitive Agent (Step 1+) ──
│   ├── __init__.py
│   ├── cogniops_agent.py       # Root LlmAgent "cogniops_planning" definition
│   ├── tools/
│   │   ├── perception_tool.py  # ADK FunctionTool — z-score + threshold anomaly detection
│   │   ├── anomaly_detection.py # Z-score & threshold scoring engine (Step 2)
│   │   ├── baseline_reader.py  # BQ 7-day rolling baseline queries (Step 2)
│   ├── execution_tools.py  # Mode-gated bounded actions: NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE
│   ├── github_client.py    # GitHub API: workflow_dispatch, issue creation (httpx async)
│   └── memory_tools.py     # Episodic memory: query recent decisions from BQ
│   ├── callbacks/
│   │   ├── guard_callback.py   # before_tool_callback (OPA + PQC guard, fail-closed)
│   │   └── opa_client.py       # OPA REST API client (timeout 5s, fail-closed)
│   └── prompts/
│       ├── system.txt          # System prompt with decision criteria matrix
│       ├── few_shot_s1.txt     # Pipeline failure: high CFR → ROLLBACK
│       ├── few_shot_s3.txt     # Resilience: high MTTD → ESCALATE / ROLLBACK
│       ├── few_shot_s5.txt     # Explainability: low ACR → ESCALATE
│       └── few_shot_ss2.txt    # Adaptive threat: integrity → QUARANTINE
│
├── perception/
│   └── handler.py              # perceive(event) → AnomalyOutput (Phase 0 stub)
├── planning/
│   └── playbook.py             # select_playbook(anomaly) → PlanningDecision (Phase 0 stub)
├── guard/
│   └── policy_check.py         # check_policy(decision) → GuardVerdict (Phase 0 stub)
├── execution/
│   └── executor.py             # execute(decision, verdict) → ExecutionResult (Phase 0 stub)
│
├── storage/
│   └── bigquery_writer.py      # write_decision(row) → bool  (best-effort)
├── telemetry/
│   ├── agentops_client.py      # trace_pipeline(event_id)  context manager
│   ├── llm_logger.py           # LLM call logging (prompt hash, latency, tokens)
│   ├── policy_refs.py          # ISO/NIST/IMO control mapping per DecisionType (Step 5)
│   └── trace_emitter.py        # ActionTrace CloudEvent builder + emitter (Step 5)
│
└── tests/                      # pytest unit tests (195 tests)
    ├── conftest.py
    ├── test_agent_pipeline.py  # ADK agent structure, tools, guard, InMemoryRunner pipeline
    ├── test_planning_llm.py    # Step 3: LLM planning, few-shots, episodic context, fallback, logger
    ├── test_guard_opa.py       # Step 4: OPA guard, PQC check, observation/execution gating
    ├── test_execution_modes.py # Step 4: shadow/advisory/enforce mode gating per tool
    ├── test_github_client.py   # Step 4: GitHub API mock tests (dispatch, issues)
    ├── test_explainability.py  # Step 5: ActionTrace validation, ACR compliance, emission
    ├── test_policy_refs.py     # Step 5: ISO/NIST/IMO control mapping per decision type
    ├── test_perception.py      # Phase 0 perception stub tests
    ├── test_perception_real.py # Step 2: z-score, threshold, combined scoring, graceful degradation
    ├── test_playbook.py
    ├── test_guard.py
    ├── test_executor.py
    ├── test_endpoint.py
    └── fixtures/
        └── mock_bq_baselines.json  # Mock BQ baseline data for S1-S4
```

---

## Pipeline

```
Pub/Sub push  →  POST /events/runtime
                       │
                 ┌─────▼──────┐
                 │ Perception  │  extract anomaly from event
                 └─────┬──────┘
                 ┌─────▼──────┐
                 │  Planning   │  select playbook (always NO_OP in Phase 0)
                 └─────┬──────┘
                 ┌─────▼──────┐
                 │   Guard     │  policy gate    (always approved in Phase 0)
                 └─────┬──────┘
                 ┌─────▼──────┐
                 │ Execution   │  apply action   (always skipped in Phase 0)
                 └─────┬──────┘
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

---

## Perception — Anomaly Detection (Step 2)

The perception layer uses **deterministic** anomaly detection — no LLM involved.

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

## Telemetry & Explainability (Step 5)

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

Every trace passes `validate_action_trace()` (**ACR = 1.0**) and is emitted
to the metrics ingest endpoint (when `METRICS_INGEST_URL` is configured).

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/events/runtime` | Pub/Sub push receiver — decodes envelope, runs pipeline, writes to BQ |
| `GET`  | `/healthz` | Liveness / readiness probe (`{"status":"ok","mode":"shadow","phase":0}`) |
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
| `PlanningDecision` | Selected decision + rationale + policy refs |
| `GuardVerdict` | Approved boolean + reason string |
| `ExecutionResult` | Whether the decision was executed + log message |
| `DecisionRow` | BigQuery row (mirrors `runtime_decisions` table schema) |
| `DecisionType` | Enum: `NO_OP`, `BLOCK`, `ROLLBACK`, `QUARANTINE`, `ESCALATE` |

### Allowed Event Types (Phase 0)

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
| `COGNIOPS_MODEL` | — | `gemini-2.0-flash` | ADK agent LLM model (Step 3+) |
| `COGNIOPS_MODE`  | — | `shadow` | Execution mode: `shadow`, `advisory`, `enforce` |
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

All 195 tests run offline (no GCP credentials or Gemini API required).
ADK pipeline tests use `InMemoryRunner` with mocked model callbacks.
Step 2 perception tests mock `query_baseline` — no BQ required.
The BigQuery writer is not invoked during tests — the endpoint tests
mock the full pipeline via ASGI transport.

---

## Docker Build

```bash
docker build -t runtime-agent:v0.1.0 .
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID=my-project \
  -e GCP_REGION=europe-west1 \
  -e BIGQUERY_DATASET=agent_metrics \
  -e BIGQUERY_TABLE=runtime_decisions \
  runtime-agent:v0.1.0
```

---

## Phase 0 Invariants

Every decision row written to BigQuery satisfies:

| Field | Value | Reason |
|-------|-------|--------|
| `decision` | `NO_OP` | No real actions in shadow mode |
| `decision_executed` | `false` | Execution module never acts |
| `mode` | `shadow` | Hard-coded for Phase 0 |

These invariants are verified by `scripts/verify_runtime_decision.sh`.

---

## Related Docs

- [Phase 0 Specification](../docs/phase0-runtime-ready-spec.md) — what to build
- [Runtime Event Contract](../docs/runtime-event-contract.md) — event envelope and scenario mapping
- [IAM Specification](../docs/runtime_agent_iam.md) — service account roles
- [Implementation Notes](../docs/phase0-implementation-notes.md) — commit history, architecture, gaps

# Runtime Event Contract
Phase 0 – CogniOps

---

## Event Envelope Schema

All runtime events must follow this structure:

{
  "event_id": "string (UUID)",
  "event_type": "string",
  "occurred_at": "RFC3339 timestamp",
  "source": "string",
  "context": {
    "run_id": "string (optional)",
    "scenario_id": "string (optional)",
    "stage": "string (optional)",
    "status": "string",
    "severity": "string",
    "commit_sha": "string (optional)"
  }
}

---

## Required Fields

- event_id
- event_type
- occurred_at
- source
- context.status

---

## Allowed Event Types (Phase 0)

- pipeline_failure
- policy_violation
- resilience_degradation
- manual_test_event

### Scenario Mapping

These event types correspond to the baseline scenarios that will
generate runtime events when the agent becomes active:

| Event Type              | Origin Scenario | Runtime Variant (Phase 1+) | Target Metric |
|-------------------------|-----------------|----------------------------|---------------|
| pipeline_failure        | S1 (CI/CD)      | S1'_runtime                | TTD, CFR      |
| policy_violation        | SS1 (OPA gate)  | SS1'_design (design-only)  | FDR, ACR      |
| resilience_degradation  | S3 (fault)      | S3'_runtime                | MTTD, MTTR    |
| manual_test_event       | Testing         | N/A                        | N/A           |

Future event types (Phase 1+):

- ota_anomaly → S2'_runtime (DSR)
- hitl_escalation → S5'_runtime (AL)
- integrity_failure → SS2'_runtime (MTTD)

---

## Validation Rules

- event_id must be unique
- occurred_at must be valid timestamp
- Unknown fields should be ignored but logged
- Invalid schema → return non-2xx (trigger retry)

---

## Example Event

{
  "event_id": "b3f0a9c1-1234-4567-8901-abcdef123456",
  "event_type": "manual_test_event",
  "occurred_at": "2026-03-01T12:00:00Z",
  "source": "test-publisher",
  "context": {
    "run_id": "run-001",
    "scenario_id": "S3",
    "stage": "deploy",
    "status": "fail",
    "severity": "medium"
  }
}

---

## Ingest Path Separation

Runtime events are delivered via Pub/Sub push to the `runtime-agent`
Cloud Run service, which writes to `agent_metrics.runtime_decisions`.

They MUST NOT be sent to `METRICS_INGEST_URL` (`scenario-runs-ingest`).
That endpoint serves baseline scenarios (S1–S5, SS1–SS2) and writes to
`agent_metrics.runs`.

The S5/SS2 CloudEvents ActionTraces (`stage = 'action_trace'`) that go to
`METRICS_INGEST_URL` are baseline explainability records — not runtime
agent decisions. These two paths are separate:

    Baseline:  GitHub Actions → METRICS_INGEST_URL → agent_metrics.runs
    Phase 0:   Pub/Sub → runtime-agent → agent_metrics.runtime_decisions

---

## Internal Perception Output Schema (Phase 0 stub)

After the Perception module processes an incoming event, it produces
a structured anomaly object. In Phase 0 this is hardcoded; in Phase 1
it will be computed by the Perception Agent.

```json
{
  "scenario": "S3",
  "anomaly_type": "resilience_degradation",
  "severity": 0.5,
  "risk_score": 0.5,
  "source_event_id": "b3f0a9c1-1234-4567-8901-abcdef123456"
}
```

Phase 0 defaults:

- severity: 0.5 (neutral — no real scoring)
- risk_score: 0.5 (neutral — no real scoring)
- anomaly_type: copied from event_type
- scenario: extracted from context.scenario_id or "unknown"

This schema is consumed by the Risk/Planning module to select a
bounded playbook (Phase 0: always returns hardcoded decision).
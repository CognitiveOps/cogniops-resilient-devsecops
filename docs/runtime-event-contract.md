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
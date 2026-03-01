Implement Phase 0 Runtime-Ready infrastructure according to:

docs/phase0-runtime-ready-spec.md
docs/runtime-event-contract.md
docs/runtime_agent_iam.md

CONSTRAINTS:
- Do not modify baseline workflows (S1–S5, SS1–SS2)
- Do not modify BigQuery ingestion schema
- Additive changes only
- No destructive action execution
- Stub-only playbooks

REQUIRED:

1. Create Pub/Sub topic + DLQ
2. Create Cloud Run runtime-agent service
3. Implement POST /events/runtime endpoint
4. Validate payload against runtime-event-contract
5. Implement bounded playbook stub
6. Integrate AgentOps (trace only, redact sensitive data)
7. Create BigQuery table runtime_explainability_logs
8. Add manual test publisher script
9. Add documentation

DEFINITION OF DONE:
- Test event processed
- AgentOps trace emitted
- Explainability row inserted
- No baseline behavior changed

Work incrementally and commit logically grouped changes.
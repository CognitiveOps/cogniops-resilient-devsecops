You are analyzing the CogniOps MSc thesis repository.

FIRST PRIORITY:
Carefully read these files in order:
1. README.md (baseline source of truth — describes what exists and must NOT be modified)
2. docs/phase0-runtime-ready-spec.md (Phase 0 specification — what to build)
3. docs/runtime-event-contract.md (event envelope + scenario mapping)
4. docs/runtime_agent_iam.md (IAM specification)

OBJECTIVE:
Propose a minimal additive structure for implementing Phase 0 Runtime-Ready infrastructure.

Phase 0 includes:
- Pub/Sub runtime event lane (topic + DLQ + push subscription)
- Cloud Run runtime-agent skeleton with 4 internal modules:
  - Perception Agent (receive + log event)
  - Risk/Planning Agent (return hardcoded decision)
  - Policy Guard (always pass)
  - Execution Agent (log decision, do nothing)
- Bounded playbook stub interface (NO_OP, BLOCK, ROLLBACK, QUARANTINE, ESCALATE)
- AgentOps telemetry (trace only, optional)
- Dedicated `agent_metrics.runtime_decisions` BigQuery table
- IAM: runtime-agent-sa with least-privilege roles
- Environment variables for Cloud Run service configuration
- Secret Manager reference for AgentOps API key (optional)

Phase 0 event flow:
  Publisher → Pub/Sub (runtime-events-v1) → Cloud Run (runtime-agent)
           → agent_metrics.runtime_decisions

Phase 0 excludes:
- Design-time agent (Architectural Synthesis System)
- PR synthesis
- Baseline schema changes
- Baseline workflow changes (S1–S5, SS1–SS2)
- Refactoring of existing components
- Episodic memory writes
- Metric-driven reaction (Phase 1 — BigQuery anomaly → Pub/Sub → agent)
- Execution of destructive mitigation actions

CONSTRAINTS:
- Fully backward compatible with baseline
- Additive changes only — new files, new resources
- No modification to agent_metrics.runs, scenario-runs-ingest, or any workflow
- Mode is always "shadow" in Phase 0 — no decisions are executed
- No code generation — only structured implementation plan

OUTPUT:
1. Baseline summary (from README)
2. Contract compliance check (spec + event contract + IAM)
3. Additive architecture proposal
4. Proposed folder structure for runtime-agent
5. Pub/Sub flow with DLQ
6. Runtime agent internal module responsibilities (4 agents)
7. Scenario mapping (event types → baseline scenarios → runtime variants)
8. Explainability logging strategy (runtime_decisions schema)
9. Required environment variables and secrets
10. IAM roles and service account bindings
11. Terraform resources needed (infra/runtime.tf)
    Expected: ~12 resources including SA, IAM bindings, Pub/Sub topics,
    subscription, BigQuery table, Cloud Run service.
    Reference existing main.tf resources — do not recreate them.
12. Testing strategy (unit tests per module + integration test scripts)
13. Definition of Done checklist

Do NOT generate code.
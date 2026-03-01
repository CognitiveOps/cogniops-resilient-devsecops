You are analyzing the CogniOps MSc thesis repository.

FIRST PRIORITY:
Carefully read README.md.
Treat it as the architectural source of truth.

OBJECTIVE:
Propose a minimal additive structure for implementing Phase 0 Runtime-Ready infrastructure.

Phase 0 includes:
- Pub/Sub runtime event lane
- Cloud Run runtime-agent skeleton
- Bounded playbook stub interface
- AgentOps telemetry (trace only)
- Explainability logging table

Phase 0 excludes:
- Design-time agent
- PR synthesis
- Schema changes
- Workflow changes
- Refactoring

CONSTRAINTS:
- Fully backward compatible
- Additive changes only
- No code generation
- Only structured implementation plan

OUTPUT:
1. Baseline summary
2. Additive architecture proposal
3. Proposed folder structure
4. Pub/Sub flow
5. Runtime agent responsibilities
6. Explainability logging strategy
7. Required environment variables
8. IAM roles
9. Definition of Done checklist

Do NOT generate code.
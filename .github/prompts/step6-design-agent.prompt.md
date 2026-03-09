---
description: "Implement Design-Time Agent for structural synthesis: context building, intent processing, proposal generation, validation."
agent: "agent"
---

# Step 6: Design-Time Agent

Read first:
- [Project governance](../copilot-instructions.md)
- [Runtime agent](../../runtime-agent/agent/cogniops_agent.py) (reference pattern)
- [OPA policies](../../security/policies/ss1.rego)
- [BQ schema](../../infra/main.tf) (agent_metrics tables)

## Task

Create the Design-Time Agentic System — structural synthesis that analyzes metrics and proposes improvements. Completely separate from the Runtime Agent.

## Architecture

```
design-agent/
├── main.py                          # FastAPI app or CLI entrypoint
├── requirements.txt                 # google-adk, google-cloud-bigquery, PyGithub
├── Dockerfile
├── agent/
│   ├── __init__.py
│   ├── design_agent.py              # ADK Agent: structural synthesis orchestrator
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── context_builder.py       # Tool: query BQ metrics, read GH workflows/policies
│   │   ├── proposal_generator.py    # Tool: generate structured improvement proposals
│   │   └── validator.py             # Tool: OPA simulate, YAML lint, dry-run validation
│   └── prompts/
│       ├── design_system.txt        # System prompt: architectural analysis role
│       ├── few_shot_optimize.txt    # "Reduce MTTR in S3" → structured proposal
│       └── few_shot_policy.txt      # "Improve FDR in SS1" → policy improvement
├── models/
│   ├── __init__.py
│   └── schemas.py                   # Pydantic: ProposalInput, ProposalOutput, ValidationResult
└── tests/
    ├── __init__.py
    ├── test_context_builder.py
    ├── test_proposal_generator.py
    └── test_validator.py
```

## Implementation

### 1. Context Builder Tool
Reads from multiple sources to build structured analysis context:
- BQ: metric trends per scenario (last 30 days, weekly aggregates)
- BQ: runtime_decisions (agent actions, outcomes, patterns)
- GitHub: workflow files (current pipeline structure)
- GitHub: OPA policies (current security posture)
- Output: structured JSON context for the Planning agent

### 2. Design Planning Agent
```python
design_agent = Agent(
    name="cogniops_design",
    model="gemini-2.0-flash",
    instruction=load_prompt("design_system.txt"),
    tools=[build_context, generate_proposal, validate_proposal],
)
```
LLM analyzes context and generates proposals via tool calls.

### 3. Proposal Generator Tool
Output format (JSON, stored in GCS):
```json
{
    "proposal_id": "uuid",
    "intent": "Reduce MTTR in S3",
    "scenario": "S3",
    "changes": [
        {"type": "threshold_adjustment", "file": "s3_rollback.yml", "current": "120s", "proposed": "60s"},
        {"type": "policy_addition", "file": "ss1.rego", "rule": "..."}
    ],
    "expected_impact": {"MTTR": "-30%", "MTTD": "-10%"},
    "validation": {"opa_sim": "pass", "yaml_lint": "pass", "dry_run": "pass"},
    "rationale": "...",
    "policy_refs": ["NIST CP-10", "ISO 27001 A.17.1.2"]
}
```

### 4. Validation Tool
Before storing any proposal:
- YAML lint (if workflow changes proposed)
- OPA simulate (if policy changes proposed)
- Schema validation (Pydantic)
- If ANY validation fails → discard proposal, log reason

### 5. Output
- Store validated proposals in GCS: `gs://{bucket}/proposals/{proposal_id}.json`
- Optionally create GitHub Issue with proposal summary
- NEVER create branches, PRs, or modify code directly

### 6. Terraform (`infra/design.tf`)
- New SA: design-agent-sa
- BQ read access to agent_metrics (dataViewer, not dataEditor)
- GCS write access to proposals bucket
- Cloud Run (or Cloud Run Jobs for batch mode)

## Critical Constraints
- Design agent NEVER executes mitigation (no rollback, block, etc.)
- Design agent NEVER modifies live infrastructure
- Design agent NEVER creates branches or PRs
- Output is always proposals (JSON) — human decides what to apply
- All proposals must pass validation before storage
- Separate service account from runtime-agent-sa

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - Design-Time Agent purpose, pipeline, and output format
   - Separation from Runtime Agent (different SA, different triggers)
   - Proposal validation chain (OPA sim + YAML lint + dry-run)
2. Update `README.md` § "📊 Implementation Progress" — mark Step 6 as ✅
3. Update `docs/ai-design-architecture.md` § 5 with actual implementation details
4. Update `docs/runtime_agent_iam.md` with new `design-agent-sa` roles
5. Create `design-agent/README.md` with service documentation

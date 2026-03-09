---
description: "Implement real OPA guard callback and execution tools with mode gating (shadow/advisory/enforce)."
agent: "agent"
---

# Step 4: Guard + Execution — Real Actions

Read first:
- [Runtime agent instructions](../instructions/runtime-agent.instructions.md)
- [Guard callback stub](../../runtime-agent/agent/callbacks/guard_callback.py) (from Step 1)
- [Execution tools](../../runtime-agent/agent/tools/execution_tools.py) (from Step 1)
- [OPA policy](../../security/policies/ss1.rego)
- [PQC verify](../../baseline/security/pqc/verify.py)

## Task

Make guard and execution real. Guard does OPA+PQC checks before tool execution. Execution tools perform real actions gated by mode (shadow/advisory/enforce).

## Implementation

### 1. Guard callback (`agent/callbacks/guard_callback.py`)

ADK `before_tool_callback` — runs before any execution tool is called:

```python
async def guard_check(tool_call, context) -> Optional[dict]:
    """
    Pre-execution guard: OPA policy check + PQC integrity.
    Returns None to allow, or dict with error to block.
    """
    # 1. OPA policy check
    opa_result = await opa_eval(tool_call, context)
    if not opa_result.allowed:
        log_guard_block(reason="opa_violation", details=opa_result.denials)
        return {"error": f"OPA blocked: {opa_result.denials}"}

    # 2. PQC integrity check (if relevant to this scenario)
    if context.get("scenario") in ("S4", "SS2"):
        pqc_ok = await pqc_integrity_check(context)
        if not pqc_ok:
            log_guard_block(reason="pqc_failure")
            return {"error": "PQC integrity check failed"}

    return None  # Allow execution
```

### 2. OPA client (`agent/callbacks/opa_client.py`)
- Call OPA REST API or `opa eval` CLI
- Input: decision context (scenario, action, anomaly details)
- Output: allowed (bool) + denials (list[str])
- Timeout: 5s, fallback: block (fail-closed)

### 3. Execution tools with mode gating (`agent/tools/execution_tools.py`)

Each tool checks runtime mode before executing:

```python
MODE = os.getenv("COGNIOPS_MODE", "shadow")  # shadow | advisory | enforce

def trigger_rollback(scenario: str, run_id: str, rationale: str) -> dict:
    """Trigger rollback workflow for failed deployment."""
    if MODE == "shadow":
        return {"status": "shadow", "action": "ROLLBACK", "message": "Logged only"}
    if MODE == "advisory":
        create_notification_issue(...)  # GitHub Issue as notification
        return {"status": "advisory", "action": "ROLLBACK", "message": "Notified"}
    # enforce mode
    dispatch_workflow("s3_rollback.yml", inputs={...})
    return {"status": "enforced", "action": "ROLLBACK"}
```

Tools to implement:
- `no_action()` — Log NO_OP, always succeeds
- `trigger_rollback()` — GitHub workflow_dispatch for rollback
- `block_deployment()` — Emit block event or fail deployment check
- `quarantine_artifact()` — Mark artifact in registry
- `create_hitl_issue()` — GitHub Issue for human review (ESCALATE)

### 4. GitHub API client (`agent/tools/github_client.py`)
- workflow_dispatch: POST to GitHub API
- create_issue: POST to GitHub API
- Auth: GitHub App token or PAT from Secret Manager
- Timeout: 10s, retry: 1x

### 5. Tests
- `tests/test_guard_opa.py`: mock OPA → test allow/deny
- `tests/test_execution_modes.py`: test shadow/advisory/enforce behavior
- `tests/test_github_client.py`: mock GitHub API responses

## Constraints
- Guard fails CLOSED (if OPA unavailable → block)
- Execution fails OPEN (if GitHub unavailable → log + NO_OP)
- New capabilities start in shadow mode
- Never call real GitHub API in unit tests (mock only)

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - OPA guard callback integration
   - PQC integrity check in guard pipeline
   - Mode-gated execution (shadow/advisory/enforce) with actual behaviour
   - GitHub API integration (rollback, HITL issues)
2. Update `README.md` § "📊 Implementation Progress" — mark Step 4 as ✅
3. Update `docs/system-guardrails.md` § Sec-3, Sec-4, S-3 with actual implementation details
4. Update `docs/runtime_agent_iam.md` if any new IAM roles were required

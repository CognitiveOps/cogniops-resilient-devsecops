# Pull Request

## Summary
<!-- One or two sentences describing the change. -->

## Component
- [ ] runtime-agent
- [ ] design-agent
- [ ] security-agent
- [ ] evaluation
- [ ] baseline
- [ ] infrastructure
- [ ] documentation
- [ ] other

## Checklist
- [ ] I have read `CONTRIBUTING.md`.
- [ ] Baseline components remain unchanged (they are immutable for AI-driven modifications).
- [ ] New/modified code includes tests.
- [ ] `just test-all` (or the equivalent per-agent pytest commands) passes locally.
- [ ] `python -m compileall runtime-agent design-agent security-agent evaluation functions baseline` passes.
- [ ] ADK agents, LLM calls, or policy changes include a fallback to `NO_OP`.
- [ ] Sensitive values are not hard-coded.

## How to test
<!-- Commands or scenarios a reviewer can run to verify the change. -->

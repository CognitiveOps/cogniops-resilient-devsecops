# Contributing to CogniOps

Thanks for your interest. This repository started as an MSc thesis project and is now maintained as an open portfolio piece for autonomous cognitive agents in DevSecOps.

## How to contribute

1. **Open an issue** first to discuss the change — especially for new scenarios, agent actions, or infrastructure changes.
2. **Fork the repository** and create a feature branch.
3. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
4. **Run tests** before committing:
   ```bash
   pytest runtime-agent/tests
   pytest design-agent/tests
   pytest security-agent/tests
   pytest evaluation/tests
   pytest baseline/services/edge_cv_app/tests
   pytest functions/ingest_runs

   # The app container test requires Docker and is run manually:
   # pytest baseline/services/app/tests
   ```
5. **Keep the architecture separation intact**:
   - Runtime agent must not edit structure (no PRs, no YAML changes).
   - Design-time agent must not execute mitigations.
   - LLM calls must have a safe fallback and schema validation.
6. **Submit a pull request** with a clear description and, if possible, a test.

## Code conventions

- Python 3.12 with type hints on public functions.
- Pydantic v2 for all schemas.
- `from __future__ import annotations` in all modules.
- Tests mock external services (GCP, GitHub API, LLM).

## Questions?

Open an issue or start a discussion in the repository.

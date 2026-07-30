# Contributing to CogniOps

Thanks for your interest. This repository started as an MSc thesis project and is now maintained as an open portfolio piece for bounded-autonomy cognitive agents in DevSecOps.

## Quick ways to contribute

- **Try the local demo** — run `docker compose up --build`, open an issue if it breaks.
- **Fix a typo or unclear explanation** in README / docs.
- **Improve Windows dev experience** — the repo is developed on Windows and has pytest discovery quirks.
- **Add tests** for edge cases in the deterministic modules (`baseline/`, `guard/`, `execution/`).

## What we are *not* looking for

- New AI models or prompt engineering experiments.
- New unbounded actions for the runtime agent.
- Breaking changes to the BigQuery `agent_metrics.runs` schema.
- Large refactoring of the agent architecture without prior discussion.

## How to contribute

1. **Open an issue** first to discuss the change — especially for new scenarios, agent actions, or infrastructure changes.
2. **Fork the repository** and create a feature branch.
3. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. **Run tests** before committing. Because each agent package defines its own top-level `agent` and `models` packages, run them from their own directories (or use the `Justfile`):
   ```bash
   just test-all                    # runs all agent + evaluation tests

   # Or run each package individually
   pytest runtime-agent/test_runtime -q
   pytest design-agent/test_design -q
   pytest security-agent/test_security -q
   pytest evaluation/test_evaluation -q

   # Optional: baseline / functions require extra local deps
   pytest baseline/services/edge_cv_app/tests -q
   pytest functions/ingest_runs -q

   # The app container test requires Docker and is run manually:
   # pytest baseline/services/app/tests
   ```
5. **Run syntax validation**:
   ```bash
   python -m compileall -q baseline design-agent evaluation functions runtime-agent security-agent
   ```
6. **Run the local Docker Compose demo** if your change touches the agents or OPA policy:
   ```bash
   cp local.env .env
   # edit .env and set GEMINI_API_KEY
   docker compose up --build
   ```
7. **Keep the architecture separation intact**:
   - Runtime agent must not edit structure (no PRs, no YAML changes).
   - Design-time agent must not execute mitigations.
   - LLM calls must have a safe fallback and schema validation.
8. **Submit a pull request** with a clear description and, if possible, a test. Keep commits atomic and messages in English, e.g. `docs: clarify local demo env setup`.

## Code conventions

- Python 3.12 with type hints on public functions.
- Pydantic v2 for all schemas.
- `from __future__ import annotations` in all modules.
- Tests mock external services (GCP, GitHub API, LLM).

## Questions?

Open an issue or start a discussion in the repository.

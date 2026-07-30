# Testing Guide

## Quick start

```bash
pip install -r requirements-dev.txt

# Run the evaluation suite from the repo root
pytest -q

# Run all agent + evaluation tests
just test-all        # or `make test-all` if you don't have `just`
```

## Why per-directory tests?

Each agent package (`runtime-agent`, `design-agent`, `security-agent`) defines
its own top-level `agent` and `models` Python packages. Running pytest from the
repository root causes import collisions because those names are shared.

Therefore the agent tests must be run **from inside each agent directory**:

```bash
cd runtime-agent && pytest test_runtime -q
cd design-agent  && pytest test_design  -q
cd security-agent && pytest test_security -q
cd evaluation    && pytest test_evaluation -q
```

The root [`pytest.ini`](../pytest.ini) only discovers `evaluation/test_evaluation`
by default, so a plain `pytest -q` is safe and deterministic.

## Full matrix

| Suite | Command | Needs |
|---|---|---|
| Evaluation | `pytest -q` | numpy, pandas, scipy |
| Runtime agent | `cd runtime-agent && pytest test_runtime -q` | google-adk, fastapi, httpx |
| Design agent | `cd design-agent && pytest test_design -q` | google-adk, fastapi, httpx |
| Security agent | `cd security-agent && pytest test_security -q` | google-adk, fastapi, httpx |
| Baseline services | `pytest baseline/services/edge_cv_app/tests -q` | opencv-python-headless |
| Cloud functions | `pytest functions/ingest_runs -q` | google-cloud-pubsub |

## CI

The GitHub Actions workflow (`ci.yml`) runs `compileall` first, then tests each
package with the correct `working-directory`. See [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Windows notes

This repository is developed on Windows. If you see import errors when running
pytest from the root, make sure you are inside the agent directory and that no
stale `__pycache__` directories are cached.

```powershell
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

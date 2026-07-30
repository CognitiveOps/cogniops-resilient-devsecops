# Justfile — CogniOps task runner
# Install `just`: https://github.com/casey/just
# Windows users can run these recipes in PowerShell or use `just --shell bash`.

set shell := ["powershell", "-c"]

PYTHON := "python"
PYTEST := PYTHON + " -m pytest"

# ── Development ─────────────────────────────────────────────────────

# Install all Python dependencies
install:
    {{PYTHON}} -m pip install --upgrade pip
    {{PYTHON}} -m pip install -r requirements.txt
    {{PYTHON}} -m pip install -r runtime-agent/requirements.txt
    {{PYTHON}} -m pip install -r design-agent/requirements.txt
    {{PYTHON}} -m pip install -r security-agent/requirements.txt

# Format all Python files
fmt:
    {{PYTHON}} -m ruff format .

# Lint all Python files
lint:
    {{PYTHON}} -m ruff check .

# Type-check all Python files
-typecheck:
    {{PYTHON}} -m mypy runtime-agent design-agent security-agent evaluation

# ── Testing ──────────────────────────────────────────────────────────

# Run the evaluation test suite from the repository root
test-evaluation:
    {{PYTEST}} evaluation/test_evaluation -q

# Run runtime-agent tests (must run from its own directory because of shared `agent`/`models` package names)
test-runtime:
    cd runtime-agent; {{PYTEST}} test_runtime -q

# Run design-agent tests
test-design:
    cd design-agent; {{PYTEST}} test_design -q

# Run security-agent tests
test-security:
    cd security-agent; {{PYTEST}} test_security -q

# Run all agent and evaluation tests
test-all: test-runtime test-design test-security test-evaluation

# Run baseline tests (requires full local dependencies: opencv-python-headless, etc.)
test-baseline:
    {{PYTEST}} baseline/services/app/tests baseline/services/edge_cv_app/tests -q

# Run cloud-function tests (requires google-cloud-* packages)
test-functions:
    {{PYTEST}} functions/ingest_runs -q

# ── Local demos ─────────────────────────────────────────────────────

# Start the runtime-agent FastAPI server locally
serve-runtime:
    cd runtime-agent; {{PYTHON}} main.py

# Start the design-agent FastAPI server locally
serve-design:
    cd design-agent; {{PYTHON}} main.py

# Start the security-agent FastAPI server locally
serve-security:
    cd security-agent; {{PYTHON}} main.py

# ── Quality gates ───────────────────────────────────────────────────

# Smoke-test that every agent package imports cleanly
smoke-imports:
    cd runtime-agent; {{PYTHON}} -c "from agent.cogniops_agent import cogniops_agent; print('runtime-agent OK')"
    cd design-agent; {{PYTHON}} -c "from agent.design_agent import design_agent; print('design-agent OK')"
    cd security-agent; {{PYTHON}} -c "from agent.security_agent import security_agent; print('security-agent OK')"

# Compile all Python files to surface syntax errors
compile:
    {{PYTHON}} -m compileall runtime-agent design-agent security-agent evaluation functions baseline

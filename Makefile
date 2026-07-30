# Makefile — CogniOps fallback task runner (if you don't have `just` installed)
# Windows: run in Git Bash / WSL, or use `nmake`/`gnumake` equivalents.

PYTHON ?= python
PYTEST = $(PYTHON) -m pytest

.PHONY: install test-all test-runtime test-design test-security test-evaluation compile lint fmt

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

test-all: test-runtime test-design test-security test-evaluation

test-evaluation:
	$(PYTEST) evaluation/test_evaluation -q

test-runtime:
	cd runtime-agent && $(PYTEST) test_runtime -q

test-design:
	cd design-agent && $(PYTEST) test_design -q

test-security:
	cd security-agent && $(PYTEST) test_security -q

compile:
	$(PYTHON) -m compileall -q runtime-agent design-agent security-agent evaluation functions baseline

lint:
	$(PYTHON) -m ruff check .

fmt:
	$(PYTHON) -m ruff format .

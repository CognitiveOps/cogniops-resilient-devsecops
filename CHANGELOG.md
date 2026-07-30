# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Repository-level `Justfile` for common dev/test/serve tasks.
- `requirements-dev.txt` aggregating all agent, baseline and function test dependencies.
- GitHub issue templates (bug report, feature request) and pull request template.
- CI compile-all gate and per-agent test matrix with `working-directory`.
- This `CHANGELOG.md`.

### Changed
- Renamed agent test directories from generic `tests` to `test_runtime`,
  `test_design`, `test_security` and `test_evaluation` to avoid import collisions.
- Updated `pytest.ini` to run only the evaluation suite by default; agent tests
  are invoked per-package via `just test-*` or from their own directories.
- Polished `README.md`, `CONTRIBUTING.md` and `docs/local-setup.md`.

### Fixed
- Removed root `conftest.py` that evicted shared `agent`/`models` modules and
  broke patching in runtime-agent tests.
- CI workflow now uses the renamed test directories.

## [0.1.0-alpha] - 2026-05-27

### Added
- Initial public release of the CogniOps resilient DevSecOps agent framework.
- Runtime agent (ADK + Gemini) for operational mitigation.
- Design-time agent for structural improvement proposals.
- Security compliance agent for policy/gap analysis.
- Evaluation framework with 2-axis metrics.
- Baseline deterministic scenarios S1–S5, SS1–SS2 via GitHub Actions.
- Terraform infrastructure for GCP.

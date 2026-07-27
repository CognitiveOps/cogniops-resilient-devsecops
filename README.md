# CogniOps — Autonomous Cognitive AI Agent for Resilient DevSecOps

> MSc thesis implementation: an autonomous cognitive agent stack that reasons over CI/CD, edge OTA, resilience, post-quantum security, and explainability — with deterministic guardrails and a rigorous 2-axis evaluation framework.

[![CI](https://github.com/CognitiveOps/cogniops-resilient-devsecops/actions/workflows/ci.yml/badge.svg)](https://github.com/CognitiveOps/cogniops-resilient-devsecops/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Problem

Modern DevSecOps pipelines span cloud CI/CD, edge deployments, rollback resilience, cryptographic verification, and human-in-the-loop approval. Coordinating these concerns with hard safety constraints is difficult:

- A deployment rollback must happen quickly, but not violate policy.
- An edge OTA update must be verified, even on constrained hardware.
- A cognitive agent can propose optimizations, but must not game the metrics or bypass guardrails.

CogniOps treats these as a unified control problem: a **cognitive control plane** supervises a **deterministic substrate**, with bounded actions, structured outputs, and causal reasoning.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    Cognitive Control Plane                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Runtime     │  │ Design-Time │  │ Security /          │  │
│  │ Agent       │  │ Agent       │  │ Compliance Agent    │  │
│  │ (mitigate)  │  │ (improve)   │  │ (audit)             │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              Deterministic Substrate (S1–SS2)                │
│  GitHub Actions · OPA · PQC (ML-DSA) · Cloud Run · BigQuery  │
└──────────────────────────────────────────────────────────────┘
```

### Design principles

- **Runtime never edits structure** — no PRs, no YAML changes.
- **Design-time never executes mitigation** — proposals only, validated before promotion.
- **LLM only in planning agents** — all other modules are deterministic.
- **Every LLM call has a fallback** — safe default (NO_OP), audit logging, schema validation.
- **Bounded action surface** — only `NO_OP`, `BLOCK`, `ROLLBACK`, `QUARANTINE`, `ESCALATE`.

## What it does

| Scenario | Concern | What is measured |
|----------|---------|------------------|
| **S1** | Cloud CI/CD | Time-to-deploy (TTD), change-failure rate (CFR), deployment frequency (DF) |
| **S2** | Edge OTA | Download latency (TDL), deployment success rate (DSR), edge TTD |
| **S3** | Resilience | Mean time to detect/recover (MTTD/MTTR) for cloud and edge faults |
| **S4** | PQC validation | Verification time (TTV), verification success (VSR), failure detection (FDR) |
| **S5** | Explainability | Approval latency (AL), audit completeness rate (ACR) |
| **SS1** | Policy audit | CFR, FDR across deterministic OPA policy cases |
| **SS2** | Adaptive threat | MTTD, AL, ACR under injected integrity/runtime faults |

## Evidence

The system was evaluated with **5,833 metric samples across 54 comparisons** (Era 1) and a follow-up **Era 2** remediation pass. See the detailed evidence in [`docs/showcase-evidence.md`](docs/showcase-evidence.md).

### Selected results

| Scenario | Metric | Improvement | Effect size | Note |
|----------|--------|------------:|------------:|------|
| S3 Cloud | MTTD | **−65%** | d = −0.94 (large) | Runtime agent detects and escalates faster than static thresholds |
| S3 Cloud | MTTR | **−32%** | d = −0.47 (small) | Full variant (runtime + design) recovers faster |
| SS2 | AL | **−23%** | d = −1.25 (large) | Design agent reduces human-approval latency |
| S4 | FDR/VSR | 100% | — | All tampered artifacts detected; all valid signatures verified |
| S1 | CFR | 0% | — | No deployment failures across baseline or agent variants |

### Honest limitations

The evaluation also surfaced real overhead costs:

- **S3 Edge MTTR** worsened by ~150% with runtime-agent involvement due to Cloud Run round-trip latency.
- **S5 AL** worsened by ~200% because the cognitive `/decide` call added ~23 s of system overhead.
- The design agent autonomously proposed substrate tuning that improved raw metrics, but some gains were sleep-gate artifacts rather than genuine latency reductions (documented as Goodhart's Law).

These trade-offs are reported, not hidden. See [`docs/showcase-evidence.md`](docs/showcase-evidence.md).

## Tech stack

| Layer | Components |
|-------|-----------|
| Agent framework | Google ADK (`LlmAgent`), Vertex AI Gemini 2.0 Flash |
| Language | Python 3.12, type hints, Pydantic v2, FastAPI, pytest |
| CI/CD | GitHub Actions, Workload Identity Federation (OIDC) |
| Infrastructure | Terraform — Artifact Registry, Cloud Run, BigQuery, IAM |
| Security | OPA (Rego), post-quantum ML-DSA (FIPS 204) via liboqs |
| Observability | BigQuery `agent_metrics.runs`, structured JSON logs |

## Repository layout

```
├── baseline/         # Deterministic DevSecOps scenarios S1–S5, SS1–SS2
├── runtime-agent/    # ADK runtime agent: perceive → plan → guard → act
├── design-agent/     # ADK design-time agent: metrics → causal graph → proposal
├── security-agent/   # ADK compliance agent: feed ingestion → audit proposal
├── evaluation/       # 2-axis evaluation framework, SQL, plots, tests
├── infra/            # Terraform IaC
├── security/         # OPA policies
├── functions/        # Cloud Functions for metrics ingest
├── docs/             # Architecture, guardrails, evaluation evidence
└── scripts/          # Integration and dispatch scripts
```

## Quick start

```bash
# Clone
 git clone git@github.com:CognitiveOps/cogniops-resilient-devsecops.git
 cd cogniops-resilient-devsecops

# Create a virtual environment
python -m venv .venv
. .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest
```

Running the full scenarios requires a GCP project with Workload Identity Federation. The detailed setup is in [`docs/thesis-setup.md`](docs/thesis-setup.md) (retained from the original thesis documentation).

## Why this matters

This work demonstrates:

- How to build a **safety-first cognitive agent** with explicit guardrails and bounded actions.
- How to **separate deterministic substrate from AI reasoning** so failures are explainable.
- How to **evaluate agent systems rigorously** with statistical effect sizes, not just accuracy.
- How to **report limitations honestly** — including cases where the agent makes things worse.

## Thesis

Yanna Koutroumpi, *Autonomous Cognitive AI Agent for Resilient DevSecOps Environments*, MSc thesis, 2026.

## License

MIT — see [LICENSE](LICENSE).

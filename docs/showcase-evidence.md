# Showcase Evidence

This page summarizes the quantitative evidence behind the CogniOps 2-axis
evaluation. The full evaluation framework, statistical methods, and reproduction
instructions are documented in [`../evaluation/README.md`](../evaluation/README.md).

## Evaluation Design

The 2-axis model compares the deterministic baseline against design-time and
runtime cognitive assistance:

| Variant | Design Agent | Runtime Agent |
|---|---|---|
| `baseline` | ✗ | ✗ |
| `design_only` | ✓ | ✗ |
| `runtime_only` | ✗ | ✓ |
| `full` | ✓ | ✓ |

Era 1 covered all 8 scenarios with **5,833 metric samples across 54 comparisons**.
Era 2 re-ran S3 Cloud, S3 Edge, and S5 after causal-graph improvements to the
design agent.

## Selected Results

| Scenario | Metric | Variant | Δ | Effect size | Significant |
|---|---|---|---|---:|:---|
| S3 Cloud | MTTD | runtime_only | **−65%** | d = −0.94 (large) | ✅ |
| S3 Cloud | MTTD | full | **−66%** | d = −0.94 (large) | ✅ |
| S3 Cloud | MTTR | full | **−32%** | d = −0.47 (small) | ✅ |
| SS2 | AL | design_only | **−23%** | d = −1.25 (large) | ✅ |
| S4 | FDR | all | 100% | — | — |
| S4 | VSR | all | 100% | — | — |
| S1 | CFR | all | 0% | — | — |

Security invariants were preserved across all variants: **FDR = 100%**, **VSR = 100%**,
**ACR = 100%**, and **CFR = 0%**.

## Honest Limitations

The evaluation also surfaced real overhead costs:

- **S3 Edge MTTR** worsened by ~150% when the runtime agent was involved, due
to Cloud Run round-trip latency on the constrained edge runner.
- **S5 AL** worsened by ~200% because the cognitive `/decide` call added ~23 s
of system overhead.
- Some design-agent gains on sleep-gate metrics were flagged as Goodhart's Law
artifacts rather than genuine latency reductions.

These trade-offs are reported transparently; they are part of the thesis
narrative on the security–latency trade-off of real-time AI risk assessment.

## Reproducibility

- Experiment runner: [`evaluation/scripts/run_experiment.py`](../evaluation/scripts/run_experiment.py)
- Statistical tests: Mann–Whitney U, Cohen's *d*, bootstrap 95% CI
- Tagged snapshot: [`v0.1.0-alpha`](https://github.com/CognitiveOps/cogniops-resilient-devsecops/releases/tag/v0.1.0-alpha)

The raw metric exports and analysis charts are generated locally by the
experiment runner and are excluded from version control (see `.gitignore`).

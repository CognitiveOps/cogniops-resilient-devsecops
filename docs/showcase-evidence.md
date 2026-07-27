# Evaluation Evidence

This page summarises the empirical evidence that the CogniOps agent stack actually ran and produced measurable outcomes. All data was generated from the 2-axis evaluation framework in [`evaluation/`](evaluation/).

## Evaluation design

- **Era 1** (`20260420T161616Z`): full 8-scenario evaluation, 54 comparisons, 5,833 metric samples, labelled baselines only, causal mode.
- **Era 2** (`20260504T054526Z`): remediation subset on the three Era 1 worse cases (S3 Cloud, S3 Edge, S5), 18 comparisons, 3,337 metric samples.
- **Variants**: `baseline`, `design_only`, `runtime_only`, `full`.
- **Statistical test**: Mann-Whitney U with Holm-Bonferroni correction; effect size via Cohen's d.

Agent configuration:

| Parameter | Runtime Agent | Design Agent | Security Agent |
|---|---|---|---|
| Model | Gemini 2.0 Flash | Gemini 2.0 Flash | Gemini 2.0 Flash |
| Temperature | 0.0 | default | default |
| Framework | Google ADK `LlmAgent` | Google ADK `LlmAgent` | Google ADK `LlmAgent` |
| Guard | OPA + PQC (`before_tool_callback`) | — | — |

## Era 1: flagship improvements

| Scenario | Metric | Variant | Δ% | p-value | Cohen's d | Effect | Improved |
|----------|--------|---------|---:|--------:|----------:|--------|:--------:|
| S3 Cloud | MTTD | runtime_only | **−65.2%** | <0.001 | **−0.94** | large | ✅ |
| S3 Cloud | MTTD | full | **−65.7%** | <0.001 | **−0.94** | large | ✅ |
| S3 Cloud | MTTR | runtime_only | **−27.2%** | 0.021 | **−0.40** | small | ✅ |
| S3 Cloud | MTTR | full | **−32.2%** | 0.002 | **−0.47** | small | ✅ |
| SS2 | AL | design_only | **−23.3%** | <0.001 | **−1.25** | large | ✅ |

## Era 1: honest worsenings

| Scenario | Metric | Variant | Δ% | p-value | Cohen's d | Effect | Note |
|----------|--------|---------|---:|--------:|----------:|--------|------|
| S3 Edge | MTTR | runtime_only | **+145.6%** | <0.001 | **+2.54** | large | Cloud Run round-trip dominates an 8 s baseline |
| S3 Edge | MTTR | full | **+149.6%** | <0.001 | **+3.61** | large | Same architectural overhead |
| S5 | AL | runtime_only | **+194.8%** | <0.001 | **+0.93** | large | `/decide` pipeline adds ~23 s system overhead |
| S5 | AL | full | **+217.3%** | <0.001 | **+1.05** | large | Same overhead plus design stage |

## Security and reliability invariants

Across all variants and both eras:

- **FDR = 100%** — all tampered or invalid artifacts detected.
- **VSR = 100%** — all valid PQC signatures verified.
- **ACR = 100%** — all actions have full audit trace.
- **CFR = 0%** — no deployment failures in S1 or SS1.

## Era 2: remediation of worse cases

The design agent used a causal graph and parameter validator to propose substrate tuning:

| Worse Case | Era 1 Δ% | Era 1 d | Era 2 Action | Era 2 Δ% | Era 2 d | Status |
|---|---:|---:|---|---|---:|---:|:---|
| S5 AL (runtime_only) | +195% | +1.0 | `S5_APPROVAL_DELAY_SEC` 10→1 s | −30% | −0.38 | Sleep artefact reduced; system overhead unchanged |
| S5 AL (full) | +217% | +1.05 | delay 10→1 s + warm instances | −23% | −0.29 | Sleep artefact reduced; system overhead unchanged |
| S3 Edge MTTR (runtime/full) | +150% | +3.6 | poll 1→0.5 s + warm instances | +11% | +3.7 | Reduced, not fixed; dominated by cold-start variance |

### What Era 2 revealed

The design agent converged autonomously to the minimum bound (`S5_APPROVAL_DELAY_SEC=1 s`) once causal constraints were added. However, the raw improvement was partly a **Goodhart's Law** effect: the metric improved because the confounding `sleep` gate was shortened, not because the `/decide` latency was reduced.

Sleep-normalised system overhead for S5:

| Variant | Overhead |
|---|---:|
| baseline | 1.9 s |
| design_only | 3.9 s |
| runtime_only | 25.1 s |
| full | 32.8 s |

This kind of honest reporting is the point of the 2-axis evaluation: a metric can improve while the underlying system property stays the same.

## Visual evidence

Pre-generated plots are committed under [`evaluation/results/analysis/graphs/`](evaluation/results/analysis/graphs/):

![Era 1 effect-size heatmap](../evaluation/results/analysis/graphs/effect_size_heatmap.png)

*Era 1 effect-size heatmap: 54 comparisons across 8 scenarios. Blue cells = improvement, red cells = worsening.*

![Two-axis quadrant](../evaluation/results/analysis/graphs/two_axis_quadrant.png)

*Two-axis evaluation quadrant: statistical significance (x) vs practical significance (y). The upper-right quadrant contains the outcomes that are both statistically robust and practically meaningful.*

## Reproducibility

The evaluation command (requires a GCP project configured with Workload Identity Federation or Application Default Credentials):

```bash
python -m evaluation.scripts.run_experiment \
  --scenarios s1 s2 s3_cloud s3_edge s4 s5 ss1 ss2 \
  --labeled-baselines-only --causal-mode -v
```

Raw results, comparison CSVs, and summary JSONs are in [`evaluation/results/`](evaluation/results/).

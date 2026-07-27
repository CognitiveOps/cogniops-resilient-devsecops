# 2-Axis Evaluation Framework

Publishable evaluation framework for the CogniOps thesis: measures autonomous agent impact across two orthogonal axes of intelligence.

## 2-Axis Model

|  | Runtime OFF | Runtime ON |
|---|---|---|
| **Design OFF** | `baseline` | `runtime_only` |
| **Design ON** | `design_only` | `full` |

Each cell is a **variant** — a complete system configuration run against all scenarios.

## Metrics

| Scenario | Metrics | Direction |
|---|---|---|
| S1 (CI/CD) | TTD, CFR, DF | lower, lower, higher |
| S2 (Edge OTA) | TDL, DSR | lower, higher |
| S3 (Resilience) | MTTD, MTTR | lower, lower |
| S4 (PQC) | TTV, VSR, FDR | lower, higher, higher |
| S5 (Explainability) | AL, ACR | lower, higher |
| SS1 (Policy Audit) | CFR, FDR | lower, higher |
| SS2 (Adaptive Threat) | MTTD, AL, ACR | lower, lower, higher |

## Statistical Methods

- **Mann-Whitney U test** (non-parametric, two-sided) — α = 0.05
- **Cohen's d** effect size — small (0.2), medium (0.5), large (0.8)
- **Bootstrap 95% CI** for mean difference (10,000 resamples)
- Minimum 10 samples per variant for statistical validity

## Usage

```bash
# Full evaluation (all scenarios)
python -m evaluation.scripts.run_experiment --all --project $GCP_PROJECT_ID -v

# Specific scenarios
python -m evaluation.scripts.run_experiment --scenarios s1 s3 --project $GCP_PROJECT_ID

# With time window
python -m evaluation.scripts.run_experiment --all --start 2025-01-01 --end 2025-06-30

# Skip chart generation
python -m evaluation.scripts.run_experiment --all --skip-charts
```

## Output

Results are written to `evaluation/results/`:
- `raw/metrics_<timestamp>.csv` — collected metric samples
- `analysis/comparison_<timestamp>.csv` — statistical comparison results
- `analysis/summary_<timestamp>.json` — structured summary
- `analysis/graphs/` — thesis-quality PNG charts

## Directory Structure

```
evaluation/
├── configs/
│   ├── experiment_matrix.json   # Scenario × variant × metric matrix
│   └── thresholds.json          # Statistical significance thresholds
├── queries/                     # Parameterized BigQuery SQL
│   ├── ttd_by_variant.sql
│   ├── cfr_by_variant.sql
│   ├── mttd_by_variant.sql
│   ├── mttr_by_variant.sql
│   ├── dsr_by_variant.sql
│   ├── al_by_variant.sql
│   └── acr_by_variant.sql
├── scripts/
│   ├── collector.py             # BQ metric extraction
│   ├── compare_variants.py      # Statistical comparison engine
│   ├── visualize.py             # Chart generation (matplotlib)
│   └── run_experiment.py        # Orchestrator CLI
├── tests/                       # pytest test suite
│   ├── test_configs.py
│   ├── test_collector.py
│   ├── test_compare.py
│   ├── test_visualize.py
│   └── test_run_experiment.py
└── results/                     # .gitignored output
    ├── raw/
    └── analysis/graphs/
```

## Reproducibility

All analysis is reproducible from BigQuery data alone:
1. Queries are parameterized (no hardcoded project IDs)
2. Timestamps define exact data windows
3. Statistical methods use fixed seeds where applicable
4. Config files are version-controlled

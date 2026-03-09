---
description: "Implement 2-Axis Evaluation Framework: baseline vs runtime vs design-time vs full agent comparison across all scenarios."
agent: "evaluator"
---

# Step 7: 2-Axis Evaluation Framework

Read first:
- [Project governance](../copilot-instructions.md) (scenario-metric matrix)
- [README.md](../../README.md) (metric definitions, scenario descriptions)
- [BQ schema](../../infra/main.tf) (runs + runtime_decisions tables)

## Task

Build the evaluation framework that measures agent impact across 2 axes (design-time intelligence × runtime intelligence) for all scenarios. This is the publishable core of the thesis.

## Architecture

```
evaluation/
├── scripts/
│   ├── run_experiment.py            # Orchestrator: run one variant for one scenario
│   ├── run_baseline.py              # Run scenarios S1-SS2 without any agent
│   ├── run_runtime.py               # Run with runtime agent only (shadow → enforce)
│   ├── run_design.py                # Run with design-time agent proposals applied
│   ├── run_full.py                  # Run with both agents combined
│   └── compare_variants.py          # Statistical comparison: Δmetrics across variants
├── queries/
│   ├── ttd_by_variant.sql           # S1: TTD per variant
│   ├── cfr_by_variant.sql           # S1: CFR per variant
│   ├── mttd_by_variant.sql          # S3/SS2: MTTD per variant
│   ├── mttr_by_variant.sql          # S3: MTTR per variant
│   ├── dsr_by_variant.sql           # S2: DSR per variant
│   ├── al_by_variant.sql            # S5/SS2: AL per variant
│   └── acr_by_variant.sql           # S5/SS1/SS2: ACR per variant
├── configs/
│   ├── experiment_matrix.json       # Define which variants × scenarios to run
│   └── thresholds.json              # Significance thresholds per metric
├── results/                         # Generated — not committed
│   ├── raw/                         # BQ query results (CSV)
│   └── analysis/                    # Statistical comparisons, graphs
└── README.md                        # How to run evaluation
```

## Evaluation Matrix

### Variants per Scenario
| Scenario | Baseline | Design-Time | Runtime | Full |
|----------|----------|-------------|---------|------|
| S1 | ✅ | ✅ S1'_design | ✅ S1'_runtime | ✅ S1'_full |
| S2 | ✅ | Optional | ✅ S2'_runtime | Optional |
| S3 | ✅ | ✅ S3'_design | ✅ S3'_runtime | ✅ S3'_full |
| S4 | ✅ | ✅ S4'_design | — | ✅ S4'_full |
| S5 | ✅ | ✅ S5'_design | ✅ S5'_runtime | ✅ S5'_full |
| SS1 | ✅ | ✅ SS1'_design | — | ✅ SS1'_full |
| SS2 | ✅ | — | ✅ SS2'_runtime | ✅ SS2'_full |

### Recommended Focus (Excellence without Chaos)
Full dual-model (all 4 variants): **S1, S3, S5**
Design-only: **SS1, S4**
Runtime-only: **S2, SS2**

## Implementation

### 1. Experiment Runner (`run_experiment.py`)
```python
def run_experiment(scenario: str, variant: str, runs: int = 10):
    """Run N iterations of a scenario under a specific variant."""
    # 1. Configure agent mode (none / runtime / design / full)
    # 2. Trigger scenario workflow (GHA dispatch or local)
    # 3. Wait for completion
    # 4. Query BQ for metrics
    # 5. Store results
```

### 2. Comparison Script (`compare_variants.py`)
For each metric per scenario:
- Compute: mean, median, stddev, p5, p95 per variant
- Delta: Δmetric = variant_mean - baseline_mean
- Statistical significance: Mann-Whitney U test (non-parametric)
- Effect size: Cohen's d
- Output: comparison table + graph data

### 3. BQ Queries
Parameterized SQL that filters by variant label:
```sql
SELECT
    AVG(duration_sec) as mean_ttd,
    STDDEV(duration_sec) as stddev_ttd,
    COUNTIF(status = 'failure') / COUNT(*) as cfr
FROM `agent_metrics.runs`
WHERE scenario_id = @scenario
  AND JSON_VALUE(labels, '$.variant') = @variant
  AND t_end BETWEEN @start AND @end
```

### 4. ADK Evaluation (Optional)
Use ADK built-in eval framework:
```python
eval_dataset = [
    {"input": "S3 anomaly, severity 0.9", "expected_tool": "trigger_rollback"},
    {"input": "S1 normal, severity 0.1", "expected_tool": "no_action"},
    ...
]
```
Measures: tool selection accuracy, latency, fallback rate.

## Output Format
```
evaluation/results/analysis/
├── s1_comparison.csv              # Variant × metric table
├── s3_comparison.csv
├── summary_table.csv              # All scenarios × all metrics
├── graphs/
│   ├── s1_ttd_boxplot.png
│   ├── s3_mttd_improvement.png
│   └── overall_radar.png
└── statistical_tests.csv          # p-values, effect sizes
```

## Constraints
- Minimum 10 runs per variant per scenario for statistical validity
- Label every BQ row with `variant` in labels JSON
- Never mix agent modes within a single evaluation run
- Baseline runs must be recent (same infrastructure version as agent runs)
- All data reproducible from BQ queries

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - 2-Axis Evaluation Framework description
   - Variant definitions (baseline / runtime / design / full)
   - How to run evaluation + interpret results
2. Update `README.md` § "📊 Implementation Progress" — mark Step 7 as ✅
3. Update `docs/ai-design-architecture.md` § 10 (Roadmap) — mark all steps complete
4. Create `evaluation/README.md` with evaluation methodology and usage

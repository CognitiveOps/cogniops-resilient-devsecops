# CogniOps Evaluation Plan — Complete Scenario Coverage

> Updated: 2026-04-11 09:00 UTC
> Branch: `design_time_agent_dev`
> Thesis: "Autonomous Cognitive AI Agent for Resilient DevSecOps Environments"

---

## Evaluation Architecture

The 2-Axis Evaluation Model tests two independent axes:
- **X-axis (Design-Time Intelligence):** Structural improvements proposed by the design agent
- **Y-axis (Runtime Intelligence):** Operational decisions made by the runtime agent

Four variants per scenario:
| Variant | Design Agent | Runtime Agent |
|---------|:-----------:|:------------:|
| `baseline` | ✗ | ✗ |
| `design_only` | ✓ | ✗ |
| `runtime_only` | ✗ | ✓ |
| `full` | ✓ | ✓ |

---

## Scenario Classification — Full 2-Axis Evaluation

All 7 scenarios now have **separate workflow files per variant** with real behavioral
differences.  Design proposals are fetched **dynamically at runtime** from the
design-agent `GET /proposals/active?scenario=…` endpoint (NO hardcoded values).
If the design-agent is unreachable, workflows fall back to baseline defaults (NO_OP-safe).

### Design-Agent Integration Pattern

Every design variant workflow includes:
```yaml
- name: Fetch design-agent proposal
  run: |
    curl -s "${DESIGN_AGENT_URL}/proposals/active?scenario=${SCENARIO}" \
      -o /tmp/design_proposal.json
    python3 -c "<parse params → GITHUB_ENV>"
```

### Scenario × Variant Matrix

| Scenario | Metrics | Design Params (from agent) | Runtime Gate | Workflow Files |
|----------|---------|---------------------------|--------------|----------------|
| **S1** (CI/CD) | TTD, CFR, DF | `S1_HEALTH_RETRIES`, `S1_HEALTH_INTERVAL_SEC` | Deploy gate (`/decide`) | `s1_ci*.yml` (4) |
| **S2** (Edge OTA) | TDL, DSR, TTD_edge | `S2_ACTIVATION_TIMEOUT_SEC`, `S2_PLATFORM` | Activation gate (`/decide`) | `s2_edge*.yml` (4) |
| **S3 Cloud** (Resilience) | MTTD, MTTR | `S3_DETECT_POLL_SEC`, `S3_RECOVER_POLL_SEC` | Anomaly detection + `/decide` | `s3_rollback*.yml` (4) |
| **S3 Edge** (Resilience) | MTTD, MTTR | `S3_DETECT_POLL_SEC`, `S3_RECOVER_POLL_SEC` | Anomaly detection + `/decide` | `s3_edge_rollback*.yml` (4) |
| **S4** (PQC) | TTV, VSR, FDR | `S4_PQC_ALG`, `S4_REPLAY_CUTOFF_SEC` | Crypto quality gate (`/decide`) | `s4_pqc*.yml` (4) |
| **S5** (Explainability) | AL, ACR | `S5_APPROVAL_DELAY_SEC` | Conditional delay skip on NO_OP | `s5_explainability*.yml` (4) |
| **SS1** (Policy Audit) | CFR, FDR | `SS1_HEALTH_RETRIES`, `SS1_HEALTH_INTERVAL_SEC` | Policy overlay (`/decide` after OPA) | `ss1_ci*.yml` (4) |
| **SS2** (Adaptive Threat) | MTTD, AL, ACR | `SS2_AUTO_APPROVE_DELAY_SEC`, `SS2_DETECT_POLL_SEC` | Agent threat decision + HITL | `ss2_*.yml` (4) |

**Total:** 32 workflow files (8 sub-scenarios × 4 variants).

> **Note:** S3 has two deployment targets — Cloud Run (`s3_rollback*.yml`, stages
> `s3_detect`/`s3_recover`) and Edge Docker container (`s3_edge_rollback*.yml`,
> stages `s3_detect_edge`/`s3_recover_edge`).  Both share the same design params
> (`S3_DETECT_POLL_SEC`, `S3_RECOVER_POLL_SEC`) from the `s3` proposal.

**Statistical method:** Mann-Whitney U test + Cohen's d effect size, temporal overlap filtering.

---

## Current Data Inventory (BigQuery `agent_metrics.runs`)

### Usable Runs (as of 2026-04-13, advisory-era filter applied)

Counting rules:
- **baseline:** All variant-labeled runs count
- **design_only:** Only runs from **dynamic** workflows count (≥2026-04-11).
  Old hardcoded design_only runs (S1 31, S4 9, SS1 38) are excluded —
  params were baked into YAML, not fetched from design-agent.
- **runtime_only / full:** Only runs from **dynamic** variant workflows count (≥2026-04-11).
  Shadow-era runs (before 04-06) excluded — agent in shadow mode.
  Advisory-era manual tests (S1 2, SS1 1 from 04-06) excluded —
  used old hardcoded workflows, not the new dynamic variant files.

| Scenario | baseline | design_only | runtime_only | full | Status |
|----------|:--------:|:-----------:|:------------:|:----:|--------|
| **S1** | 21 | 4 | 6 | 5 | 🔄 Batch 3 queued (30 pairs) |
| **S2** | 20 | 3 | 2 | 4 | 🔄 Batch 3 queued (30 pairs) |
| **S3 Cloud** | 118 | 109 | 46 | 46 | ✅ Evaluated |
| **S3 Edge** | 0 | 1 | 1 | 2 | 🔄 Batch 3 queued (30 pairs) |
| **S4** | 18 | 3 | 5 | 4 | 🔄 Batch 3 queued (30 pairs) |
| **S5** | 99 | 115 | 63 | 63 | ✅ Evaluated |
| **SS1** | 17 | 5 | 4 | 5 | 🔄 Batch 3 queued (30 pairs) |
| **SS2** | 85 | 53 | 42 | 45 | ✅ Evaluated |

> **Discarded runs** (exist in BQ but excluded from evaluation):
> - **Shadow-era runtime/full** (before 04-06): S3 Cloud 45+78, S5 39+71, SS2 43+60
> - **Hardcoded design params** (before 04-11): S1 31d, S4 9d, SS1 38d
> - **Hardcoded runtime/full** (before 04-11): S1 32r/32f, S2 21r, S4 20f, SS1 60f
> - **Manual advisory tests** (04-06, old workflows): S1 2r, SS1 1r
> - **S3 Edge legacy:** 3 runtime (shadow, no matching variants)
>
> Exclusion criteria:
> 1. **Design axis:** params hardcoded in workflows, not fetched from design-agent
> 2. **Runtime axis:** old workflow (no `/decide` gate) or shadow mode
> 3. **Cutover date:** Dynamic variant workflows deployed 2026-04-11 (commit `b00c728`)

### Unlabeled Legacy Runs (`variant=NULL`)

| Scenario | n | Date Range |
|----------|:--:|:-----------|
| S1 | 98 | Oct 2025 → Mar 2026 |
| S2 | 56 | — |
| S3 Cloud | 48 | — |
| S3 Edge | 3 | — |
| S4 | 29 | — |
| S5 | 34 | Jan → Mar 2026 |
| SS1 | 152 | Dec 2025 → Mar 2026 |
| SS2 | 37 | Feb → Mar 2026 |

Legacy runs lack `variant` label and predate the 2-axis evaluation framework.

### Queue Status

**~670 runs queued** on GitHub Actions (self-hosted runner `cogniops-fresh`):
- Batch 3 (2026-04-13): 600 runs (30 pairs × 5 scenarios × 4 variants)
- Remaining from previous batches: ~73 runs
- **Root cause of previous failures fixed:** `cancel-in-progress: true` was
  causing mass cancellations (407/426 runs cancelled in Batches 1-2).
  Fixed to `cancel-in-progress: false` on all 32 workflows (commit `312c4dd`,
  cherry-picked to `main` as `db4bb50`).

Runner `cogniops-fresh` is **online and busy**, processing sequentially.

---

## Required Actions

### Phase 1: Drain Existing Queue ✅ DONE
- **227 runs** queued (S3/S5/SS2 paired + S1/S2/S4/SS1 baselines)
- Runner `cogniops-fresh` active and processing
- Monitor: `tail -f /tmp/runner1.log`

### Phase 2: Commit + Push New Workflow Files ✅ DONE
Pushed to `design_time_agent_dev` (commit `b00c728`) and cherry-picked to `main` (commit `2905353`):
- 15 new variant workflows for S1/S2/S4/SS1/S3-Edge
- 3 refactored design workflows (S3 Cloud, S5, SS2)
- Design-agent `GET /proposals/active` endpoint
- Seed proposals script, dispatch scripts, EVALUATION_PLAN.md

### Phase 3: Seed Design Proposals to GCS ✅ DONE
7 proposals seeded to `gs://cogent-wall-445012-h5-agent-artifacts/proposals/design/active/`.
```bash
export GOOGLE_APPLICATION_CREDENTIALS=$PWD/key.json
python scripts/seed_design_proposals.py --bucket $AGENT_ARTIFACTS_BUCKET
```

Proposal params per scenario (see `scripts/seed_design_proposals.py`):
| Scenario | Param | Baseline | Proposed |
|----------|-------|:--------:|:--------:|
| S1 | `S1_HEALTH_RETRIES` | 6 | 3 |
| S1 | `S1_HEALTH_INTERVAL_SEC` | 10 | 5 |
| S2 | `S2_ACTIVATION_TIMEOUT_SEC` | 300 | 120 |
| S3 | `S3_DETECT_POLL_SEC` | 5 | 1 |
| S3 | `S3_RECOVER_POLL_SEC` | 5 | 1 |
| S4 | `S4_PQC_ALG` | Dilithium2 | Dilithium2 |
| S4 | `S4_REPLAY_CUTOFF_SEC` | 900 | 600 |
| S5 | `S5_APPROVAL_DELAY_SEC` | 10 | 5 |
| SS1 | `SS1_HEALTH_RETRIES` | 6 | 3 |
| SS1 | `SS1_HEALTH_INTERVAL_SEC` | 10 | 5 |
| SS2 | `SS2_AUTO_APPROVE_DELAY_SEC` | 15 | 8 |
| SS2 | `SS2_DETECT_POLL_SEC` | 2 | 1 |

### Phase 4: Deploy Updated Design Agent ✅ DONE
Design-agent redeployed to Cloud Run (revision `design-agent-00010-pg9`).
- Image: `europe-docker.pkg.dev/cogent-wall-445012-h5/apps/design-agent:latest`
- URL: `https://design-agent-kauyrrwc3a-ew.a.run.app`
- GitHub variable `DESIGN_AGENT_URL` set for workflow access

### Phase 5: Dispatch Variant Runs for S1/S2/S3-Edge/S4/SS1 ✅ DONE
~1215 runs dispatched total (three batches):
- **Batch 1** (2026-04-11): 300 runs (15 pairs × 5 scenarios × 4 variants)
  - Validation batch: 3 pairs (60 runs) — confirmed all workflows trigger
  - Full batch: 12 pairs (240 runs) — 240/240 dispatched, 0 failures
  - S3 Edge baseline fix: added `run_suffix` input to `s3_edge_rollback.yml`
  - ⚠️ **Most runs cancelled** due to `cancel-in-progress: true` (see below)
- **Batch 2** (2026-04-12): 315 runs to fill treatment variant gaps
  - 300 runs: 15 pairs × 5 scenarios × 4 variants + 15 extra S3 Edge baselines
  - ⚠️ **Most runs cancelled** — same `cancel-in-progress` issue
- **⚠️ Cancellation root cause:** `cancel-in-progress: true` in concurrency groups
  caused 407 of 426 completed runs to be cancelled despite unique `run_suffix`.
  GitHub Actions expression `${{ (inputs.run_suffix || '') != '' && format(...) }}`
  in the `concurrency.group` context did not resolve correctly for queued runs.
- **Fix:** `cancel-in-progress: false` on all 32 workflows (commit `312c4dd`).
  Cherry-picked to `main` (`db4bb50`).
- **Batch 3** (2026-04-13): 600 runs (30 pairs × 5 scenarios × 4 variants)
  - 599/600 dispatched + 1 retried = 600 total
  - With `cancel-in-progress: false`, runs should complete without cancellation

### Phase 6: Run Evaluation Pipeline ✅ PARTIAL (3/8 scenarios)
First pass completed for **S3 Cloud, S5, SS2** (the 3 scenarios with ≥30 runs per variant).
Remaining 5 scenarios (S1, S2, S3 Edge, S4, SS1) still queued.

**Results summary (21 comparisons, 3908 metric samples):**

| Scenario | Metric | Variant | Δ% | p-value | Cohen's d | Effect | Improved |
|----------|--------|---------|---:|--------:|----------:|--------|----------|
| S3 Cloud | MTTD | design_only | -8.9% | 0.001 | -0.11 | negligible | ✅ |
| S3 Cloud | MTTD | **runtime_only** | **-65.8%** | <0.001 | **-0.96** | **large** | ✅ |
| S3 Cloud | MTTD | **full** | **-67.3%** | <0.001 | **-0.98** | **large** | ✅ |
| S3 Cloud | MTTR | design_only | -9.2% | 0.002 | -0.12 | negligible | ✅ |
| S3 Cloud | MTTR | **runtime_only** | **-31.4%** | 0.002 | **-0.46** | **small** | ✅ |
| S3 Cloud | MTTR | **full** | **-37.4%** | <0.001 | **-0.55** | **medium** | ✅ |
| S5 | AL | design_only | +6.5% | 0.54 | 0.03 | negligible | ❌ |
| S5 | AL | runtime_only | +282% | <0.001 | 1.07 | large | ❌ ↑worse |
| S5 | AL | full | +287% | <0.001 | 1.17 | large | ❌ ↑worse |
| S5 | ACR | all variants | 0% | 1.0 | 0.00 | — | — ceiling |
| SS2 | AL | **design_only** | **-25.7%** | <0.001 | **-1.48** | **large** | ✅ |
| SS2 | AL | runtime_only | -10.3% | 0.031 | -0.64 | medium | ✅ |
| SS2 | AL | full | -7.3% | 0.106 | -0.42 | small | — |
| SS2 | MTTD | all variants | <±7% | >0.1 | <0.25 | negligible | — |
| SS2 | ACR | all variants | 0% | 1.0 | 0.00 | — | — ceiling |

**Key findings:**
1. **S3 Cloud:** Both axes work. Runtime agent dominates MTTD (-66%, large effect).
   Design agent provides modest but significant structural improvement (-9%).
   Combined (full) marginally better than runtime_only.
2. **S5:** Runtime agent **increases** AL (+282%) — the `/decide` gate adds latency.
   This is an expected trade-off: explainability + cognitive oversight costs time.
   ACR at 100% ceiling across all variants (no room for improvement).
3. **SS2:** Design agent is the star — AL -26% (large effect, d=-1.48).
   Runtime agent provides modest AL reduction (-10%). Combination is not additive.
   MTTD shows no significant change. ACR at ceiling.

**Artifacts:** [summary](evaluation/results/analysis/summary_20260411T202005Z.json),
[comparison CSV](evaluation/results/analysis/comparison_20260411T202005Z.csv),
[raw metrics](evaluation/results/raw/metrics_20260411T202005Z.csv)

**Re-run for all 8 scenarios** after queue drains:
```bash
source 3_12_7_venv/bin/activate
python -m evaluation.scripts.run_experiment \
  --scenarios s1 s2 s3_cloud s3_edge s4 s5 ss1 ss2 \
  --causal-mode -v
```

---

## Expected Evaluation Output

### Full 2-Axis Comparative Analysis (all 7 scenarios)
- **n comparisons:** 7 scenarios × ~2 metrics × 3 treatments = **~42 comparisons**
- **Per comparison:** p-value, Cohen's d, 95% CI, Δ%, direction
- **Charts:** Effect size heatmap, per-metric bar charts, 2-axis quadrant plot
- **Key thesis question:** Does the cognitive layer (design + runtime) improve
  each DevSecOps metric compared to the deterministic baseline?

### Runtime Decision Quality Analysis
- **n decisions:** 654 total
  - Shadow mode: 206 (177 NO_OP + 29 ESCALATE)
  - Advisory mode: 448 (10 NO_OP + 438 ESCALATE)
- 0 decisions executed (`decision_executed=false` for all)
- **Analysis:** Decision distribution, rationale quality, mode progression
  (shadow 03-30→04-06, advisory 04-06→present)

---

## Run Tracking Checklist

| Phase | Scenario | Variant | Target | Current | Gap | Status |
|-------|----------|---------|:------:|:-------:|:---:|--------|
| 1 | S3 Cloud | baseline | ≥30 | 118 | — | ✅ Evaluated |
| 1 | S3 Cloud | design_only | ≥30 | 107 | — | ✅ Evaluated |
| 1 | S3 Cloud | runtime_only | ≥30 | 43 | — | ✅ Evaluated |
| 1 | S3 Cloud | full | ≥30 | 40 | — | ✅ Evaluated |
| 1 | S5 | baseline | ≥30 | 98 | — | ✅ Evaluated |
| 1 | S5 | design_only | ≥30 | 115 | — | ✅ Evaluated |
| 1 | S5 | runtime_only | ≥30 | 63 | — | ✅ Evaluated |
| 1 | S5 | full | ≥30 | 63 | — | ✅ Evaluated |
| 1 | SS2 | baseline | ≥30 | 84 | — | ✅ Evaluated |
| 1 | SS2 | design_only | ≥30 | 52 | — | ✅ Evaluated |
| 1 | SS2 | runtime_only | ≥30 | 42 | — | ✅ Evaluated |
| 1 | SS2 | full | ≥30 | 43 | — | ✅ Evaluated |
| 5 | S1 | baseline | ≥30 | 21 | 9 | 🔄 Batch 3: +30 pairs queued |
| 5 | S1 | design_only | ≥30 | 4 | 26 | 🔄 Batch 3: +30 pairs queued |
| 5 | S1 | runtime_only | ≥30 | 6 | 24 | 🔄 Batch 3: +30 pairs queued |
| 5 | S1 | full | ≥30 | 5 | 25 | 🔄 Batch 3: +30 pairs queued |
| 5 | S2 | baseline | ≥30 | 20 | 10 | 🔄 Batch 3: +30 pairs queued |
| 5 | S2 | design_only | ≥30 | 3 | 27 | 🔄 Batch 3: +30 pairs queued |
| 5 | S2 | runtime_only | ≥30 | 2 | 28 | 🔄 Batch 3: +30 pairs queued |
| 5 | S2 | full | ≥30 | 4 | 26 | 🔄 Batch 3: +30 pairs queued |
| 5 | S3 Edge | baseline | ≥30 | 0 | 30 | 🔄 Batch 3: +30 pairs queued |
| 5 | S3 Edge | design_only | ≥30 | 1 | 29 | 🔄 Batch 3: +30 pairs queued |
| 5 | S3 Edge | runtime_only | ≥30 | 1 | 29 | 🔄 Batch 3: +30 pairs queued |
| 5 | S3 Edge | full | ≥30 | 2 | 28 | 🔄 Batch 3: +30 pairs queued |
| 5 | S4 | baseline | ≥30 | 18 | 12 | 🔄 Batch 3: +30 pairs queued |
| 5 | S4 | design_only | ≥30 | 3 | 27 | 🔄 Batch 3: +30 pairs queued |
| 5 | S4 | runtime_only | ≥30 | 5 | 25 | 🔄 Batch 3: +30 pairs queued |
| 5 | S4 | full | ≥30 | 4 | 26 | 🔄 Batch 3: +30 pairs queued |
| 5 | SS1 | baseline | ≥30 | 17 | 13 | 🔄 Batch 3: +30 pairs queued |
| 5 | SS1 | design_only | ≥30 | 5 | 25 | 🔄 Batch 3: +30 pairs queued |
| 5 | SS1 | runtime_only | ≥30 | 4 | 26 | 🔄 Batch 3: +30 pairs queued |
| 5 | SS1 | full | ≥30 | 5 | 25 | 🔄 Batch 3: +30 pairs queued |

> **Counting rules:** S1/S2/S4/SS1 treatment variants (design_only, runtime_only, full)
> only count runs from dynamic workflows (≥2026-04-11). Old hardcoded runs excluded.
> Queue: ~670 runs on `cogniops-fresh` (Batch 3 = 600 + ~73 leftovers).
> **Batch 3 dispatched 2026-04-13:** 600 runs (30 pairs × 5 scenarios × 4 variants).
> **Fix applied:** `cancel-in-progress: false` prevents cancellation (commit `312c4dd`).

---

## Notes

- **Runtime agent mode:** shadow (03-30→04-06) → advisory (04-06→present).
  All 654 decisions have `decision_executed=false` (executor is Phase 0 stub).
  **Enforce is out of scope** — it would require real BLOCK/ROLLBACK execution
  which modifies the deterministic baseline (IMMUTABLE). Advisory suffices for
  the 2-axis evaluation: the runtime-axis measures detection speed (MTTD) and
  decision quality (accuracy, rationale), not execution. Enforce → future work.
- **Design agent integration:** Now **dynamic** — design workflows fetch proposals
  from `GET /proposals/active?scenario=…` at runtime. Proposals seeded to GCS via
  `scripts/seed_design_proposals.py`. Old runs (⚠) used hardcoded values.
  **Why seed instead of autonomous generation?** The design agent already has a
  full autonomous pipeline (`POST /run` → Context Builder → Gemini LlmAgent →
  Proposal Generator → Validator → GCS + GitHub Issue). However, for the
  evaluation we seed proposals because: (a) most scenarios lack sufficient
  baseline data for the context builder to produce meaningful analysis,
  (b) seeded proposals guarantee identical treatment across all paired runs
  (LLM non-determinism would be a confounding variable), and (c) the weekly
  Cloud Scheduler cadence is too slow for the evaluation timeline.
  Full autonomous proposal generation → future work (post-evaluation).
- **Temporal overlap:** Evaluation uses `_filter_to_overlap_windows()` to ensure
  baseline and treatment runs occurred in the same time period.
- **S3 stages:** S3 has no `s3_final`; use `s3_detect`/`s3_recover` for run counting.
  Each run_id produces one row per fault mode (6 fault modes per matrix).
- **S4 stages:** S4 has no `s4_final`; use `s4_p0_valid` through `s4_p3_replay`.
  4 sub-scenarios per run.
- **S2 stages:** S2 has `s2_activate` and `s2_ttd_edge`; no `_final` stage.
- **SS2 stages:** SS2 uses `ss2_detect`; its final metrics go through `s5_final`.
- **Legacy runs:** 454 unlabeled runs (`variant=NULL`) exist across all scenarios.
  These predate the 2-axis framework and are excluded from evaluation.
- **New workflow files (not yet pushed):**
  12 new variant workflows for S1/S2/S4/SS1, 3 refactored design workflows
  for S3/S5/SS2, updated dispatch script, seed proposals script.

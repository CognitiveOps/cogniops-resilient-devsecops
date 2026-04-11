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

### Usable Runs (as of 2026-04-11, advisory-era filter applied)

Counting rules:
- **baseline / design_only:** All runs count (runtime agent not involved)
- **runtime_only / full:** Only runs after 2026-04-06 count (advisory mode).
  Shadow-era runs (before 04-06) are excluded — agent logged decisions but did
  not notify, so runtime behavior was indistinguishable from baseline.

| Scenario | baseline | design_only | runtime_only | full | Status |
|----------|:--------:|:-----------:|:------------:|:----:|--------|
| **S1** | 1 | 0 | 0 | 0 | ❌ Needs all variant runs |
| **S2** | 0 | 0 | 0 | 0 | ❌ Needs all variant runs |
| **S3 Cloud** | 112 | 100 | 41 | 33 | ✅ Sufficient (≥30 each) |
| **S3 Edge** | 0 | 0 | 0 | 0 | ❌ Needs all variant runs |
| **S4** | 0 | 0 | 0 | 0 | ❌ Needs all variant runs |
| **S5** | 65 | 61 | 18 | 16 | ⚠ runtime_only/full below 30 |
| **SS1** | 0 | 0 | 0 | 0 | ❌ Needs all variant runs |
| **SS2** | 77 | 46 | 33 | 38 | ✅ Sufficient (≥30 each) |

> **Discarded runs** (exist in BQ but excluded from evaluation):
> - **Shadow-era runtime/full** (before 04-06): S3 Cloud 45+78, S5 39+71, SS2 43+60
> - **Hardcoded design params:** S1 31d/32r/32f, S2 21r, S4 9d/20f, SS1 38d/60f
> - **S3 Edge legacy:** 3 runtime (shadow, no matching variants)
>
> Exclusion criteria:
> 1. **Design axis:** params hardcoded in workflows, not fetched from design-agent
> 2. **Runtime axis:** agent in shadow mode (decisions logged only, not advisory)

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

**227 runs queued** on GitHub Actions (self-hosted runner `cogniops-fresh`):
- S3 Cloud baseline/design/runtime/full: ~55 runs (15 paired)
- S3 Edge: 6 runs total (very sparse, needs paired dispatch)
- S5 baseline/design/runtime/full: ~56 runs (14 paired)
- SS2 baseline/design/runtime/full: ~56 runs (14 paired)
- S1/S2/S4/SS1 baseline: 60 runs (15 each, Tier 2 dispatch)

Runner is active and processing sequentially.

---

## Required Actions

### Phase 1: Drain Existing Queue ✅ IN PROGRESS
- **227 runs** queued (S3/S5/SS2 paired + S1/S2/S4/SS1 baselines)
- Runner `cogniops-fresh` active and processing
- Monitor: `tail -f /tmp/runner1.log`

### Phase 2: Commit + Push New Workflow Files ⏳ NEXT
New variant workflows created but **not yet pushed** to `design_time_agent_dev`:
- `s1_ci_design.yml`, `s1_ci_runtime.yml`, `s1_ci_full.yml`
- `s2_edge_design.yml`, `s2_edge_runtime.yml`, `s2_edge_full.yml`
- `s4_pqc_design.yml`, `s4_pqc_runtime.yml`, `s4_pqc_full.yml`
- `ss1_ci_design.yml`, `ss1_ci_runtime.yml`, `ss1_ci_full.yml`
- Refactored: `s3_rollback_design.yml`, `s5_explainability_design.yml`, `ss2_design.yml`
- NEW: `s3_edge_rollback_design.yml`, `s3_edge_rollback_runtime.yml`, `s3_edge_rollback_full.yml`

```bash
git add .github/workflows/ scripts/ evaluation/ design-agent/main.py
git commit -m "feat(eval): add dynamic design-agent integration for all 7 scenarios"
git push origin design_time_agent_dev
```

### Phase 3: Seed Design Proposals to GCS ⏳ PENDING
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

### Phase 4: Deploy Updated Design Agent ⏳ PENDING
Rebuild & deploy design-agent to Cloud Run with new `GET /proposals/active` endpoint.
```bash
cd design-agent
gcloud builds submit --tag gcr.io/$PROJECT_ID/design-agent .
gcloud run deploy design-agent --image gcr.io/$PROJECT_ID/design-agent --region $REGION
```

### Phase 5: Dispatch Variant Runs for S1/S2/S4/SS1 ⏳ PENDING
After Phases 2–4 complete. S3 Cloud/S5/SS2 already have data; S3 Edge needs runs.
```bash
# 15 paired runs for new scenarios × 4 variants = 300 runs
./scripts/dispatch_paired_runs.sh \
  --pairs 15 \
  --scenarios s1,s2,s3_edge,s4,ss1 \
  --branch design_time_agent_dev
```

For a quick validation first:
```bash
# 3 pairs to validate workflows work
./scripts/dispatch_paired_runs.sh \
  --pairs 3 \
  --scenarios s1,s2,s3_edge,s4,ss1 \
  --branch design_time_agent_dev
```

### Phase 6: Run Evaluation Pipeline ⏳ PENDING
After all runs complete:
```bash
source 3_12_7_venv/bin/activate
# Full 2-axis evaluation across ALL scenarios
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
| 1 | S3 Cloud | baseline | ≥30 | 112 | — | ✅ Done |
| 1 | S3 Cloud | design_only | ≥30 | 100 | — | ✅ Done |
| 1 | S3 Cloud | runtime_only | ≥30 | 41 | — | ✅ Done (advisory only) |
| 1 | S3 Cloud | full | ≥30 | 33 | — | ✅ Done (advisory only) |
| 1 | S5 | baseline | ≥30 | 65 | — | ✅ Done |
| 1 | S5 | design_only | ≥30 | 61 | — | ✅ Done |
| 1 | S5 | runtime_only | ≥30 | 18 | 12 | ⚠ Below target (advisory only) |
| 1 | S5 | full | ≥30 | 16 | 14 | ⚠ Below target (advisory only) |
| 1 | SS2 | baseline | ≥30 | 77 | — | ✅ Done |
| 1 | SS2 | design_only | ≥30 | 46 | — | ✅ Done |
| 1 | SS2 | runtime_only | ≥30 | 33 | — | ✅ Done (advisory only) |
| 1 | SS2 | full | ≥30 | 38 | — | ✅ Done (advisory only) |
| 1+ | S3,S5,SS2 | all ×15 | +167 | — | 167 | 🔄 Queued (227 total in queue) |
| 2 | S1 | baseline | 15 | 1 | 14 | 🔄 Queued (15 dispatched) |
| 2 | S2 | baseline | 15 | 0 | 15 | 🔄 Queued (15 dispatched) |
| 2 | S4 | baseline | 15 | 0 | 15 | 🔄 Queued (15 dispatched) |
| 2 | SS1 | baseline | 15 | 0 | 15 | 🔄 Queued (15 dispatched) |
| 5 | S1 | all ×15 | 60 | 0 | 60 | ⏳ Pending (workflows created, not pushed) |
| 5 | S2 | all ×15 | 60 | 0 | 60 | ⏳ Pending (workflows created, not pushed) |
| 5 | S3 Edge | all ×15 | 60 | 0 | 60 | ⏳ Pending (workflows created, not pushed) |
| 5 | S4 | all ×15 | 60 | 0 | 60 | ⏳ Pending (workflows created, not pushed) |
| 5 | SS1 | all ×15 | 60 | 0 | 60 | ⏳ Pending (workflows created, not pushed) |

> **Note:** "advisory only" = shadow-era runtime_only/full runs excluded.
> The 227 queued runs (all advisory era) will boost S5 runtime_only/full past ≥30.

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

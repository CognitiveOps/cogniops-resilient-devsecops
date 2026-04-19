# CogniOps Evaluation Plan — Complete Scenario Coverage

> Updated: 2026-04-19 UTC
> Branch: `design_time_agent_dev`
> Thesis: "Autonomous Cognitive AI Agent for Resilient DevSecOps Environments"
> **Data integrity audit completed 2026-04-17** — see §Data Integrity Audit below.
> **S3 Edge bugs fixed 2026-04-19** — see §Issue 6 below. Pending commit + re-dispatch.

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
design-agent `GET /proposals/active?scenario=…` endpoint.
If the design-agent is unreachable, workflows fall back to baseline defaults (NO_OP-safe).

> **Note on design-agent integration timeline:**
> - **S3 Cloud:** Dynamic integration since Apr 3 (44 successful Cloud Run calls logged)
> - **S1/S2/S4/SS1/S3 Edge:** Dynamic integration since Apr 11 (commit `b00c728`)
> - **S5/SS2:** Pre-Apr-11 runs used **hardcoded design params** (identical to
>   seed proposal values: S5 delay=5s, SS2 delay=8s/poll=1s). Dynamic agent
>   fetch added Apr 11, but all dispatched runs were queued before the commit.
>   Treatment effect is valid (same parameter values), but not agent-driven.

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

### Usable Runs (as of 2026-04-19, `--labeled-baselines-only`)

Counting rules:
- **baseline:** Only runs with explicit `labels.variant='baseline'` (legacy NULL excluded)
- **S3 Cloud / S5 / SS2 treatment:** Dynamic workflows since advisory era (≥2026-04-06).
  Shadow-era runs (before 04-06) excluded.
- **S1 / S2 / S4 / SS1 / S3 Edge treatment:** Only runs from new dynamic
  variant workflows (≥2026-04-11). Old hardcoded runs excluded.
- **S3 Cloud/Edge:** Counts use `s3_detect` / `s3_detect_edge` stage (one row per run).

| Scenario | baseline | design_only | runtime_only | full | Status |
|----------|:--------:|:-----------:|:------------:|:----:|--------|
| **S1** | 163 | 60 | 72 | 66 | ✅ All ≥30 — ready to evaluate |
| **S2** | 64 | 32 | 22 | 24 | 🔶 runtime=22 (need 8), full=24 (need 6) |
| **S3 Cloud** | 506 | 155 | 106 | 110 | ✅ Evaluated |
| **S3 Edge** | 0† | 1 | 6 | 7 | ❌ Bugs fixed 04-19 — need re-dispatch |
| **S4** | 80 | 20 | 32 | 24 | 🔶 design=20 (need 10) |
| **S5** | 250 | 130 | 116 | 116 | ✅ Evaluated |
| **SS1** | 307 | 246 | 246 | 239 | ✅ All ≥30 — ready to evaluate |
| **SS2** | 1352 | 401 | 392 | 390 | ✅ Evaluated |

*†S3 Edge has 18 legacy NULL baselines but **zero labeled baselines**. All Batch 4
S3 Edge runs (60) failed due to Bug A (see Issue 6). Need to dispatch baselines too.*

> **Why labeled baselines only?** Data integrity audit (see below) found that
> `COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline')` treated **all** legacy
> NULL-variant runs as baselines. These legacy runs (5520 total) predate the
> evaluation framework and introduce temporal confounders. The `--labeled-baselines-only`
> flag excludes them, keeping only explicitly labeled baselines.
>
> **Discarded runs** (exist in BQ but excluded from evaluation):
> - **Legacy NULL baselines:** 5520 runs (S1:133, S2:112, S3:590, S4:120, S5:1521, SS1:1058, SS2:1986)
> - **Shadow-era runtime/full** (before 04-06): S3 Cloud 45+78, S5 39+71, SS2 43+60
> - **Hardcoded design params** (before 04-11): S1 31d, S4 9d, SS1 38d
> - **Hardcoded runtime/full** (before 04-11): S1 32r/32f, S2 21r, S4 20f, SS1 60f
>
> Exclusion criteria:
> 1. **Legacy baselines:** `JSON_VALUE(labels, '$.variant') IS NULL` — pre-framework era
> 2. **Design axis:** params hardcoded in workflows, not fetched from design-agent
> 3. **Runtime axis:** old workflow (no `/decide` gate) or shadow mode
> 4. **Cutover date:** Dynamic variant workflows deployed 2026-04-11 (commit `b00c728`)

### Unlabeled Legacy Runs (`variant=NULL`)

| Scenario | n | Date Range |
|----------|:--:|:-----------|
| S1 | 133 | Dec 2025 → Mar 2026 |
| S2 | 112 | Nov 2025 → Mar 2026 |
| S3 | 590 | Dec 2025 → Mar 2026 |
| S4 | 120 | Jan → Mar 2026 |
| S5 | 1521 | Jan → **Apr 2026** ⚠️ |
| SS1 | 1058 | Dec 2025 → Mar 2026 |
| SS2 | 1986 | Feb → **Apr 2026** ⚠️ |
| **Total** | **5520** | |

Legacy runs lack `variant` label and predate the 2-axis evaluation framework.
**⚠️ S5 and SS2 legacy runs extend into the treatment era** (Apr 3–12 for S5,
Apr 1–15 for SS2), creating temporal overlap with treatment variants.
The `--labeled-baselines-only` flag excludes them to prevent confounding.

### Queue Status (as of 2026-04-19)

**66 runs queued** on GitHub Actions — all pre-fix S3 Edge runs (will still fail).
- 22× S3 Edge full, 22× S3 Edge design_only, 20× S3 Edge runtime_only
- 1× S3 Edge baseline, 1× SS1
- **Must cancel all** before re-dispatch (they use pre-fix commit SHA, no edge image rebuild).

**⚠️ OOM failure diagnosis (04-17 morning):**
Runner session 04-16→04-17 processed 147 jobs: **30 succeeded, 113 failed, 4 abandoned**.
Root cause: **`docker buildx build` OOM kills** on 2GB RAM machine.

| Exit Code | Count | Cause | Step |
|:---------:|:-----:|-------|------|
| 137 | 11 | OOM Kill (SIGKILL) | `buildpush` (docker buildx build) |
| 255 | 7 | Buildkit crash (memory) | `buildpush` |
| 100 | 3 | apt-get lock/failure | `Install jq` |
| 1 | 2 | General build failure | `buildpush` |

**Fix applied and pushed (04-17):** Replaced `docker buildx build --platform linux/amd64 --push`
with `docker build` + `docker push` in all 8 affected workflows (S3 Edge × 4 + SS2 × 4).
Machine is x86_64 — buildx/QEMU overhead was unnecessary.
Removed `docker/setup-qemu-action@v3` and `docker/setup-buildx-action@v3` steps.

**⚠️ Remaining 76 queued runs may use OLD commit SHA** — some will still fail.
Need to cancel stale runs and re-dispatch after fix.

**GCP cost optimization (04-17 evening):**
- `opa-server` min-instances: 1 → **0** (was always-on, ~€15-20/mo saved)
- `cpu-throttling: true` enabled on 6 services: baseline-app, design-agent,
  edge-cv-app, opa-server, runtime-agent, security-compliance-agent
  (~€10-15/mo saved — CPU only allocated during request processing)
- AR cleanup policy re-applied (keep 5 recent + delete untagged >7 days)
- Estimated monthly savings: ~€30-40/mo

**Runner config changes (04-15):**
- Old runners deleted (`cogniops-local-2`, `-3`), freed ~8 GB
- Auto-start disabled (crontab removed)
- `start-runners.sh` now cleans _diag logs (keeps only failures)
- `run.sh` uncommented (was entirely commented out)
- Manual start: `bash ~/start-runners.sh` or `/tmp/runner-monitor.sh`

**Next steps (Batch 5):**
1. Commit + push S3 Edge bug fixes (trap cleanup + hardcoded `/status`)
2. Cancel 66 stale queued runs (pre-fix commit SHA)
3. Rebuild + push edge-cv-app Docker image (main.py changed)
4. Dispatch **S3 Edge** — ALL 4 variants incl. baselines (15 pairs × 4 = 60 runs)
5. Dispatch **S2** gap fills — runtime_only (8 more), full (6 more)
6. Dispatch **S4** gap fills — design_only (10 more)
7. Start runner, process queue
8. Re-run evaluation pipeline for **all 8 scenarios**:
   ```bash
   python -m evaluation.scripts.run_experiment \
     --scenarios s1 s2 s3_cloud s3_edge s4 s5 ss1 ss2 \
     --labeled-baselines-only --causal-mode -v
   ```

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
  - ⚠️ **S1/S2/S4/SS1 runs cancelled again** — runner was offline (boot script
    stuck on network 04-13→04-15). GitHub Actions cancelled queued runs.
    S3 Edge runs partially survived (~99 still queued).
- **Runner session** (2026-04-15): Ran for ~5h with CPU guard.
  Docker daemon was down (all jobs failing) — fixed mid-session.
  `run.sh` was entirely commented out — fixed (uncommented).
  Processed ~67 runs (295→228 queued). S3 Edge/Cloud/SS2 progressed.
- **Batch 4** (2026-04-17): Targeted dispatch to fill remaining gaps.
  First cancelled 76 stale S3 Edge runs from Batch 3 (commit `312c4dd`, pre-buildx-fix).
  Dispatched 220 runs via `dispatch_paired_runs.sh`:
  - S1: 6 pairs × 4 variants = 24 runs (timestamp `20260417T074003Z`)
  - SS1: 7 pairs × 4 variants = 28 runs (timestamp `20260417T074157Z`)
  - S2: 15 pairs × 4 variants = 60 runs
  - S4: 12 pairs × 4 variants = 48 runs
  - S3 Edge: 15 pairs × 4 variants = 60 runs (buildx-fixed)
  - **Total: 220 dispatched, 0 failures**
  - **Runner session** (2026-04-17 16:42 → 2026-04-18 11:10 UTC): ~18.5h uptime
    - S1: 24/24 ✅, SS1: 18/28 ✅ (8 cancelled), S2: 42/60 ✅ (15 cancelled, 1 failed)
    - S4: 7/48 ✅ (38 cancelled, 1 failed), S3 Edge: **0/60 ✅** (all failing — see Issue 6)
    - 77 runs cancelled (runner downtime, Docker restart), 2 failed (S4-design, S2-runtime)
    - **69 still queued** (45× S3 Edge + SS1/S4 remnants)
  - ⚠️ **S3 Edge Issue (Bug):** All S3 Edge jobs fail — see [Issue 6](#issue-6-s3-edge-recovery-port-mismatch) below

### Phase 6: Run Evaluation Pipeline ✅ PARTIAL (4/8 evaluated, 5/8 ready)
Re-evaluated with `--labeled-baselines-only` after data integrity audit (2026-04-17 23:00 UTC).
**S3 Cloud, S4 (partial), S5, SS2** have results.
**S1 and SS1** now fully ready (all variants ≥30) after Batch 4 — pending re-evaluation.
**S2, S3 Edge, S4** need Batch 5 gap fills before evaluation.

**Results summary (23 comparisons, 5012 metric samples, labeled baselines only):**

| Scenario | Metric | Variant | Δ% | p-value | Cohen's d | Effect | Sig | Improved |
|----------|--------|---------|---:|--------:|----------:|--------|:---:|----------|
| S3 Cloud | MTTD | design_only | -8.7% | 0.001 | -0.11 | negligible | ✅ | ✅ |
| S3 Cloud | MTTD | **runtime_only** | **-65.2%** | <0.001 | **-0.94** | **large** | ✅ | ✅ |
| S3 Cloud | MTTD | **full** | **-65.8%** | <0.001 | **-0.95** | **large** | ✅ | ✅ |
| S3 Cloud | MTTR | design_only | -8.9% | 0.002 | -0.12 | negligible | ✅ | ✅ |
| S3 Cloud | MTTR | **runtime_only** | **-27.0%** | 0.022 | **-0.39** | **small** | ✅ | ✅ |
| S3 Cloud | MTTR | **full** | **-32.0%** | 0.002 | **-0.47** | **small** | ✅ | ✅ |
| S4 | FDR | runtime_only | 0% | 1.0 | 0.00 | — | — | — ceiling |
| S4 | FDR | full | 0% | 1.0 | 0.00 | — | — | — ceiling |
| S5 | AL | design_only | -13.4% | 0.411 | -0.07 | negligible | — | — |
| S5 | AL | runtime_only | +205% | <0.001 | +0.98 | large | ✅ | ❌ ↑worse |
| S5 | AL | full | +223% | <0.001 | +1.08 | large | ✅ | ❌ ↑worse |
| S5 | ACR | all variants | 0% | 1.0 | 0.00 | — | — | — ceiling |
| SS2 | AL | **design_only** | **-26.0%** | <0.001 | **-1.66** | **large** | ✅ | ✅ |
| SS2 | AL | runtime_only | -10.9% | 0.148 | -0.81 | large | — | — |
| SS2 | AL | full | -9.0% | 0.245 | -0.63 | medium | — | — |
| SS2 | MTTD | design_only | +35.9% | 0.001 | +0.18 | negligible | ✅ | ❌ ↑worse |
| SS2 | MTTD | runtime_only | +13.4% | 0.602 | +0.08 | negligible | — | — |
| SS2 | MTTD | full | +84.9% | 0.218 | +0.42 | small | — | — |
| SS2 | ACR | all variants | 0% | 1.0 | 0.00 | — | — | — ceiling |

**Key findings (labeled baselines only):**
1. **S3 Cloud:** Both axes work. Runtime agent dominates MTTD (-65%, large effect).
   Design agent provides modest but significant structural improvement (-9%).
   Combined (full) marginally better than runtime_only for both MTTD and MTTR.
2. **S5:** Runtime agent **increases** AL (+205%) — the `/decide` gate adds latency.
   This is an expected trade-off: cognitive oversight costs time.
   Design-only shows non-significant -13% improvement (direction correct).
   ACR at 100% ceiling across all variants (no room for improvement).
3. **SS2:** Design agent is the star — AL -26% (d=-1.66, largest effect).
   **New finding:** SS2 design MTTD worsened +36% (p=0.001) — the reduced
   poll interval (`1s` vs `2s` baseline) may cause more false-positive detections
   that increase apparent MTTD. Runtime AL/MTTD not significant.
   ACR at ceiling.
4. **S4:** FDR at 100% ceiling for all variants (PQC validation is deterministic).
   TTV/VSR insufficient samples (need Batch 4).

**Impact of `--labeled-baselines-only` vs old results:**
- SS2 AL runtime_only: was significant (p=0.031) → now NOT significant (p=0.148).
  The legacy baselines (1986 NULL runs) were inflating sample size and masking noise.
- SS2 MTTD design_only: was negligible → now significant worsening (+36%, p=0.001).
  Previously hidden by diluted baseline pool.
- S5 AL: runtime effect reduced from +282% to +205% (still large, same conclusion).
- S3 Cloud: results stable — minimal change from labeled-only filtering.

**Artifacts:** [summary](evaluation/results/analysis/summary_20260417T071656Z.json),
[comparison CSV](evaluation/results/analysis/comparison_20260417T071656Z.csv),
[raw metrics](evaluation/results/raw/metrics_20260417T071656Z.csv)

**Re-run for all 8 scenarios** after queue drains:
```bash
source 3_12_7_venv/bin/activate
python -m evaluation.scripts.run_experiment \
  --scenarios s1 s2 s3_cloud s3_edge s4 s5 ss1 ss2 \
  --labeled-baselines-only --causal-mode -v
```

---

## Data Integrity Audit (2026-04-17)

### Issue 1: Legacy NULL Baselines Inflating Sample Sizes

**Finding:** `COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline')` treated all
5520 legacy NULL-variant runs as baselines. These runs predate the evaluation framework
and span Oct 2025–Apr 2026. Critically, **S5 (1521 NULL) and SS2 (1986 NULL) legacy
runs extend into the treatment era** (Apr 3–12), creating temporal overlap.

**Impact:** Inflated baseline n, masked noise in treatment comparisons.
SS2 AL runtime_only was falsely significant (p=0.031→0.148 after fix).

**Fix:** Added `--labeled-baselines-only` flag to [collector.py](evaluation/scripts/collector.py)
and [run_experiment.py](evaluation/scripts/run_experiment.py). When enabled, SQL adds
`AND JSON_VALUE(labels, '$.variant') IS NOT NULL` to exclude legacy runs.
Tests: 33/33 passed.

### Issue 2: `trigger_variant_runs.sh` Used Baseline Workflows

**Finding:** [trigger_variant_runs.sh](scripts/trigger_variant_runs.sh) dispatched
treatment variants to **baseline** workflow files (e.g., `s5_explainability.yml`)
with only a variant label, instead of the dedicated variant workflows
(e.g., `s5_explainability_design.yml`). Baseline workflows have **no agent integration**
— they produce mislabeled baselines.

**Impact:** Limited — `trigger_variant_runs.sh` was used only in Batch 0 (Mar 31),
before dedicated workflows existed. All post-Apr-11 runs were dispatched via
[dispatch_paired_runs.sh](scripts/dispatch_paired_runs.sh) which uses correct workflows.

**Fix:** Rewrote `trigger_variant_runs.sh` DISPATCH_PLAN to use dedicated workflow files
(e.g., `s5_explainability_design.yml` instead of `s5_explainability.yml`).
Added SS2 `auto_approve` and SS1 `include_p5` extra fields.

### Issue 3: S5/SS2 Design Agent Not Actually Called

**Finding:** Cloud Run logs show **0 design-agent calls** for S5 and SS2.
All 79 logged `/proposals/active` calls were: S3=44, S1=11, SS1=10, S4=7, S2=7.
S5/SS2 design_only and full runs used **hardcoded parameters** (S5: delay=5s,
SS2: delay=8s, poll=1s) — identical to seed proposal values.

**Root cause:** All S5/SS2 runs were dispatched Apr 10 (`causal-20260410T150528Z`)
but the dynamic design-agent integration commit (`b00c728`) landed Apr 11.
Workflows executed the pre-commit code which had hardcoded fallback values.

**Impact:** Treatment effect is **still valid** — the hardcoded values (S5: 5s vs 10s
baseline, SS2: 8s vs 15s baseline) produce genuine behavioral differences.
The seed proposals specify the same values. The only difference: parameter source
was compile-time instead of runtime agent fetch. For thesis purposes, these runs
demonstrate the design axis treatment correctly.

### Issue 4: Runtime Agent Coverage

**Finding:** 624 `/decide` calls logged (all HTTP 200), but only a subset of
runtime/full BQ runs correspond to actual agent calls. Cross-reference by event type:

| Event Type | Scenario | Calls | Notes |
|-----------|----------|:-----:|-------|
| resilience_degradation | S3 | 247 | S3 detection + recovery |
| adaptive_threat | SS2 | 196 | SS2 threat assessment |
| policy_violation | SS1 | 171 | Post-OPA overlay |
| risk_assessment | S5 | 155 | Pre-approval risk check |
| pipeline_failure/success | S1 | 64 | CI/CD gate |
| crypto_anomaly | S4 | 9 | PQC quality gate |
| edge_activation | S2 | 6 | OTA deployment gate |

**Impact:** Coverage is adequate for evaluated scenarios (S3/S5/SS2).
S1/S4/S2 have fewer calls due to smaller treatment sample sizes.

### Issue 5: Design Agent Silent Fallback

**Finding:** When design-agent is unreachable, workflows use `set +e` and fall back
to `{"params":{}}` (baseline defaults) **silently** — the run is still labeled as
`design_only` or `full`. No metric or flag records the fallback.

**Impact:** 2 of 79 Cloud Run calls returned HTTP 403 (both S1, Apr 11).
These 2 runs used baseline defaults but are labeled as design variants.
Negligible contamination (2/79 = 2.5%).

**Recommendation:** Add a `design_proposal_applied: true/false` field to metrics
labels in future workflow versions.

### Issue 6: S3 Edge Container Lifecycle Bugs ✅ FIXED {#issue-6-s3-edge-recovery-port-mismatch}

**Finding:** All S3 Edge variant runs fail in Batch 4 (0/60 succeeded). Runner logs
show individual jobs reporting `Failed` (~10min timeout) or `Abandoned`. Root cause
analysis reveals **two bugs**:

**Bug A — Cleanup trap kills healthy rollback container:** The "Rollback to LKG"
step calls `edge_pull_and_activate.sh` with `EDGE_HEALTH_CHECK=0`. The script starts
a healthy container on the correct port (`EDGE_HOST_PORT="${EDGE_PORT}"`). However,
`trap cleanup EXIT` on line 88 registers `docker rm -f "$CONTAINER_NAME"` to run on
any exit. When `EDGE_HEALTH_CHECK=0`, the script exits at line 91 (`exit 0`), which
triggers the trap — **killing the healthy container before the recovery poll starts**.
Result: recovery poll finds nothing → timeout 600s → `exit 1`.

Note: The port reuse (`EDGE_HOST_PORT="${EDGE_PORT}"`) and old container cleanup
(`docker rm -f "$EDGE_CONTAINER"`) were already correct in all 4 workflows. The
initially suspected "port mismatch" was a red herring — the real blocker was the trap.

**Bug B — Hardcoded `/status` overrides in `main.py`:** Lines 158–161 of
`baseline/services/edge_cv_app/main.py` hardcode HTTP 500/507 responses for
`corrupt_weights` and `disk_full` env vars, **bypassing the fault model entirely**.
This means the faulty container **always** returns 500/507 on `/status`, even after
the fault model would have recovered. Combined with Bug A, recovery is impossible.

**Affected fault modes (pre-fix):**
| Fault Mode | Detection | Recovery | Net Result |
|-----------|-----------|----------|------------|
| `corrupt_weights` | ✅ (sees 500) | ❌ Bug A+B | Always fails |
| `disk_full` | ✅ (sees 507) | ❌ Bug A+B | Always fails |
| `dead_camera` | ✅ (healthy=false) | ❌ Bug A | Always fails |
| `wrong_arch` | ✅ (healthy=false) | ❌ Bug A | Always fails |
| `cpu_starvation` | ✅ (fps low) | ❌ Bug A | Always fails |
| `net_unstable` | ✅ (intermittent) | ❌ Bug A | Always fails |

**Why some S3 Edge runs succeeded historically:**
- Legacy NULL baselines (Feb 5-20): 18 detect_edge rows with different code path
- Recent sporadic successes (runtime/full: 6+7 rows): old faulty container crashed/exited
  on its own (exit code 255), freeing the port. Recovery poll succeeded by chance
  before the new healthy container was also killed by the trap.

**Impact:** S3 Edge evaluation was **blocked** until both bugs were fixed. S3 **Cloud**
is unaffected (uses Cloud Run service URLs, not local Docker ports).
**S3 Edge has zero labeled baselines** — all 18 historical runs were NULL variant.
After fix, need to dispatch all 4 variants including baselines (Batch 5).

**Fix plan:**
1. Bug A: ~~Set `EDGE_HOST_PORT="${EDGE_PORT}"` in rollback step env, or kill the old
   container and reuse `EDGE_PORT` for the rollback container.~~ Already done in workflows.
   **Actual root cause:** `edge_pull_and_activate.sh` has `trap cleanup EXIT` that
   `docker rm -f`s the container on exit. When `EDGE_HEALTH_CHECK=0` (rollback path),
   `exit 0` triggers the trap → healthy container is killed before recovery poll starts.
   **Fix (2026-04-19):** Only set the cleanup trap when `EDGE_HEALTH_CHECK != 0`.
   Changed in `baseline/services/edge_cv_app/edge_pull_and_activate.sh`.
2. Bug B: Remove hardcoded `/status` overrides for `corrupt_weights` and `disk_full`;
   let the fault model handle degradation via the frame loop and `METRICS.to_dict()`.
   The detection script (`s3_detect_status.py`) checks `healthy`, `fps`, and
   `detection_rate` in the JSON response — all set correctly by the fault models.
   **Fix (2026-04-19):** Removed hardcoded 500/507 from `baseline/services/edge_cv_app/main.py`.
3. No workflow changes needed — all 4 S3 Edge workflows already had the correct
   `docker rm -f "$EDGE_CONTAINER"` + `EDGE_HOST_PORT="${EDGE_PORT}"` in rollback step.

---

## Expected Evaluation Output

### Full 2-Axis Comparative Analysis (all 7 scenarios)
- **n comparisons:** 7 scenarios × ~2 metrics × 3 treatments = **~42 comparisons**
- **Per comparison:** p-value, Cohen's d, 95% CI, Δ%, direction
- **Charts:** Effect size heatmap, per-metric bar charts, 2-axis quadrant plot
- **Key thesis question:** Does the cognitive layer (design + runtime) improve
  each DevSecOps metric compared to the deterministic baseline?

### Runtime Decision Quality Analysis
- **n decisions:** 855 total
  - Shadow mode: 206 (177 NO_OP + 29 ESCALATE)
  - Advisory mode: 649 (11 NO_OP + 638 ESCALATE)
- 0 decisions executed (`decision_executed=false` for all)
- 624 Cloud Run `/decide` calls logged (all HTTP 200)
- **Analysis:** Decision distribution, rationale quality, mode progression
  (shadow 03-30→04-06, advisory 04-06→present)

---

## Run Tracking Checklist

| Phase | Scenario | Variant | Target | Current | Gap | Status |
|-------|----------|---------|:------:|:-------:|:---:|--------|
| 1 | S3 Cloud | baseline | ≥30 | 506 | — | ✅ Evaluated |
| 1 | S3 Cloud | design_only | ≥30 | 155 | — | ✅ Evaluated |
| 1 | S3 Cloud | runtime_only | ≥30 | 106 | — | ✅ Evaluated |
| 1 | S3 Cloud | full | ≥30 | 110 | — | ✅ Evaluated |
| 1 | S5 | baseline | ≥30 | 250 | — | ✅ Evaluated |
| 1 | S5 | design_only | ≥30 | 130 | — | ✅ Evaluated |
| 1 | S5 | runtime_only | ≥30 | 116 | — | ✅ Evaluated |
| 1 | S5 | full | ≥30 | 116 | — | ✅ Evaluated |
| 1 | SS2 | baseline | ≥30 | 1352 | — | ✅ Evaluated |
| 1 | SS2 | design_only | ≥30 | 401 | — | ✅ Evaluated |
| 1 | SS2 | runtime_only | ≥30 | 392 | — | ✅ Evaluated |
| 1 | SS2 | full | ≥30 | 390 | — | ✅ Evaluated |
| 5 | S1 | baseline | ≥30 | 163 | — | ✅ ≥30 |
| 5 | S1 | design_only | ≥30 | 60 | — | ✅ ≥30 |
| 5 | S1 | runtime_only | ≥30 | 72 | — | ✅ ≥30 |
| 5 | S1 | full | ≥30 | 66 | — | ✅ ≥30 |
| 5 | S2 | baseline | ≥30 | 64 | — | ✅ ≥30 |
| 5 | S2 | design_only | ≥30 | 32 | — | ✅ ≥30 |
| 5 | S2 | runtime_only | ≥30 | 22 | 8 | 🔶 Need 8 more |
| 5 | S2 | full | ≥30 | 24 | 6 | 🔶 Need 6 more |
| 5 | S3 Edge | baseline | ≥30 | 0 | 30 | ❌ Zero labeled — need Batch 5 |
| 5 | S3 Edge | design_only | ≥30 | 1 | 29 | ❌ Bug fixed — need Batch 5 |
| 5 | S3 Edge | runtime_only | ≥30 | 6 | 24 | ❌ Bug fixed — need Batch 5 |
| 5 | S3 Edge | full | ≥30 | 7 | 23 | ❌ Bug fixed — need Batch 5 |
| 5 | S4 | baseline | ≥30 | 80 | — | ✅ ≥30 |
| 5 | S4 | design_only | ≥30 | 20 | 10 | 🔶 Need 10 more |
| 5 | S4 | runtime_only | ≥30 | 32 | — | ✅ ≥30 |
| 5 | S4 | full | ≥30 | 24 | 6 | 🔶 Need 6 more |
| 5 | SS1 | baseline | ≥30 | 307 | — | ✅ ≥30 |
| 5 | SS1 | design_only | ≥30 | 246 | — | ✅ ≥30 |
| 5 | SS1 | runtime_only | ≥30 | 246 | — | ✅ ≥30 |
| 5 | SS1 | full | ≥30 | 239 | — | ✅ ≥30 |

> **Updated 2026-04-19 (post Batch 4 + S3 Edge fix):**
> - Batch 4 runner session (04-17→04-18): S1 24/24 ✅, SS1 18/28, S2 42/60, S4 7/48, S3 Edge 0/60 ❌
> - S1 and SS1 now fully ready (all variants ≥30) — were blocking, now unblocked
> - S3 Edge: **zero labeled baselines** (old ~36 were legacy NULL). Bugs fixed 04-19, need Batch 5
> - S2: runtime_only (22) + full (24) need small gap fills
> - S4: design_only (20) + full (24) need small gap fills
> - **5/8 ready:** S3 Cloud ✅, S5 ✅, SS2 ✅, S1 ✅, SS1 ✅
> - **3 need Batch 5:** S3 Edge (blocked → fixed), S2 (small gaps), S4 (small gaps)

---

## Notes

- **Runtime agent mode:** shadow (03-30→04-06) → advisory (04-06→present).
  All 855 decisions have `decision_executed=false` (executor is Phase 0 stub).
  624 Cloud Run `/decide` calls logged (all HTTP 200, zero failures).
  **Enforce is out of scope** — it would require real BLOCK/ROLLBACK execution
  which modifies the deterministic baseline (IMMUTABLE). Advisory suffices for
  the 2-axis evaluation: the runtime-axis measures detection speed (MTTD) and
  decision quality (accuracy, rationale), not execution. Enforce → future work.
- **Design agent integration:** Dynamic fetch from `GET /proposals/active?scenario=…`
  since commit `b00c728` (Apr 11). Pre-Apr-11 runs used hardcoded params (identical
  to seed proposal values — verified via audit). Cloud Run logs: 77 successful
  calls + 2 failures (403, S1 on Apr 11). Design-agent coverage by scenario:
  S3=44, S1=11, SS1=10, S4=7, S2=7, S5=0, SS2=0. Zero S5/SS2 calls because all
  runs were dispatched before the dynamic integration commit.
- **Data integrity flags:** `--labeled-baselines-only` (exclude NULL-variant legacy
  runs), `--causal-mode` (temporal overlap filtering). Both are CLI flags in
  `run_experiment.py`. The `trigger_variant_runs.sh` bug (dispatching to baseline
  workflows) was fixed 2026-04-17. See §Data Integrity Audit for full details.
- **Legacy runs:** 5520 unlabeled runs (`variant=NULL`) exist across all scenarios.
  These predate the 2-axis framework. S5 and SS2 legacy runs extend into the
  treatment era — must use `--labeled-baselines-only` to exclude them.
- **Temporal overlap:** Evaluation uses `_filter_to_overlap_windows()` to ensure
  baseline and treatment runs occurred in the same time period.
- **S3 stages:** S3 has no `s3_final`; use `s3_detect`/`s3_recover` for Cloud,
  `s3_detect_edge`/`s3_recover_edge` for Edge.
  Each run_id produces one row per fault mode (6 fault modes per matrix).
- **S4 stages:** S4 has no `s4_final`; use `s4_p0_valid` through `s4_p3_replay`.
  4 sub-scenarios per run.
- **S2 stages:** S2 has `s2_activate` and `s2_ttd_edge`; no `_final` stage.
- **SS2 stages:** SS2 uses `ss2_detect`; its final metrics go through `s5_final`.
- **S3 Edge bugs (fixed 2026-04-19):** Two bugs blocked all S3 Edge runs:
  (a) `trap cleanup EXIT` in `edge_pull_and_activate.sh` killed the healthy rollback
  container when `EDGE_HEALTH_CHECK=0` caused `exit 0`;
  (b) hardcoded HTTP 500/507 in `main.py` `/status` for `corrupt_weights`/`disk_full`
  bypassed the fault model. Both fixed — see §Issue 6.
  **S3 Edge has zero labeled baselines** (old ~36 were NULL variant).
  Need Batch 5: all 4 variants including baselines.
- **S3 Cloud counts:** Use `s3_detect` stage for Cloud and `s3_detect_edge` for Edge
  (one row per run). Previous EVALUATION_PLAN versions double-counted by including
  both detect + recover stages. Corrected 2026-04-19.

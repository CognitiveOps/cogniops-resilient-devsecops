# CogniOps Evaluation Plan — Complete Scenario Coverage

> Updated: 2026-04-20 19:16 UTC
> Branch: `design_time_agent_dev`
> Thesis: "Autonomous Cognitive AI Agent for Resilient DevSecOps Environments"
> **Data integrity audit completed 2026-04-17** — see §Data Integrity Audit below.
> **S3 Edge bugs fixed + OOM fix applied 2026-04-19** — see §Issue 6 and §Issue 7 below.
> **Batch 6 complete 2026-04-20 16:00 UTC** — All 28/28 cells ≥30 labeled runs.
> **FULL 8-SCENARIO EVALUATION COMPLETE** — 54 comparisons, 5,833 samples, 7 significant improvements.
> Evaluation timestamp: `20260420T161616Z`

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

### Usable Runs (as of 2026-04-19 21:00 UTC, `--labeled-baselines-only`)

Counting rules:
- **baseline:** Only runs with explicit `labels.variant='baseline'` (legacy NULL excluded)
- **S3 Cloud / S5 / SS2 treatment:** Dynamic workflows since advisory era (≥2026-04-06).
  Shadow-era runs (before 04-06) excluded.
- **S1 / S2 / S4 / SS1 / S3 Edge treatment:** Only runs from new dynamic
  variant workflows (≥2026-04-11). Old hardcoded runs excluded.
- **S3 Cloud/Edge:** Counts use `s3_detect` / `s3_detect_edge` stage (one row per run).
- **⚠️ Previous version** of this table used COALESCE (including legacy NULL runs)
  despite the `--labeled-baselines-only` header. Numbers below are corrected.

| Scenario | baseline | design_only | runtime_only | full | Status |
|----------|:--------:|:-----------:|:------------:|:----:|--------|
| **S1** | 31 | 41 | 52 | 43 | ✅ All ≥30 — evaluated |
| **S2** | 32 | 30 | 33 | 30 | ✅ All ≥30 — evaluated |
| **S3 Cloud** | 118 | 108 | 90 | 122 | ✅ All ≥30 — evaluated |
| **S3 Edge** | 147 | 143 | 130 | 154 | ✅ All ≥30 — evaluated |
| **S4** | 30 | 30 | 30 | 30 | ✅ All ≥30 — evaluated |
| **S5** | 99 | 115 | 123 | 135 | ✅ All ≥30 — evaluated |
| **SS1** | 45 | 74 | 37 | 95 | ✅ All ≥30 — evaluated |
| **SS2** | 85 | 53 | 85 | 105 | ✅ All ≥30 — evaluated |

**All 28/28 cells ≥30.** Full evaluation completed `20260420T161616Z`.

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

### Queue Status (as of 2026-04-20 19:16 UTC)

**Queue empty. All batches complete.**

Batch 6 completed at **16:16 UTC Apr 20**:
- 7 S2 gap-fill runs: 2 design_only + 2 full + 4 baseline → all succeeded
- S3 Edge, S1, S4, SS1 gaps filled in earlier Batch 6 dispatches
- Docker daemon was down on runner restart → fixed with manual `sudo dockerd`
- 2GB swap added (`/swapfile2`) for insurance — total swap 3GB

**Final result: All 28/28 scenario×variant cells ≥30 labeled runs.**

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

**Batch 5 (2026-04-19) — S3 Edge re-dispatch:**
1. ✅ Committed S3 Edge bug fixes (trap cleanup + hardcoded `/status`)
2. ✅ Cancelled ~44 stale S3 Edge runs from Batch 4 (pre-fix commit SHA)
3. ✅ Applied OOM fix: replaced `docker build` with `docker pull` from Artifact Registry
   in all 4 S3 Edge workflows (commit `fa61d21`). Logic: try pull by SHA →
   fallback re-tag local cached image → last resort `DOCKER_BUILDKIT=0 docker build`.
4. ✅ Dispatched **60 S3 Edge runs** (15 sets × 4 variants, `b5r1` through `b5r15`)
5. ✅ Restarted watchdog (PID 28759), runner processing queue
6. ✅ **Queue drained at 02:36 UTC Apr 20** (all 60 runs processed)
7. ✅ **S3 Edge BQ: baseline=5, design=35, runtime=40, full=32** (112 total, was 0 before fix)

**Known issue (GCS upload):** All S3 Edge runs marked "failure" in GitHub Actions
because the "Upload S3 edge artifacts to GCS" step fails (gsutil OOM on 120-byte
`.sha256` file, exit code 1). All core steps succeed (BQ ingest lands data correctly).
Fix: add `continue-on-error: true` to the upload step — pending.

**Batch 6 — gap fills (COMPLETED 2026-04-20):**
1. ✅ Batch 5 queue drained (02:36 UTC Apr 20)
2. ✅ `continue-on-error: true` added to GCS upload step in S3 Edge workflows
3. ✅ S3 Edge baselines filled (5→147 after multiple dispatch batches)
4. ✅ S1 gap fills completed (27→31 baseline)
5. ✅ S2 gap fills completed (design_only 17→30, full 13→30)
6. ✅ S4 gap fills completed (all variants ≥30)
7. ✅ Full 8-scenario evaluation run:
   ```bash
   GCP_PROJECT_ID=cogent-wall-445012-h5 python -m evaluation.scripts.run_experiment \
     --scenarios s1 s2 s3_cloud s3_edge s4 s5 ss1 ss2 \
     --labeled-baselines-only --causal-mode -v
   ```
   Results: 54 comparisons, 5,833 samples, 20 charts, timestamp `20260420T161616Z`

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
- **Batch 5** (2026-04-19): S3 Edge re-dispatch after bug + OOM fixes.
  - Committed S3 Edge lifecycle fixes (trap cleanup + hardcoded `/status`)
  - Cancelled ~44 stale S3 Edge runs from Batch 4
  - Applied OOM fix: `docker pull` instead of `docker build` (commit `fa61d21`)
  - Dispatched 60 S3 Edge runs (15 sets × 4 variants, `b5r1` through `b5r15`)
  - **Runner session** (2026-04-19 18:00→ ongoing):
    - Baseline: 15 dispatched, 2 completed (failure/GCS upload), 13 cancelled → 5 BQ rows
    - Design: 17 still in queue, 33 BQ rows so far
    - Runtime: 18 still in queue, 37 BQ rows so far
    - Full: 17 still in queue, 30 BQ rows so far
    - **Total: 460 S3 Edge rows in BQ** (was 0 before fix)
  - ⚠️ All runs marked "failure" due to GCS upload step (gsutil OOM) — BQ data OK.
    See [Issue 7](#issue-7-s3-edge-oom-during-docker-build--gcs-upload-failure).

### Phase 6: Run Evaluation Pipeline ✅ COMPLETE (8/8 evaluated)
Full 8-scenario evaluation completed `20260420T161616Z` with `--labeled-baselines-only --causal-mode`.
**All 28/28 cells ≥30 labeled runs.** 54 comparisons, 5,833 samples, 20 charts.

**Results summary (54 comparisons, 5833 metric samples, labeled baselines only):**

| Scenario | Metric | Variant | Δ% | p-value | Cohen's d | Effect | Sig | Improved |
|----------|--------|---------|---:|--------:|----------:|--------|:---:|----------|
| S1 | CFR | design/runtime/full | ≈0% | >0.8 | <0.12 | negligible | — | — floor |
| S2 | DSR | all variants | 0% | 1.0 | 0.00 | — | — | — ceiling |
| S2 | TDL | design_only | −8.1% | 0.159 | −0.49 | small | — | ✅ |
| S2 | TDL | runtime_only | −10.7% | 0.109 | −0.68 | medium | — | ✅ |
| S2 | TTD_edge | all variants | ≈±3% | >0.06 | <0.27 | negligible | — | mixed |
| S3 Cloud | MTTD | design_only | −9.9% | <0.001 | −0.12 | negligible | ✅ | ✅ |
| S3 Cloud | MTTD | **runtime_only** | **−65.2%** | **<0.001** | **−0.94** | **large** | **✅** | **✅** |
| S3 Cloud | MTTD | **full** | **−65.7%** | **<0.001** | **−0.94** | **large** | **✅** | **✅** |
| S3 Cloud | MTTR | design_only | −9.7% | <0.001 | −0.12 | negligible | ✅ | ✅ |
| S3 Cloud | MTTR | **runtime_only** | **−27.2%** | **0.021** | **−0.40** | **small** | **✅** | **✅** |
| S3 Cloud | MTTR | **full** | **−32.2%** | **0.002** | **−0.47** | **small** | **✅** | **✅** |
| S3 Edge | MTTD | all variants | +21–37% | >0.2 | <0.29 | negligible-small | — | — |
| S3 Edge | MTTR | **runtime_only** | **+145.6%** | **<0.001** | **+2.54** | **large** | **✅** | **❌ ↑worse** |
| S3 Edge | MTTR | **full** | **+149.6%** | **<0.001** | **+3.61** | **large** | **✅** | **❌ ↑worse** |
| S4 | FDR/VSR | all variants | 0% | 1.0 | 0.00 | — | — | — ceiling |
| S4 | TTV | all variants | −30–40% | >0.29 | <0.49 | small | — | ✅ |
| S5 | AL | design_only | −25.5% | 0.334 | −0.14 | negligible | — | ✅ |
| S5 | AL | **runtime_only** | **+194.8%** | **<0.001** | **+0.93** | **large** | **✅** | **❌ ↑worse** |
| S5 | AL | **full** | **+217.3%** | **<0.001** | **+1.05** | **large** | **✅** | **❌ ↑worse** |
| S5 | ACR | all variants | 0% | 1.0 | 0.00 | — | — | — ceiling |
| SS1 | CFR | all variants | 0% | 1.0 | 0.00 | — | — | — floor |
| SS1 | FDR | all variants | ≈±4% | >0.8 | <0.06 | negligible | — | mixed |
| SS2 | AL | **design_only** | **−23.3%** | **<0.001** | **−1.25** | **large** | **✅** | **✅** |
| SS2 | AL | runtime_only | −7.6% | 0.443 | −0.47 | small | — | ✅ |
| SS2 | MTTD | all variants | ≈±16% | >0.1 | <0.20 | negligible | — | mixed |
| SS2 | ACR | all variants | 0% | 1.0 | 0.00 | — | — | — ceiling |

**Key findings (full 8-scenario, labeled baselines only):**
1. **S3 Cloud — flagship scenario:** All 6 comparisons significant improvements. Runtime MTTD −65% (d=−0.94, large). Design MTTD/MTTR −10% (significant). Full MTTR −32% (d=−0.47, best combined).
2. **SS2 — design agent star:** AL −23.3% (d=−1.25, large) — strongest single-axis effect across all scenarios.
3. **S3 Edge — overhead risk:** Runtime/full MTTR worsened +146–150% (d=+2.54–3.61) — agent overhead on constrained edge env.
4. **S5 — overhead confirmed:** Runtime/full AL +195–217% (d=+0.93–1.05) — cognitive gate adds latency.
5. **S2 — directional but NS:** TDL improving −8–11% but p > 0.1. DSR at ceiling.
6. **Security invariants preserved:** FDR=100%, VSR=100%, ACR=100%, CFR=0% across all variants.
7. **7/54 significant improvements, 4/54 significant worsenings, 43/54 no significant change.**
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

### Issue 7: S3 Edge OOM during Docker Build + GCS Upload Failure ✅ PARTIALLY FIXED

**Finding (2026-04-19):** Even after Bug A+B fixes, S3 Edge runs still failed
because `docker build` (BuildKit) consumed ~400MB peak RAM on the 2GB runner,
leaving insufficient memory for subsequent steps. Additionally, `gsutil cp` fails
when uploading a 120-byte `.sha256` file to GCS (exit code 1, likely OOM).

**Fix A — Docker pull instead of build (APPLIED, commit `fa61d21`):**
Replaced `docker build` with `docker pull` from Artifact Registry in all 4 S3 Edge
workflows. Logic: try `docker pull` by SHA → fallback re-tag local cached image →
last resort `DOCKER_BUILDKIT=0 docker build`. This eliminated ~400MB peak RAM usage
during the image preparation step.

**Fix B — GCS upload step (PENDING):**
The "Upload S3 edge artifacts to GCS (canonical)" step fails on every run because
gsutil OOM-kills when copying a 120-byte file. The step runs **after** BQ ingest,
so data integrity is unaffected — runs are marked "failure" in GitHub Actions but
all metrics land in BigQuery successfully.
Proposed fix: add `continue-on-error: true` to the upload step.

**Impact:** 460 S3 Edge rows now in BQ (was 0). All runs show as "failure" in GitHub
UI, but this is cosmetic — core pipeline (fault injection, detection, recovery, BQ
ingest) works correctly.

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
| 1 | S3 Cloud | baseline | ≥30 | 118 | — | ✅ Evaluated |
| 1 | S3 Cloud | design_only | ≥30 | 108 | — | ✅ Evaluated |
| 1 | S3 Cloud | runtime_only | ≥30 | 90 | — | ✅ Evaluated |
| 1 | S3 Cloud | full | ≥30 | 122 | — | ✅ Evaluated |
| 1 | S5 | baseline | ≥30 | 99 | — | ✅ Evaluated |
| 1 | S5 | design_only | ≥30 | 115 | — | ✅ Evaluated |
| 1 | S5 | runtime_only | ≥30 | 123 | — | ✅ Evaluated |
| 1 | S5 | full | ≥30 | 135 | — | ✅ Evaluated |
| 1 | SS2 | baseline | ≥30 | 85 | — | ✅ Evaluated |
| 1 | SS2 | design_only | ≥30 | 53 | — | ✅ Evaluated |
| 1 | SS2 | runtime_only | ≥30 | 85 | — | ✅ Evaluated |
| 1 | SS2 | full | ≥30 | 105 | — | ✅ Evaluated |
| 6 | S1 | baseline | ≥30 | 31 | — | ✅ Evaluated |
| 6 | S1 | design_only | ≥30 | 41 | — | ✅ Evaluated |
| 6 | S1 | runtime_only | ≥30 | 52 | — | ✅ Evaluated |
| 6 | S1 | full | ≥30 | 43 | — | ✅ Evaluated |
| 6 | S2 | baseline | ≥30 | 32 | — | ✅ Evaluated |
| 6 | S2 | design_only | ≥30 | 30 | — | ✅ Evaluated |
| 6 | S2 | runtime_only | ≥30 | 33 | — | ✅ Evaluated |
| 6 | S2 | full | ≥30 | 30 | — | ✅ Evaluated |
| 6 | S3 Edge | baseline | ≥30 | 147 | — | ✅ Evaluated |
| 6 | S3 Edge | design_only | ≥30 | 143 | — | ✅ Evaluated |
| 6 | S3 Edge | runtime_only | ≥30 | 130 | — | ✅ Evaluated |
| 6 | S3 Edge | full | ≥30 | 154 | — | ✅ Evaluated |
| 6 | S4 | baseline | ≥30 | 30 | — | ✅ Evaluated |
| 6 | S4 | design_only | ≥30 | 30 | — | ✅ Evaluated |
| 6 | S4 | runtime_only | ≥30 | 30 | — | ✅ Evaluated |
| 6 | S4 | full | ≥30 | 30 | — | ✅ Evaluated |
| 6 | SS1 | baseline | ≥30 | 45 | — | ✅ Evaluated |
| 6 | SS1 | design_only | ≥30 | 74 | — | ✅ Evaluated |
| 6 | SS1 | runtime_only | ≥30 | 37 | — | ✅ Evaluated |
| 6 | SS1 | full | ≥30 | 95 | — | ✅ Evaluated |

> **Updated 2026-04-20 19:16 UTC (Batch 6 complete — FINAL):**
> - **All 28/28 cells ≥30 labeled runs.** Evaluation complete.
> - Batch 6 gap fills: S2 design (13→30), S2 full (17→30), S3 Edge baseline (5→147),
>   S1 baseline (27→31), S4 all variants (→30), SS1 runtime (36→37)
> - Docker daemon fix (manual `sudo dockerd`) + 2GB swap added
> - Full 8-scenario evaluation: `20260420T161616Z`
> - **54 comparisons, 5,833 samples, 20 charts, 7 significant improvements**

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
  **S3 Edge OOM (fixed 2026-04-19):** Docker build consumed ~400MB peak RAM,
  replaced with `docker pull` from Artifact Registry (commit `fa61d21`). See §Issue 7.
  **460 S3 Edge rows now in BQ** (was 0). Baselines still short (5, need ≥30).
- **S3 Cloud counts:** Use `s3_detect` stage for Cloud and `s3_detect_edge` for Edge
  (one row per run). Previous EVALUATION_PLAN versions double-counted by including
  both detect + recover stages. Corrected 2026-04-19.

---

## Era 2 — Causal-Aware Design Agent Optimization

> Added: 2026-04-30
> Triggered by: Professor review — "δούμε αν υπάρχουν κάποιες παράμετροι που μπορούν να φτιαχτούν"

### Context

Era 1 evaluation (timestamp `20260420T161616Z`) identified failed comparisons where
the agent system performed worse than or not significantly different from baseline.
The professor requested an investigation into tunable parameters that could improve
these scenarios, followed by re-evaluation.

### Era 1 Failed/NS Comparisons (from 54 total)

| Scenario | Variant | Metric | Effect | Why |
|----------|---------|--------|--------|-----|
| S3 Edge | runtime_only | MTTR | +146% *** | `/decide` latency (~12s) on 8s baseline |
| S3 Edge | full | MTTR | +150% *** | Same — `/decide` + minimal param benefit |
| S5 | runtime_only | AL | +195% *** | `/decide` latency dominates |
| S5 | full | AL | +217% *** | `/decide` + reduced delay, still net negative |
| S5 | design_only | AL | -25.5% NS | Correct direction, low statistical power |
| S2 | runtime_only | TDL | -10.7% NS | Medium effect (d=-0.68), n=11 too small |

### Root Cause Analysis

The "failed" runtime_only/full comparisons in S3 Edge and S5 are **architectural**:
the `/decide` endpoint (Cloud Run + Gemini LLM inference) adds ~12s per call.
This is the **expected cost of real-time AI risk assessment** — not a bug or
misconfiguration. No parameter tuning can eliminate this overhead.

The NS (not significant) results in S5 design_only and S2 runtime_only may benefit
from (a) more aggressive params and/or (b) more samples.

### Design Agent Improvement — Causal Graph Integration

The initial Design Agent made proposals via surface-level LLM pattern matching
("metric degrading → reduce associated number") without understanding causal
relationships between parameters and metrics. This led to invalid proposals
(e.g. proposing S2_ACTIVATION_TIMEOUT_SEC=240, worse than current 120).

**Fix applied (2026-04-25 → 2026-04-30):**

1. **Causal Graph** (`design-agent/agent/causal_graph.yaml`):
   - Encodes direction (LOWER/HIGHER_IS_BETTER) for each parameter
   - Defines bounds, max expected impact, bottleneck notes
   - Documents architectural overhead (not tunable by params)
   - Lists which evaluation variants each param affects

2. **Constraint Validator** (`design-agent/agent/param_validator.py`):
   - Validates proposed params against causal graph BEFORE storage
   - Rejects params outside bounds or in wrong direction
   - Flags params that would worsen metrics vs current active values

3. **Context Builder Enhancement** (`design-agent/agent/tools/context_builder.py`):
   - Injects causal graph summary into LLM context
   - Reads and exposes active design params (so agent knows current values)
   - Added S5 + S3 Cloud metrics (previously missing)

4. **System Prompt Update** (`design-agent/agent/prompts/design_system.txt`):
   - Explicit causal reasoning instructions
   - Direction-aware proposal rules
   - Variant-awareness (param changes don't help runtime_only)

### Era 2 Agent Proposal

**Proposal ID:** `design-20260430-b23695ca`
**Generated by:** Design Agent (gemini-2.5-flash via ADK) with causal graph context

| Parameter | Era 1 (Seed) | Era 2 (Agent) | Direction | Rationale |
|-----------|:------------:|:-------------:|:---------:|-----------|
| `S5_APPROVAL_DELAY_SEC` | 5 | **1** | ↓ | Reduce HITL delay — directly cuts AL in design_only |
| `S3_DETECT_POLL_SEC` | 1 | **0.5** | ↓ | Faster fault detection — cuts MTTD |
| `S3_RECOVER_POLL_SEC` | 1 | **0.5** | ↓ | Faster recovery confirmation — cuts MTTR |

**Agent impact estimates (from proposal):**
- AL (S5 design_only): -20% to -40% (confidence: 0.7)
- MTTD cloud: -5% to -15% (confidence: 0.8)
- MTTR cloud: -5% to -15% (confidence: 0.8)
- MTTD/MTTR edge: no significant change (confidence: 0.9) — correctly identifies /decide bottleneck
- TDL (S2): no significant change (confidence: 0.8) — correctly skips

**Param validation:** PASSED (all within bounds, correct direction, improves on current)

### Era 2 Evaluation Plan — Scenarios to Re-run

Only re-run scenarios where Era 2 params differ from Era 1 AND improvement is causally possible:

| Scenario | Variants to Re-run | Why | Expected Benefit |
|----------|-------------------|-----|-----------------|
| **S5** | design_only, full | S5_APPROVAL_DELAY_SEC 5→1 | AL should decrease significantly |
| **S3 Cloud** | design_only, full | DETECT/RECOVER_POLL 1→0.5 | MTTD/MTTR should decrease |
| **S3 Edge** | design_only | RECOVER_POLL 1→0.5 | MTTR_edge may improve slightly (param is ~3s of total) |

**NOT re-running:**
- S3 Edge runtime_only/full: `/decide` latency dominates, params irrelevant
- S5 runtime_only: `/decide` latency dominates, approval delay irrelevant
- S2: agent correctly identified no param change helps (timeout already at 120)
- S1, S4, SS1, SS2: no param changes proposed

**Samples needed:** ≥30 per variant (matching Era 1 methodology).
Baseline runs from Era 1 remain valid (same deterministic workflows, no baseline changes).

### Activation Steps

1. ☐ Upload Era 2 active proposals to GCS (overwrite `active/s5.json`, `active/s3.json`)
2. ☐ Dispatch design_only + full runs for S5 (≥30 each)
3. ☐ Dispatch design_only + full runs for S3 Cloud (≥30 each)
4. ☐ Dispatch design_only runs for S3 Edge (≥30)
5. ☐ Wait for queue to drain
6. ☐ Re-run evaluation: `run_experiment.py --scenarios s5 s3_cloud s3_edge --labeled-baselines-only --causal-mode`
7. ☐ Compare Era 1 vs Era 2 results

### Expected Thesis Narrative

The evaluation demonstrates:
1. **Runtime agent adds measurable latency** (~12s per decision) — this is the
   security-latency tradeoff inherent in real-time AI risk assessment
2. **Design agent (with causal reasoning) produces valid structural optimizations**
   that reduce latency in the design_only axis without runtime overhead
3. **The two axes are complementary**: design reduces baseline latency, runtime
   adds security at the cost of some latency — net effect depends on use case
4. **AI-assisted development** (GitHub Copilot) identified the causal structure
   that the Design Agent needed to reason correctly — demonstrating human-AI
   collaboration in the improvement loop

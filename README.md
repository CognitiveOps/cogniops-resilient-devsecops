# 🧠 CogniOps – Resilient DevSecOps

Repository for the MSc Thesis  
**“Autonomous Cognitive AI Agent for Resilient DevSecOps Environments”**

---

## 🎯 Overview
This repository implements the complete MSc thesis project in two main phases:

- **Baseline Implementation (Months 1–2)** — manual hybrid DevSecOps pipelines (**S1–S5 + SS1–SS2**) and quantitative **per-scenario metrics**.  
- **Autonomous Cognitive Agent (Months 3–5)** — AI-driven reasoning, explainability, **post-quantum (PQC)** validation, and resilience automation.

The goal is to demonstrate how an autonomous cognitive agent can manage **secure DevSecOps-to-Edge pipelines**, reason about **resilience and security**, and validate updates using **post-quantum cryptography**.

---

## 📂 Repository Structure

```
cogniops-resilient-devsecops/
├── baseline/
│ ├── services/ # demo microservices (FastAPI, test workloads)
│ ├── edge/ # simulated edge devices, OTA updates, PQC validation
│ ├── .github/workflows/ # GitHub Actions pipelines (S1–S5)
│ ├── scripts/ # metrics writers, rollback logic, PQC signing
│ ├── metrics/ # raw & aggregated CSV/JSON data
│ ├── dashboards/ # Prometheus / Grafana observability
│ └── reports/ # baseline & evaluation reports
│
├── agent/
│ ├── core/ # reasoning & explainability engine
│ ├── adapters/ # connectors for cloud & edge runtimes
│ ├── policies/ # ISO/NIST/IMO compliance mapping
│ └── tests/ # unit, integration & resilience tests
│
├── infra/ # Terraform IaC for GCP (Artifact Registry, Cloud Run, BigQuery, WIF)
├── functions/ingest_runs/ # Cloud Function Gen2 for scenario metrics ingest
├── docs/ # architecture diagrams & thesis documentation
└── README.md

```
---

## 🔹 Evaluation Scenarios (S1–S5 + SS1–SS2)

| ID      | Scenario                                                                 | Purpose                                                                                                                                                                     |
| ------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **S1**  | [Cloud → Pipeline CI/CD Baseline](#s1-hybrid-baseline)                    | Measure build–test–push–deploy agility and reliability using GitHub Actions + GCP (metrics: TTD, CFR, DF).                                                                  |
| **S2**  | [Pipeline → Edge Deployment (Functional OTA Baseline)](#s2-ota-baseline) | Perform OTA deployment to simulated edge devices measuring OTA latency (TDL), end-to-end deploy time (TTD_edge), and deployment success rate (DSR). No security or PQC yet. |
| **S3**  | [Rollback & Hotfix Resilience](#s3-rollback-hotfix-resilience)            | Inject controlled faults and validate manual/hybrid recovery. Measure MTTD & MTTR.                                                                                          |
| **S4**  | [Security & PQC Validation](#s4-security-pqc-validation)                  | Validate update authenticity and PQC signature verification using NIST FIPS 203–205 algorithms.                                                                             |
| **S5**  | [Explainability & Human-in-the-Loop](#s5-explainability)                 | Measure human approval latency (AL) and audit completeness rate (ACR).                                                                                                      |
| **SS1** | [End-to-End Security Policy Audit](#ss1-end-to-end-security-policy-audit) | Execute full-pipeline OPA policy enforcement and ISO/NIST audit traceability.                                                                                               |
| **SS2** | [Adaptive Threat Mitigation](#ss2-adaptive-threat-mitigation)            | Simulate anomaly injection; the agent performs autonomous mitigation with PQC trust chain validation.                                                                       |

## 🧮 Scenario–Metric Matrix

| Scenario | Operational                    | Resilience         | Security                  | Explainability  |
| -------- | ------------------------------ | ------------------ | ------------------------- | --------------- |
| **S1**   | **TTD**, **CFR**, **DF**       | –                  | –                         | –               |
| **S2**   | **TDL**, **DSR**, **TTD_edge** | –                  | –                         | –               |
| **S3**   | –                              | **MTTD**, **MTTR** | –                         | –               |
| **S4**   | –                              | –                  | **TTV**, **VSR**, **FDR** | –               |
| **S5**   | –                              | –                  | –                         | **AL**, **ACR** |
| **SS1**  | **CFR**, **DF**                | –                  | **FDR**, **ACR**          | **ACR**         |
| **SS2**  | –                              | **MTTD**           | –                         | **AL**, **ACR** |

---

## 🧩 Metric Definitions

| Category           | Metric                                   | Description                                                       |
| ------------------ | ---------------------------------------- | ----------------------------------------------------------------- |
| **Operational**    | **TTD – Time to Deploy**                 | Time from commit to healthy deployment (agility indicator).       |
|                    | **CFR – Change Failure Rate**            | % of failed deployments over total attempts.                      |
|                    | **DF – Deployment Frequency**            | Successful deployments per unit time.                             |
|                    | **TDL – Time to Download (OTA Latency)** | Time for OTA update to reach and activate on the edge device.     |
|                    | **DSR – Deployment Success Rate**        | % of edge deployments completing successfully.                    |
|                    | **TTD_edge – Edge Time to Deploy**       | End-to-end latency from pipeline start to edge app healthy state. |
| **Resilience**     | **MTTD – Mean Time to Detect**           | Average time to detect a fault or anomaly.                        |
|                    | **MTTR – Mean Time to Recover**          | Average time to restore service after a failure.                  |
| **Security**       | **TTV – Time to Verify**                 | Time required for PQC signature validation (FIPS 203–205).        |
|                    | **VSR – Verification Success Rate**      | % of valid PQC verifications over total attempts.                 |
|                    | **FDR – Failure Detection Rate**         | % of tampered or invalid artifacts detected.                      |
| **Explainability** | **AL – Approval Latency**                | Time between agent recommendation and human approval.             |
|                    | **ACR – Audit Completeness Rate**        | % of actions with full explainable trace and metadata logs.       |

---

## ⚙️ Tech Stack

| Layer                     | Tools / Components                                              |
| ------------------------- | --------------------------------------------------------------- |
| **Cloud**                 | Google Cloud Platform (GCP)                                     |
| **CI/CD**                 | GitHub Actions + OIDC Workload Identity Federation              |
| **IaC**                   | Terraform (v1.8+) – Artifact Registry, Cloud Run, BigQuery, IAM |
| **Runtime**               | Cloud Run (Managed) + Artifact Registry Images                  |
| **Edge**                  | Docker Compose (Raspberry Pi / Jetson Nano OTA simulation)      |
| **Monitoring**            | Prometheus + Grafana (+ Loki for logs)                          |
| **Security**              | Post-Quantum Crypto (FIPS 203 – 205 : Dilithium, SPHINCS+)      |
| **Explainability**        | Structured JSON logs + Markdown/PDF Explainability Reports      |
| **Language / Frameworks** | Python 3.11 / FastAPI / pytest                                  |

---

<a id="s1-hybrid-baseline"></a>
## 🚀 S1 – Hybrid Baseline (GitHub Actions + GCP)

### 🎯 Objective
Establish a fully automated CI/CD baseline with real **deploy** to Cloud Run and quantitative metrics for TTD, DF, CFR. The deployed application is a lightweight web server, exposed via HTTP, used for health checking and status polling.

### 🧱 Pipeline stages
1. **Build → Test → Push → Deploy → Measure**
2. Source: GitHub  
   → Build/Test with Docker + pytest  
   → Push image to **Artifact Registry**  
   → Deploy to **Cloud Run (Managed)**  
   → Poll `/status` for health OK  
   → Send stage metrics events to `METRICS_INGEST_URL` (scenario-runs-ingest → BigQuery)

### 🪣 GCP Resources
| Resource | Purpose |
|-----------|----------|
| **Artifact Registry** | Docker image storage (`apps`) |
| **Cloud Run** | Service deployment (`baseline-app`) |
| **BigQuery (optional)** | Ingest metrics for later analysis |
| **Service Accounts** | `gha-infra`, `gha-app`, `run-exec` with OIDC auth |
| **Storage Bucket** | Terraform state + function source (`*-fn-src`) |

---

## 🧠 Authentication (GitHub → GCP OIDC)

| Component | Description |
|------------|--------------|
| **Workload Identity Federation** | Trust link between GitHub and GCP (issuer `https://token.actions.githubusercontent.com`) |
| **Infra SA (`gha-infra`)** | Used by Terraform to provision infrastructure |
| **App SA (`gha-app`)** | Used by CI pipeline to build/push/deploy |
| **Runtime SA (`run-exec`)** | Used by Cloud Run to execute the app |

No service keys are stored — only short-lived OIDC tokens are used.

---

## 🧪 Running S1

1. Ensure repository variables are set:

GCP_PROJECT_ID, GCP_REGION,
GCP_WIF_PROVIDER,
GCP_SA_APP_EMAIL,
GCP_SA_INFRA_EMAIL,
METRICS_INGEST_URL (optional),
TF_STATE_BUCKET (optional)

2. Push any change to `baseline/services/app/`
3. The **S1 CI/CD Baseline** workflow runs automatically.
4. Watch under **Actions → S1 CI/CD Baseline**
5. Check Summary for status + TTD + service URL.

Example summary:

S1 CI (with deploy)

Status: success

Service URL: https://baseline-app-ew.a.run.app

Full TTD (commit→healthy): 132 sec

Image: europe-docker.pkg.dev/thesis-pipeline/apps/baseline-app:abcdef1


---

## 🧩 Metrics Collection Pipeline (Per-Scenario)

All scenarios send stage events (commit/test/push/deploy/health/etc.) to the same HTTP endpoint `METRICS_INGEST_URL` (Cloud Function Gen2 `scenario-runs-ingest`). No local CSVs are kept for S1 anymore.

### 📊 Data Store

| Layer | Table | Purpose |
|:------|:------|:--------|
| **BigQuery** | `agent_metrics.runs` | Central store for all stage events across scenarios. |

### 🧱 Schema (agent_metrics.runs)

| Field | Type | Description |
|:--|:--|:--|
| `run_id` | STRING | GitHub Actions run id or logical id. |
| `scenario_id` | STRING | s1, s2, s3, s4, s5, ss1, ss2, etc. |
| `stage` | STRING | Stage name (e.g., `s1_push`, `s3_recover`). |
| `mode` | STRING | baseline / shadow / enforce. |
| `status` | STRING | success / failure / cancelled. |
| `commit_sha` | STRING | Commit SHA. |
| `t_start` / `t_end` | TIMESTAMP | Stage timestamps. |
| `duration_sec` | FLOAT | `t_end - t_start` (computed if absent). |
| `labels` | JSON | Free-form labels (service, env, branch, fault_type, etc.). |
| `metrics` | JSON | Stage metrics (e.g., digest, healthy, ttr_sample_sec). |
| `ingested_at` | TIMESTAMP | BigQuery ingestion time. |

### ⚙️ Flow

1. GitHub Actions workflows (S1–S3…) emit one event per stage to `METRICS_INGEST_URL`.  
2. Cloud Function `scenario-runs-ingest` normalizes and writes to BigQuery.  
3. Derived metrics (TTD/CFR/DF/MTTD/MTTR, etc.) are computed downstream via SQL/BI.

### S1 → BigQuery (`scenario-runs-ingest`)

Example payload for the S1 commit stage:

```json
{
  "run_id": "123456789-1",
  "scenario_id": "s1",
  "stage": "s1_commit",
  "mode": "baseline",
  "status": "success",
  "commit_sha": "<commit_sha>",
  "t_start": 1733913600,
  "t_end": 1733913600,
  "labels": {
    "service": "baseline-app",
    "env": "prod",
    "branch": "<branch>"
  }
}
```

Later stages (`s1_test`, `s1_push`, `s1_deploy`, `s1_health`, `s1_final`) follow the same shape, adding stage-specific metrics (e.g., `digest`, `service_url`, `healthy`, `ttd_sec`).

### BigQuery: CFR/DF from `agent_metrics.runs`

Example query to compute per-scenario CFR and DF directly from the unified runs table:

```sql
SELECT
  COALESCE(scenario_id, 'UNKNOWN') AS scenario_id,
  COUNT(*) AS total_runs,
  SUM(CASE WHEN LOWER(status) = 'success' THEN 1 ELSE 0 END) AS success,
  SUM(CASE WHEN LOWER(status) <> 'success' THEN 1 ELSE 0 END) AS fail,
  ROUND(
    SUM(CASE WHEN LOWER(status) <> 'success' THEN 1 ELSE 0 END) * 100.0
    / COUNT(*),
    2
  ) AS cfr_percent,
  ROUND(
    SUM(CASE WHEN LOWER(status) = 'success' THEN 1 ELSE 0 END)
    / GREATEST(
        DATE_DIFF(MAX(DATE(t_end)), MIN(DATE(t_end)), DAY) + 1,
        1
      ),
    2
  ) AS df_per_day
FROM `cogent-wall-445012-h5.agent_metrics.runs`
GROUP BY scenario_id
ORDER BY scenario_id;
```

### 📈 Example (S1 Baseline Metrics)

| Metric | Value | Meaning |
|:--|:--|:--|
| **TTD = 118 s** | Avg commit → healthy deployment. |
| **CFR = 10 %** | 1 failed run in 10. |
| **DF = 3.4 /day** | Successful deployments per day. |

---

<a id="ss1-end-to-end-security-policy-audit"></a>
## 🛡️ SS1 – Security & Policy Audit (Pipeline-Centric)

SS1 wraps the S1 CI/CD pipeline with an independent OPA policy gate and full audit trail. It validates the deploy intent (service, region, tag, registry, public flag, ingress, runtime SA, resources) against declared policies and records every stage — even when blocked — for ACR accuracy. Aligned with NIST SP 800-204C, SSDF (SP 800-218), SLSA, CNCF Cloud Native Security, and GitHub Actions hardening.

- **Scope:** Pipeline only (build → test → push → deploy). Out of scope: edge/OTA, resilience faults, PQC (handled later).
- **Principles:** Policy-as-Code (OPA), automated checks, auditability/traceability, supply-chain risk reduction.
- **Metrics:** FDR (policy violations detected), ACR (audit completeness), CFR/DF impact when the gate denies or errors.
- **Policies (`security/policies/ss1.rego`):** prod-only deploys, secure-* naming, immutable tags (no `latest`), CPU/memory bounds, allowed regions, allowed ingress (default `all` for pipeline reachability), public access flag, allowed runtime service accounts, allowed registry prefix. Null-safe guards prevent OPA errors on empty allowlists.
- **Config via repo vars:** `SS1_ALLOW_PUBLIC` (default false), `SS1_ALLOWED_INGRESS` (default `all`), `SS1_ALLOWED_REGIONS`, `SS1_ALLOWED_SERVICE_ACCOUNTS` (default `RUN_EXEC_SA_EMAIL`), `SS1_ALLOWED_REGISTRY_PREFIX`. Runtime SA checked: `RUN_EXEC_SA_EMAIL`.
- **Gate semantics:** OPA emits `gate = pass | deny | error` and `policy_violations` (int). Deploy/health run only on `pass`; otherwise `ss1_deploy`/`ss1_health` emit `status=skipped` with `reason` (`policy_violation` or `opa_error`) to keep ACR intact.
- **BigQuery ingest:** Stages (`ss1_commit`, `ss1_test`, `ss1_policy`, `ss1_push`, `ss1_deploy`, `ss1_health`, `ss1_final`) go to `agent_metrics.runs` with labels (`service`, `env`, `branch`, `epoch`, `subscenario`, `policy`, `violation_expected`, `reason` when blocked).

### SS1 Sub-Scenarios (deterministic policy cases)

| Sub-Scenario | What it tests             | Inputs tweaked                     |
| ------------ | ------------------------- | ---------------------------------- |
| **SS1-P0**   | Clean run (no violation)  | Default settings                   |
| **SS1-P1**   | Mutable image tag         | `image_tag = latest`               |
| **SS1-P2**   | Public access allowed     | `allow_unauthenticated = true` (policy says no) |
| **SS1-P3**   | Unapproved registry       | `image_repo = docker.io/...`       |
| **SS1-P4**   | Wrong region              | `region = us-central1`             |

All other pipeline stages remain unchanged; only the policy inputs change. Every stage still emits metrics (success, failure, or skipped) to preserve audit completeness.

---

<a id="s2-ota-baseline"></a>
## 🚀 S2 – Pipeline → Edge Deployment (OTA Baseline)

## 🎯 Objective

Extend the baseline CI/CD with a **functional over-the-air (OTA) deployment** path from the cloud pipeline to an **edge computer-vision web service** (the `edge_cv_app`, simulated on the GitHub runner), and measure:

* **TDL** – pure OTA latency (manifest → pull → `edge_cv_app` healthy on edge via `/status`)
* **DSR** – Deployment Success Rate for OTA activations of the `edge_cv_app` container
* **TTD_edge (optional)** – overall time from S2 job start → edge web service healthy

The edge application is a **FastAPI web server** that:

* exposes `/status` for health checks (used by S2 OTA and later S3 resilience), and  
* exposes `/infer` to run a simple **computer-vision inference** (face detection using OpenCV Haar cascades) on uploaded images.

This is a **non-secure baseline**: no PQC or cryptographic validation yet.  
Security and PQC metrics are introduced later in **S4 / SS2**.

**Execution substrate**

S2 is evaluated on the **edge OTA substrate**: an edge-like host that **pulls & runs containers from an OTA manifest** (simulated on the GitHub runner, or a real device). This is the canonical deployment mechanism reused by SS2 (“SS2 extends S2” without changing delivery semantics).

---

## 🧱 Architecture Overview

```text
GitHub Actions (S2 workflow)
        │
        ▼
Build & Push edge_cv_app image (Artifact Registry)
        │
        ▼
Create OTA manifest (s2_make_ota_manifest.py)
        │
        ▼
Edge Simulation on GitHub Runner
  └─ edge_pull_and_activate.sh:
        - read manifest
        - docker pull & run edge_cv_app
        - health check on /status
```

### ⚙️ Components

#### CI/CD

**File:** `.github/workflows/s2_edge.yml`

* Builds a multi-arch image for `edge_cv_app`
* Pushes to Artifact Registry
* Generates an OTA manifest (JSON) with image, digest, version
* Simulates edge activation on the runner via a shell script
* Sends metrics events to Cloud Function → BigQuery

#### Registry

```
${AR_LOCATION}-docker.pkg.dev/<PROJECT_ID>/apps/edge-cv-app:<sha>
```

#### Edge App (Simulated Device)

**Path:** `baseline/services/edge_cv_app`

Dockerized computer vision service with `/status` endpoint.

#### Edge Activation Script

**File:** `edge_pull_and_activate.sh`

* Downloads/pulls the image from Artifact Registry
* Starts the container
* Polls `/status` until healthy or timeout

**Why a shell script is thesis-acceptable (realism vs reproducibility)**

Using a small activation script is a deliberate baseline choice: it reproduces the core behavior of a device-side OTA updater for container workloads (manifest-driven activation, pull-by-digest immutability, stop/start of the workload, and a health gate via `/status`) while remaining deterministic and portable in CI. In a production edge stack, the same logic typically runs as a long-lived agent/service (e.g., systemd-managed “edge updater”) with persistent state, richer policies, and hardened key storage.

#### Metrics Ingest (S2+)

**Component:** Cloud Function Gen2 – `scenario-runs-ingest`

Writes to **BigQuery** → `agent_metrics.runs`

---

## 🧮 Metrics Collected (S2 Baseline)

All S2 metrics are stored centrally in **BigQuery** (`agent_metrics.runs`), not as primary CSV files.

| Category    | Metric             | Description                                                   |
| ----------- | ------------------ | ------------------------------------------------------------- |
| Operational | **TDL**            | OTA latency: manifest → edge service healthy (`s2_activate`)  |
| Operational | **TTD_edge** (opt) | Overall S2 job: workflow start → edge healthy (`s2_ttd_edge`) |
| Reliability | **DSR**            | Deployment Success Rate: success ratio of OTA activations     |
| Security    | –                  | No security/PQC metrics in S2 baseline (introduced in S4/SS2) |
| Resilience  | –                  | No MTTD/MTTR yet; rollback & faults belong to S3              |

---

## 🧩 Workflow Summary (`s2_edge.yml`)

### Trigger

* On changes to `baseline/services/edge_cv_app/**` or `.github/workflows/s2_edge.yml`
* Optionally after infra workflow completion

### Auth to GCP (OIDC)

Uses Workload Identity Federation with:

* `GCP_WIF_PROVIDER`
* `GCP_SA_APP_EMAIL`

### Build & Push Edge Image

Configure Docker for Artifact Registry:

```
${AR_LOCATION}-docker.pkg.dev
```

Build multi-arch:

```bash
docker buildx build --platform linux/amd64,linux/arm64
```

Tag and push:

```bash
${AR_LOCATION}-docker.pkg.dev/${GCP_PROJECT}/apps/edge-cv-app:${GITHUB_SHA}
```

Extract digest and store.

---

### Create OTA Manifest

Script: `baseline/scripts/s2_make_ota_manifest.py`

Inputs:

```
--image, --digest, --version
```

Output:

```
baseline/metrics/s2/artifacts/ota_<timestamp>.json
baseline/metrics/s2/artifacts/ota_<timestamp>.json.sha256
```

Manifest path exported as `ota.manifest` step output.

---

### Edge Activation (Simulated)

Steps:

1. Copy manifest into `baseline/services/edge_cv_app/`
2. Execute `edge_pull_and_activate.sh`
3. Read manifest → pull image → run container
4. Poll `http://localhost:8080/status`

**Measurements:**

| Symbol                            | Description             |
| --------------------------------- | ----------------------- |
| T0                                | start of OTA activation |
| T1                                | edge service healthy    |
| `ota_latency = T1 − T0` → **TDL** |                         |

Exports: `t_ota_start`, `t_edge_end`, `ota_latency`

---

### Metrics → BigQuery (`scenario-runs-ingest`)

Workflow sends JSON via HTTP POST to `${{ vars.METRICS_INGEST_URL }}`

#### a) `s2_activate` event

```json
{
  "run_id": "<RUN_ID>",
  "scenario_id": "s2",
  "stage": "s2_activate",
  "mode": "baseline",
  "status": "success",
  "commit_sha": "<COMMIT_SHA>",
  "t_start": <T_OTA_START>,
  "t_end": <T_EDGE_END>,
  "metrics": {
    "tdl_sec": <TDL>
  },
  "labels": {
    "service": "edge_cv_app",
    "edge_device": "gh-runner"
  }
}
```

#### b) `s2_ttd_edge` event (optional)

```json
{
  "run_id": "<RUN_ID>",
  "scenario_id": "s2",
  "stage": "s2_ttd_edge",
  "mode": "baseline",
  "status": "success",
  "commit_sha": "<COMMIT_SHA>",
  "t_start": <T0>,
  "t_end": <T_EDGE_END>,
  "metrics": {
    "ttd_edge_source": "s2_pipeline"
  },
  "labels": {
    "service": "edge_cv_app",
    "edge_device": "gh-runner"
  }
}
```
---

## 📡 BigQuery – S2 Rows (`agent_metrics.runs`)

Each S2 run generates at least two rows:

* `scenario_id = 's2', stage = 's2_activate'`
* `scenario_id = 's2', stage = 's2_ttd_edge'` (optional)

| Column             | Description                                 |
| ------------------ | ------------------------------------------- |
| `scenario_id`      | Always `"s2"` for this scenario             |
| `stage`            | `"s2_activate"` or `"s2_ttd_edge"`          |
| `status`           | `"success"` / `"failed"`                    |
| `t_start`, `t_end` | Epoch seconds converted to TIMESTAMP        |
| `duration_sec`     | Computed by ingest (`t_end - t_start`)      |
| `metrics`          | JSON (e.g., `{ "tdl_sec": 25.0 }`)          |
| `labels`           | JSON (e.g., `{ "service": "edge_cv_app" }`) |

---

## 🧮 Derived Metrics (S2)

Using rows where `scenario_id = 's2'`:

| Metric             | Definition                                                                | Filter                |
| ------------------ | ------------------------------------------------------------------------- | --------------------- |
| **TDL**            | Median/mean `duration_sec` where stage=`s2_activate` and status=`success` | `stage='s2_activate'` |
| **TTD_edge (opt)** | Duration for overall workflow → edge healthy                              | `stage='s2_ttd_edge'` |
| **DSR**            | `COUNTIF(status='success') / COUNT(*)`                                    | `stage='s2_activate'` |

> Security metrics (TTV, VSR, FDR) belong to **S4/SS2**, not part of S2.

---

## 🧪 Running S2

### Prerequisites

Ensure infrastructure is applied:

* Artifact Registry exists
* Cloud Function `scenario-runs-ingest` & BigQuery `agent_metrics.runs` deployed

Repository variables set:

```
GCP_PROJECT_ID
GCP_REGION
GCP_REPO_LOCATION
GCP_WIF_PROVIDER
GCP_SA_APP_EMAIL
METRICS_INGEST_URL
```

---

### Trigger the Workflow

* Commit to `baseline/services/edge_cv_app/**`
* or manually run:
  **Actions → S2 Edge Deployment (OTA) → Run workflow**

---

### Monitor

* ✅ Build & push to Artifact Registry
* ✅ Edge activation `/status` healthy
* ✅ Metrics POSTs to Cloud Function

---

### Query Results

BigQuery Dataset: `agent_metrics`
Table: `runs`
Filter: `scenario_id = 's2'`

---

## 📈 Evaluation Purpose

| Aspect         | Baseline S2 (no agent)           | Future S2′ (with agent)        |
| -------------- | -------------------------------- | ------------------------------ |
| Update Logic   | Static OTA pipeline              | Agent-driven OTA orchestration |
| Security Layer | None (no crypto/PQC)             | PQC-aware OTA (S4)             |
| Fault Handling | Manual recovery (S3 covers this) | Autonomous mitigation          |
| Metrics        | TDL, DSR, optional TTD_edge      | Same + reasoning metrics       |

---

**S2 establishes the pure operational baseline for cloud-to-edge OTA delivery, providing a quantitative benchmark before introducing the cognitive agent’s adaptive reasoning and resilience capabilities.**

---

<a id="s3-rollback-hotfix-resilience"></a>
## 🚧 S3 – Rollback & Hotfix Resilience (`edge_cv_app`)

### 🎯 Objective

Use the same edge workload (`edge_cv_app`) to evaluate **resilience**:

- Inject a **faulty version** of `edge_cv_app` that passes basic CI tests but fails under edge conditions.
- Let the **edge** detect the fault via health/inference checks.
- Roll back to the **last-known-good** version.
- Measure:
  - **MTTD** – time from faulted deployment to detection on the edge  
  - **MTTR** – time from detection to full recovery (previous version healthy)

This reflects realistic issues **not caught by CI**, that only appear under edge load or for specific inputs.

### 🧨 Edge Fault Injection Scenarios (S3 focus)

Structured view of the fault injections used to exercise resilience logic (A = injection, B = stochastic model, C = detection signal).

| # | Fault Scenario | A – Injection | B – Stochastic Model | C – Detection | Metrics | Literature Support |
|:-:| -------------- | ------------- | -------------------- | ------------- | ------- | ------------------- |
| 1 | Network Instability | `tc netem` loss/latency/jitter | Bernoulli `FAIL_P`; Poisson bursts | Slow `/status`, timeouts, retries ↑ | MTTD / MTTR | Intermittent Failure Dynamics; Edge Fault Survey |
| 2 | Disk Full / Read-Only FS | `/tmp/` fill until <5% space | Exponential time-to-full; Bernoulli write failure | Write error, crashloop | MTTD / MTTR | Multistate Reliability Model; Intermittent Stochastic Model Summary |
| 3 | CPU Starvation | `stress-ng` (CPU 95%+) | Poisson CPU spikes; Bernoulli per-frame slow | FPS drop, inference latency ↑ | MTTD / MTTR | Non-homogeneous Markov Faults; Edge Fault Survey |
| 4 | Dead Camera / Black Frames | Inject black or 0-byte frames | Bernoulli missing frames; gap process | `detection_rate = 0`, identical frames | MTTD / MTTR | Markov Sensor Failure (IoT); Random Telegraph Noise |
| 5 | Wrong Arch Rollout | OTA x86 image to ARM | Deterministic fail; renewal attempts | Liveness/readiness fail | MTTD / MTTR | Markov Availability Models |
| 6 | Corrupted Model Weights | Truncate `.pt` / `.onnx` files | Bernoulli corruption; Markov degradation | Model load exception | MTTD / MTTR | Intermittent Degradation Models; MSS Reliability |

Edge faults have three characteristics: intermittent (come and go), bursty (occur in clusters), multi-state (healthy → degraded → failed → recover).

Modeling layers used for automation and analysis:

- Event-level: Bernoulli `FAIL_P` for binary intermittent events (frame/healthcheck/write).
- Time-level: Poisson arrivals (Exponential inter-arrival) for random fault timing.
- State-level: 3-state Markov chain — Healthy → Degraded → Failed → Recovering (multistate reliability).

Implementation (real edge + twin):
- `baseline/services/edge_cv_app/metrics.py` — unified `EdgeMetrics` contract returned by `/status`.
- `baseline/services/edge_cv_app/fault_models.py` — behavioral fault injectors (network, CPU, camera, model).
- `baseline/services/edge_cv_app/main.py` — single container that runs in `MODE=real` (S2) or `MODE=twin` (S3) with `SCENARIO`/`FAIL_MODE` driving faults.
- S3 is benchmarked in two execution substrates (kept separate on purpose):
  - **Edge OTA (canonical for thesis scope and SS2/S2 alignment):** `.github/workflows/s3_edge_rollback.yml` where rollback is executed by re-running `baseline/services/edge_cv_app/edge_pull_and_activate.sh` against the LKG manifest (same OTA activation semantics as S2; SS2 invokes the same rollback mechanism via `.github/workflows/_s3_edge_rollback_action.yml`).
  - **Cloud Run (supplemental benchmark):** `.github/workflows/s3_rollback.yml` with Cloud Run redeploy-based recovery (useful for cloud workloads, not the OTA/edge loop).
  In both cases, metrics are ingested into `agent_metrics.runs`, but results are interpreted per-substrate (no mixing).
  For comparability, both substrates emit the same metric keys (`ttd_sample_sec`, `ttr_sample_sec`) and use the same detection logic (HTTP non-200, latency budget, and `/status` threshold triggers) with 5s polling. However, **absolute values are not expected to match**: Cloud Run “injection” includes deploy + traffic shift, while edge‑OTA “injection” is a local container restart; Cloud Run “recovery” is redeploy, while edge‑OTA “recovery” applies an LKG OTA manifest (pull/run/health on the runner).

Limitations & future work (edge OTA realism):
- Replace the script-based activation with a persistent **edge-updater agent** (container/service) that exposes an `apply(manifest)` API and maintains state across reboots.
- Model OS-level OTA and key storage (A/B partitions, TPM/HSM), and extend to fleet rollouts (multi-device staged deployment).
  - Scheduled runs: `.github/workflows/s3_schedule.yml` triggers S3 nightly (cron), with a guard that stops when BQ has >=500 S3 rows and a small repeat matrix (capped at 3 per night) to accumulate samples per fault type without unbounded growth.
- Why these edge faults (and not Kubernetes/control-plane faults): the thesis scope is cloud→pipeline→edge; Kubernetes control-plane failures are cloud-side and well-covered in existing chaos catalogs. Here we target device-level, resource-light injections that (a) reproduce reliably on GitHub runners and Cloud Run, (b) match edge literature (intermittent/bursty/multi-state), and (c) stress the OTA/rollback path where the agent operates. Kubernetes-specific chaos would test the cloud fabric, not the edge OTA/resilience loop we measure in S3.
  - Future work: add a small cloud-side chaos scenario (e.g., K8s node/network fault) to complement edge faults; current scope stays edge-focused to align with cloud→pipeline→edge and OTA/resilience measurement.

### 🧩 How S3 models stochastic, intermittent, multi-state faults

- **Fault models (A/B):** Bernoulli per-frame events + Poisson bursts/spikes (network, CPU), time-to-full ramp with Bernoulli write errors (disk), Bernoulli missing frames (camera), deterministic + retry cycle (wrong-arch), growing Bernoulli corruption with gradual degradation (weights).  
- **State-level:** a 3-state Markov stepper (healthy → degraded → failed → recovering) shapes base metrics before fault injection to reflect multi-state reliability.  
- **Detection (C):** non-200 responses, latency budgets, and metrics thresholds on `/status` (`fps_min`, `detection_rate_min`, `healthy` flag) drive MTTD. MTTR is time to healthy after rollback.

Threshold rationale (per matrix in `.github/workflows/s3_rollback.yml`):
- `latency_budget_sec` — used for network/CPU faults to catch slow `/status` responses from jitter/spikes (e.g., 2s for net, 3s for CPU).  
- `fps_min` — tighter for CPU (`15`) to flag throttling; relaxed (`10`) elsewhere to avoid false positives.  
- `detection_rate_min` — near-zero for camera (`0.001`) to detect black frames; default (`0.01`) for others.  
- **Calibration:** before faults, the workflow polls the healthy service on the runner and derives thresholds from observed noise (p95 latency × 3, p5 fps × 0.7, p5 detection_rate × 0.5). The calibrated values override the matrix defaults, are exported as env vars for detection, and are included as labels in the BigQuery ingest so you can audit/retune per run.  
- All other metrics stay identical so baseline vs agent comparisons remain schema-compatible.

Stochastic model parameters (configurable via env in `s3_rollback.yml`, defaults shown):
- Network: `S3_NET_FAIL_P=0.1`, `S3_NET_BURST_PROB=0.05`
- CPU: `S3_CPU_DROP_FACTOR=0.4`, `S3_CPU_SPIKE_LAMBDA=0.2`
- Camera: `S3_CAM_FAIL_P=0.25`
- Corrupted weights: `S3_MODEL_BASE_FAIL_P=0.05`, `S3_MODEL_GROWTH=0.02`
- Disk: `S3_DISK_TIME_TO_FULL=90.0`, `S3_DISK_BASE_FAIL_P=0.05`
- Wrong arch: `S3_WRONG_RETRY_INTERVAL=20.0`, `S3_WRONG_FAIL_WINDOW=10.0`, `S3_WRONG_RETRY_SUCCESS_P=0.2`

---

### 🧱 Architecture Overview (S3)

```text
GitHub Actions (S3 workflow: s3_rollback.yml)
        │
        ▼
Build & push "faulty" edge_cv_app image (Artifact Registry)
        │
        ▼
Create OTA manifest for faulty version
        │
        ▼
Edge pulls & activates faulty manifest (edge_pull_and_activate.sh)
        │
        ▼
Fault Injection & Detection on Edge
  └─ s3_fault_probe.py / test_infer.py:
        - send inference requests to /infer
        - detect failures (HTTP 5xx, invalid payloads, high latency)
        - record t_detect
        │
        ▼
Rollback
  └─ edge_rollback.sh:
        - redeploy last-known-good image (stored OTA manifest)
        - wait for /status healthy
        - record t_recover
        │
        ▼
Metrics → Cloud Function (scenario-runs-ingest) → BigQuery agent_metrics.runs
````

---

### 💻 Workload: `edge_cv_app`

Edge app (already used in S2):

* `GET /status` – health endpoint
* `POST /infer` – OpenCV Haar-cascade face detection endpoint

Faults can be simulated by, for example:

* Environment variable (e.g. `FAULT_MODE=1`) causing `/infer` to raise errors or sleep.
* A code branch that misbehaves only for specific payloads (e.g. certain image sizes).

---

### 🧮 Metrics Collected (S3)

S3 uses the same generic table **`agent_metrics.runs`** with **two main stages per run**:

#### 1️⃣ `s3_detect` – fault detection on edge

* `t_start`: moment we start probing the faulty version.
* `t_end`: moment detection condition is met (e.g. N consecutive failures or timeout).
* `duration_sec` ≈ **TTD_sample** for that run.
* `metrics.ttd_sample_sec` mirrors `duration_sec` (per-run sample; mean is computed later in BQ).
* `metrics.metrics_raw` (optional) carries the `/status` snapshot when detection fired (for XAI/forensics).

#### 2️⃣ `s3_recover` – rollback / hotfix recovery

* `t_start`: moment rollback is triggered.
* `t_end`: edge service back to healthy on previous version.
* `duration_sec` ≈ **TTR_sample** for that run.
* `metrics.ttr_sample_sec` mirrors `duration_sec` (per-run sample; mean is computed later in BQ).
* `metrics.metrics_raw` (optional) carries the `/status` snapshot when recovery completed.

---

### 📡 Example payloads to `scenario-runs-ingest`

```json
{
  "run_id": "<RUN_ID>",
  "scenario_id": "s3",
  "stage": "s3_detect",
  "mode": "baseline",
  "status": "success",
  "commit_sha": "<FAULTY_COMMIT_SHA>",
  "t_start": 1762720000,
  "t_end": 1762720035,
  "metrics": {
    "ttd_sample_sec": 35.0,
    "metrics_raw": {
      "fps": 8.5,
      "detection_rate": 0.0,
      "queue_latency_ms": 120.0,
      "inference_ms": 60.0,
      "healthy": false,
      "state": "failed",
      "frame_idx": 1234,
      "ts": 1762720035
    }
  },
  "labels": {
    "service": "edge_cv_app",
    "env": "cloud-run",
    "fault_type": "cpu-starvation",
    "latency_budget_sec": "3",
    "fps_min": "15",
    "detection_rate_min": "0.05"
  }
}
```

```json
{
  "run_id": "<RUN_ID>",
  "scenario_id": "s3",
  "stage": "s3_recover",
  "mode": "baseline",
  "status": "success",
  "commit_sha": "<FAULTY_COMMIT_SHA>",
  "t_start": 1762720035,
  "t_end": 1762720090,
  "metrics": {
    "ttr_sample_sec": 55.0,
    "metrics_raw": {
      "fps": 24.0,
      "detection_rate": 0.82,
      "queue_latency_ms": 18.0,
      "inference_ms": 22.0,
      "healthy": true,
      "state": "healthy",
      "frame_idx": 1500,
      "ts": 1762720090
    }
  },
  "labels": {
    "service": "edge_cv_app",
    "env": "cloud-run",
    "fault_type": "cpu-starvation",
    "latency_budget_sec": "3",
    "fps_min": "15",
    "detection_rate_min": "0.05"
  }
}
```

---

### 🧮 BigQuery – MTTD / MTTR Query (S3)

Example query to extract **MTTD/MTTR summary per fault type**, **separated by substrate** (so you can keep Cloud Run vs edge‑OTA results distinct without mixing):

```sql
-- S3 (both substrates) – MTTD/MTTR by fault type.
--
-- edge‑OTA (runner-simulated edge):
--   stage s3_detect_edge  → metrics.ttd_sample_sec (legacy runs may have mttd_sample_sec)
--   stage s3_recover_edge → metrics.ttr_sample_sec
--
-- Cloud Run:
--   stage s3_detect        → metrics.ttd_sample_sec
--   stage s3_recover       → metrics.ttr_sample_sec
--
-- Optional sanity check (uncomment):
-- SELECT stage, JSON_VALUE(labels,'$.env') AS env, COUNT(*) AS rows
-- FROM `PROJECT_ID.agent_metrics.runs`
-- WHERE scenario_id='s3'
-- GROUP BY stage, env
-- ORDER BY stage, env;

WITH s3 AS (
  SELECT
    run_id,
    REPLACE(
      COALESCE(JSON_VALUE(labels, '$.fault_type'), JSON_VALUE(labels, '$.fault_mode'), 'unknown'),
      '_',
      '-'
    ) AS fault_type,
    CASE
      WHEN JSON_VALUE(labels, '$.env') = 'gh-runner' THEN 'edge-ota'
      WHEN JSON_VALUE(labels, '$.env') = 'cloud-run' THEN 'cloud-run'
      -- Back-compat: older rows may not have labels.env, so infer substrate from stage.
      WHEN stage IN ('s3_detect_edge', 's3_recover_edge') THEN 'edge-ota'
      WHEN stage IN ('s3_detect', 's3_recover') THEN 'cloud-run'
      ELSE COALESCE(JSON_VALUE(labels, '$.env'), 'unknown')
    END AS substrate,
    stage,
    SAFE_CAST(
      COALESCE(
        JSON_VALUE(metrics, '$.ttd_sample_sec'),
        JSON_VALUE(metrics, '$.mttd_sample_sec')
      ) AS FLOAT64
    ) AS mttd_sample_sec,
    SAFE_CAST(JSON_VALUE(metrics, '$.ttr_sample_sec') AS FLOAT64) AS mttr_sample_sec
  FROM `PROJECT_ID.agent_metrics.runs`
  WHERE scenario_id = 's3'
    AND stage IN ('s3_detect_edge', 's3_recover_edge', 's3_detect', 's3_recover')
    AND status = 'success'
),
paired AS (
  SELECT
    run_id,
    substrate,
    fault_type,
    MAX(IF(stage IN ('s3_detect_edge', 's3_detect'), mttd_sample_sec, NULL)) AS mttd_sample_sec, -- detect
    MAX(IF(stage IN ('s3_recover_edge', 's3_recover'), mttr_sample_sec, NULL)) AS mttr_sample_sec  -- recover
  FROM s3
  GROUP BY run_id, substrate, fault_type
),
filtered AS (
  SELECT *
  FROM paired
  WHERE mttd_sample_sec IS NOT NULL
    AND mttr_sample_sec IS NOT NULL
)
SELECT
  substrate,
  fault_type,
  COUNT(*) AS runs,
  AVG(mttd_sample_sec) AS mttd_avg_sec,
  APPROX_QUANTILES(mttd_sample_sec, 101)[OFFSET(50)] AS mttd_p50_sec,
  APPROX_QUANTILES(mttd_sample_sec, 101)[OFFSET(95)] AS mttd_p95_sec,
  AVG(mttr_sample_sec) AS mttr_avg_sec,
  APPROX_QUANTILES(mttr_sample_sec, 101)[OFFSET(50)] AS mttr_p50_sec,
  APPROX_QUANTILES(mttr_sample_sec, 101)[OFFSET(95)] AS mttr_p95_sec
FROM filtered
GROUP BY substrate, fault_type
ORDER BY substrate, fault_type;
```

> Replace `PROJECT_ID` with your actual GCP project ID.

---

### 🧨 Edge Fault Injection Scenarios (S3 focus)

Structured view of the fault injections used to exercise resilience logic (A = injection, B = stochastic model, C = detection signal).

| # | Fault Scenario | A – Injection | B – Stochastic Model | C – Detection | Metrics | Literature Support |
|:-:| -------------- | ------------- | -------------------- | ------------- | ------- | ------------------- |
| 1 | Network Instability | `tc netem` loss/latency/jitter | Bernoulli `FAIL_P`; Poisson bursts | Slow `/status`, timeouts, retries ↑ | MTTD / MTTR | Intermittent Failure Dynamics; Edge Fault Survey |
| 2 | Disk Full / Read-Only FS | `/tmp/` fill until <5% space | Exponential time-to-full; Bernoulli write failure | Write error, crashloop | MTTD / MTTR | Multistate Reliability Model; Intermittent Stochastic Model Summary |
| 3 | CPU Starvation | `stress-ng` (CPU 95%+) | Poisson CPU spikes; Bernoulli per-frame slow | FPS drop, inference latency ↑ | MTTD / MTTR | Non-homogeneous Markov Faults; Edge Fault Survey |
| 4 | Dead Camera / Black Frames | Inject black or 0-byte frames | Bernoulli missing frames; gap process | `detection_rate = 0`, identical frames | MTTD / MTTR | Markov Sensor Failure (IoT); Random Telegraph Noise |
| 5 | Wrong Arch Rollout | OTA x86 image to ARM | Deterministic fail; renewal attempts | Liveness/readiness fail | MTTD / MTTR | Markov Availability Models |
| 6 | Corrupted Model Weights | Truncate `.pt` / `.onnx` files | Bernoulli corruption; Markov degradation | Model load exception | MTTD / MTTR | Intermittent Degradation Models; MSS Reliability |

Edge faults have three characteristics: intermittent (come and go), bursty (clusters), multi-state (healthy → degraded → failed → recover).

Modeling layers used for automation and analysis:

- Event-level: Bernoulli `FAIL_P` for binary intermittent events (frame/healthcheck/write).
- Time-level: Poisson arrivals (Exponential inter-arrival) for random fault timing.
- State-level: 3-state Markov chain — Healthy → Degraded → Failed → Recovering (multistate reliability).

Implementation (real edge + twin):
- `baseline/services/edge_cv_app/metrics.py` — unified `EdgeMetrics` contract returned by `/status`.
- `baseline/services/edge_cv_app/fault_models.py` — behavioral fault injectors (network, CPU, camera, model).
- `baseline/services/edge_cv_app/main.py` — single container that runs in `MODE=real` (S2) or `MODE=twin` (S3) with `SCENARIO`/`FAIL_MODE` driving faults.
- `baseline/s3/run_s3_single_scenario.py` + `baseline/s3/detector.py` — polls `/status`, computes MTTD/MTTR, and posts to BigQuery ingest.

---

<a id="s4-security-pqc-validation"></a>
## 🔒 S4 – Security & PQC Validation

Scenario S4 is an isolated, deterministic benchmark for post-quantum (PQC) signature verification of the OTA manifest already used in S2/S3. It focuses exclusively on authenticity and integrity (FIPS 203–205 style digital signatures) without changing the deployment logic or introducing resilience/rollback behavior.

**What runs:** a dedicated GitHub Actions workflow (`.github/workflows/s4_pqc.yml`) creates an OTA manifest fixture, generates a PQC keypair, signs the manifest, and executes four sub-scenarios:

- **S4-P0:** valid manifest + correct signature (expected PASS)
- **S4-P1:** tampered manifest (expected FAIL)
- **S4-P2:** incorrect public key (expected FAIL)
- **S4-P3:** replayed/old manifest (expected FAIL via replay window; modeled as a logical freshness violation of signed metadata rather than a transport-level replay)

**Metrics emitted:** per-stage Time-to-Verify (**TTV**) for P0–P3 events. Aggregate metrics (**VSR**, **FDR**, `ttv_valid_ms`, `ttv_all_ms`) are derived in BigQuery from the raw per-case events; a local `results.json` summary is kept under `baseline/metrics/s4/`.

**BigQuery query (S4):** summary query with **valid-path TTV** (P0 only) plus **all-attempt TTV**, VSR, and FDR (test case derived from `stage`).
```sql
-- S4 summary (valid-path + all-attempt TTV, VSR, FDR)
WITH s4_cases AS (
  SELECT
    run_id,
    stage,
    status,
    COALESCE(
      SAFE_CAST(JSON_VALUE(metrics, '$.ttv_sec') AS FLOAT64),
      SAFE_CAST(JSON_VALUE(metrics, '$.ttv_ms') AS FLOAT64) / 1000.0,
      duration_sec
    ) AS ttv_sec,
    COALESCE(
      JSON_VALUE(metrics, '$.pqc_backend'),
      JSON_VALUE(labels, '$.backend'),
      JSON_VALUE(labels, '$.pqc_backend')
    ) AS backend,
    COALESCE(
      JSON_VALUE(metrics, '$.pqc_algorithm'),
      JSON_VALUE(labels, '$.algorithm'),
      JSON_VALUE(labels, '$.alg')
    ) AS alg,
    UPPER(REGEXP_EXTRACT(stage, r's4_(p[0-9]+)_')) AS test_case,
    COALESCE(
      SAFE_CAST(JSON_VALUE(metrics, '$.expected') AS BOOL),
      SAFE_CAST(JSON_VALUE(labels, '$.expected') AS BOOL),
      UPPER(REGEXP_EXTRACT(stage, r's4_(p[0-9]+)_')) = 'P0'
    ) AS expected_bool,
    COALESCE(
      SAFE_CAST(JSON_VALUE(metrics, '$.verified') AS BOOL),
      SAFE_CAST(JSON_VALUE(labels, '$.verified') AS BOOL)
    ) AS verified_bool
  FROM `cogent-wall-445012-h5.agent_metrics.runs`
  WHERE scenario_id = 's4'
    AND STARTS_WITH(stage, 's4_p')
)
SELECT
  COALESCE(backend, 'unknown') AS backend,
  COALESCE(alg, 'unknown')     AS alg,
  COUNT(*) AS case_rows,

  -- Primary (thesis): valid-path TTV (P0 only)
  APPROX_QUANTILES(IF(test_case = 'P0', ttv_sec, NULL), 101)[OFFSET(50)] AS ttv_p50_valid_sec,
  APPROX_QUANTILES(IF(test_case = 'P0', ttv_sec, NULL), 101)[OFFSET(95)] AS ttv_p95_valid_sec,

  -- Secondary (industry): all attempts
  APPROX_QUANTILES(ttv_sec, 101)[OFFSET(50)] AS ttv_p50_all_sec,
  APPROX_QUANTILES(ttv_sec, 101)[OFFSET(95)] AS ttv_p95_all_sec,
  AVG(ttv_sec) AS ttv_avg_all_sec,
  SAFE_DIVIDE(
    COUNTIF(expected_bool = TRUE AND verified_bool = TRUE),
    NULLIF(COUNTIF(expected_bool = TRUE), 0)
  ) AS vsr,
  SAFE_DIVIDE(
    COUNTIF(expected_bool = FALSE AND verified_bool = FALSE),
    NULLIF(COUNTIF(expected_bool = FALSE), 0)
  ) AS fdr
FROM s4_cases
GROUP BY backend, alg
ORDER BY backend, alg;
```

**Verifier CLI:** `baseline/security/pqc/verify.py` verifies a canonical manifest against a signature and public key, with optional replay-window enforcement. This is reused in SS2 to validate real OTA artifacts.

**Artifact-level signatures:** S4 emits `ota.json.pqcsig` and `pub.key` alongside the manifest to model OCI/registry metadata bundles used in production.

**Crypto backend (industry-ready):** the verifier is pluggable but requires a real PQC backend via Open Quantum Safe (`liboqs` / python-oqs), with **ML-DSA (Dilithium)** as the default demo algorithm for fast verification and OTA-friendly signature sizes.

**Required demo config:** set `S4_PQC_BACKEND=oqs` and `S4_PQC_ALG=Dilithium2` in repo variables. The workflow installs `liboqs-python` from source and fails if OQS is unavailable, avoiding toy/auto fallbacks.

**Compliance posture:** the implementation is **FIPS-aligned / NIST-selected** and architecture-ready for certified modules (KMS/HSM), without making certification claims.

**Why isolated:** S4 establishes reproducible cryptographic baselines that SS2 will reuse for trust decisions without re-benchmarking crypto performance, keeping experimental boundaries clean.

---

<a id="s5-explainability"></a>
## 🧭 S5 – Explainability & Human-in-the-Loop

**S5** evaluates the **Explainability and Human-in-the-Loop (HITL)** layer as an **independent, standalone scenario**, producing quantitative explainability metrics:

- **AL (Approval Latency)**
- **ACR (Audit Completeness Rate)**

In addition, S5 provides a **reusable Explainability & Approval Kit** that is later **invoked by SS2 (Adaptive Threat Mitigation)** to avoid duplicated implementations.

This creates a clean experimental separation:

- **S5** → component-level evaluation (explainability & HITL)
- **SS2** → system-level evaluation (adaptive mitigation using the same components)

---

## Design Principles

- **Explainability-by-design:** every automated recommendation produces a structured explanation.
- **Human-in-the-loop gating:** high-risk actions require explicit human approval.
- **Auditability & traceability:** all actions are logged with sufficient metadata for post-hoc analysis.
- **Reusability:** the same explainability primitives are reused by SS2.

---

## Approval Mechanism (HITL)

### Selected mechanism: simulated gate (S5) + soft gate (SS2)

This project separates **measurement** (S5) from **real usage** (SS2):

- **S5 (standalone benchmark):** human participation is **intentionally simulated** to preserve determinism and reproducibility. AL is measured using **scripted approval delays / deterministic approval policies**, not real human behavior.
- **SS2 (system evaluation):** a human approval step is executed *in the pipeline* before recovery actions. On **GitHub Free + private repos** (where “Required reviewers” is unavailable), SS2 uses an **issue/comment-based soft gate**: the workflow creates a HITL issue and waits for an `approve` / `reject` comment from an allowed approver list.

> This is auditable: the decision is recorded as S5/SS2 ActionTrace events in BigQuery, and the soft gate additionally leaves a human comment trail in GitHub Issues.

Soft-gate configuration (repo variables):

- `SS2_APPROVERS="yourUser,otherUser"` (CSV; default: the workflow actor)
- `SS2_APPROVAL_TIMEOUT_MIN=60`, `SS2_APPROVAL_POLL_SEC=20`

---

## Repository Layout (S5 as Scenario + Kit)

Reusable kit (invoked by S5 and SS2):

```
baseline/explainability/
  ├── schema.py        # ActionTrace schema + required fields (ACR contract)
  ├── cloudevents.py   # CloudEvents v1.0 wrapper utilities
  ├── emit.py          # Emits stage events to METRICS_INGEST_URL
  ├── report.py        # Markdown / JSON explanation generator
  └── approval.py      # Approval timestamp helpers (AL)
```

---

## Standalone S5 Workflow

Workflow:

```
.github/workflows/s5_explainability.yml
```

### Workflow behavior

S5 executes **controlled synthetic cases**, independent of S1–S4 or SS2, such as:

- policy violation detected
- tampered artifact detected
- rollback recommendation generated

### Stages

1. **`s5_explain`**
   - generates ActionTraces + explanation reports
   - records `t_recommend`
2. **`s5_approve`**
   - simulates approval with a deterministic delay
   - records `t_approved`
3. **`s5_final`**
   - computes **AL** and **ACR**
   - sends final metrics to `agent_metrics.runs` via `METRICS_INGEST_URL` (required by default)

---

## Metrics

### Approval Latency (AL)

```
AL = t_approved − t_recommend
```

Where:

- `t_recommend` is recorded when the recommendation is emitted (before the gate)
- `t_approved` is recorded when the environment-approved job resumes

---

### Audit Completeness Rate (ACR)

In S5, “sufficient explainability” is not judged subjectively (by a human or by AI). Instead, it is defined structurally via an audit schema. Each action trace must contain a minimum required set of fields (defined in `baseline/explainability/schema.py`). An action is “complete” if all required fields are present.

```
ACR = (# complete audit records) / (total actions)
```

---

## Reuse in SS2 (Adaptive Threat Mitigation)

S5 is **not re-implemented** in SS2. SS2 invokes the same kit via the reusable workflow:

```
.github/workflows/_hitl_explain_and_approve_soft.yml
```

This ensures identical explainability semantics, consistent AL/ACR measurement, and no duplication of logic.

---

## CloudEvents → GCP Ingest (optional)

The same `METRICS_INGEST_URL` endpoint can ingest both:

- **stage metrics events** (run/stage timing + aggregated metrics), and
- **CloudEvents v1.0 ActionTraces** emitted by S5/SS2 (stored as `stage = action_trace` in `agent_metrics.runs`).

This enables computing metrics (especially **ACR**) directly from BigQuery without relying on workflow artifacts.

---

## Standards & Related Work

- **NIST SP 800-53 (AU family)** — audit/event logging completeness and accountability controls.
- **CloudEvents v1.0 (CNCF)** — standard event envelope for portable, structured event data.
- **OpenTelemetry Semantic Conventions** — standardized attributes for `service.name` and `deployment.environment.name`.
- **OPA decision logs** — common industry pattern for explainable policy decisions (inputs/outputs/metadata).
- **GitHub Actions Environments & Required Reviewers** — CI/CD manual approval gate used for production deployments.

References:

- GitHub Environments: https://docs.github.com/actions/deployment/targeting-different-environments/using-environments-for-deployment
- CloudEvents spec: https://github.com/cloudevents/spec
- OpenTelemetry semantic conventions: https://opentelemetry.io/docs/what-is-opentelemetry/
- NIST SP 800-53 Rev. 5: https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- OPA decision logs: https://www.openpolicyagent.org/docs/management-decision-logs

---

<a id="ss2-adaptive-threat-mitigation"></a>
## 🛡️ SS2 – Adaptive Threat Mitigation

(Extension of the S2 OTA Delivery Pipeline)

---

### 1. Architectural Objective

The **SS2 (Adaptive Threat Mitigation)** scenario evaluates the capability of a DevSecOps system to **detect, contain, and mitigate security or integrity incidents** occurring across a **cloud-to-edge delivery pipeline**, while preserving **auditability, explainability, and trust guarantees**.

Crucially, **SS2 is designed as a direct extension of the S2 OTA delivery scenario**. Rather than introducing a new deployment mechanism, SS2 **reuses the S2 OTA pipeline unchanged** and augments it with additional **control, verification, mitigation, and explainability layers**.

Unlike earlier scenarios that benchmark isolated capabilities—such as CI/CD performance (**S1**), OTA delivery (**S2**), resilience and recovery mechanisms (**S3**), cryptographic verification (**S4**), or explainability (**S5**)—SS2 is a system-level orchestration scenario. Its objective is to validate how previously evaluated components (**S3 – Resilience & Recovery**, **S4 – Security / PQC**, and **S5 – Explainability & Human-in-the-Loop**) are composed on top of the S2 delivery mechanism to form an operational mitigation loop under realistic incident conditions.

S2 provides the delivery substrate; S3 provides validated recovery actions; SS2 provides the adaptive control and mitigation logic.

---

### 2. Design Principles

The SS2 architecture is grounded in three well-established paradigms drawn from security operations, software supply-chain security, and experimental methodology.

---

#### 2.1 Incident Response Lifecycle (Structural Backbone)

SS2 follows the standard incident response lifecycle:

Detect → Contain → Recover → Verify → Resume

This lifecycle is formally defined in incident-handling guidance by NIST and is widely adopted in Security Operations Centers (SOCs).

**Justification**

Using an incident-response model ensures that mitigation actions are:

- Explainable, as each step has a clear operational rationale,
- Repeatable, through deterministic control flow,
- Measurable, enabling quantitative evaluation via MTTD,
- Comparable, aligning results with real-world security operations.

While recovery correctness and timing are benchmarked in S3, SS2 focuses on orchestrating when and why recovery actions are invoked within the incident-response lifecycle.

**Primary references**

- NIST SP 800-61 Rev.2 – Computer Security Incident Handling Guide: https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final
- NIST SP 800-92 – Guide to Computer Security Log Management: https://csrc.nist.gov/publications/detail/sp/800-92/final

---

#### 2.2 SOAR-Style Orchestration (Execution Model)

SS2 is implemented as a SOAR-like orchestration layer that wraps the S2 OTA workflow, consisting of:

- Triggers: anomaly or integrity-failure signals originating from S2 execution (activation failures, degraded health, integrity mismatches),
- Playbooks: predefined mitigation workflows applied to S2 deployments,
- Actions: block, quarantine, invoke validated recovery actions, verify, and escalate.

This mirrors modern Security Orchestration, Automation, and Response (SOAR) platforms used in enterprise environments.

**Justification**

A SOAR-style orchestration model:

- Enables automation without altering the underlying delivery pipeline,
- Avoids embedding opaque intelligence directly into S2 execution steps,
- Cleanly separates delivery logic (S2) from control and mitigation logic (SS2).

Recovery actions coordinated by SS2 are implemented and benchmarked in S3 and are not re-evaluated in SS2.

**Primary references**

- Gartner – Security Orchestration, Automation and Response (SOAR): https://www.gartner.com/en/information-technology/glossary/security-orchestration-automation-response-soar
- IBM – What is SOAR?: https://www.ibm.com/think/topics/security-orchestration-automation-response

---

#### 2.3 Separation of Measurement vs Usage (Experimental Validity)

SS2 does not benchmark recovery efficiency, cryptographic performance, or explainability quality directly.

Instead:

- S3 independently benchmarks resilience and recovery mechanisms (e.g., rollback correctness, MTTR),
- S4 independently benchmarks security verification metrics (TTV, VSR, FDR),
- S5 independently benchmarks explainability and human-in-the-loop metrics (AL, ACR).

SS2 reuses these components during S2 execution, following the evaluation hierarchy:

Component-level evaluation (S3, S4, S5) → System-level orchestration (SS2 over S2)

This separation prevents metric contamination and ensures methodological rigor.

---

### 3. High-Level SS2 Architecture (Layered over S2)

SS2 is architected as a control and mitigation layer operating on top of the S2 OTA delivery pipeline.

At runtime:

- OTA activation remains unchanged and is executed using the mechanisms defined in S2,
- Recovery actions (e.g., rollback) are invoked using mechanisms implemented and benchmarked in S3,
- SS2 observes, controls, and intervenes in the S2 flow only when an incident is detected.

This design ensures that delivery semantics remain identical, while SS2 evaluates the effectiveness of adaptive mitigation.

---

### 4. Core Architectural Components (Extensions of S2)

#### 4.1 Detection Layer

**Role** Monitors S2 execution outcomes to identify abnormal or malicious conditions, including:

- OTA integrity failures during S2 activation,
- Edge health degradation reported by the S2 `/status` endpoint,
- Repeated S2 deployment or activation failures,
- Artifact or provenance mismatches discovered pre- or post-activation.

**Characteristics**

- Deterministic, rule-based logic in the SS2 baseline,
- Timestamped detection events enabling measurement of MTTD.

#### 4.2 Mitigation Orchestrator (SS2 Core)

**Role** Coordinates mitigation actions within the S2 pipeline by invoking predefined playbooks mapped to detected threat categories.

**Example playbooks**

- Block S2 activation before container start,
- Invoke rollback or recovery actions implemented and benchmarked in S3,
- Quarantine the affected edge workload,
- Rotate or invalidate trust metadata.

SS2 does not reimplement or remeasure recovery logic, but orchestrates the invocation of validated recovery actions.

#### 4.3 Trust Verification (Delegated to S4)

**Role in SS2** Before S2 activation or recovery, SS2 invokes the S4 trust verifier to validate artifact authenticity, signature correctness, and resistance to replay or tampering.

SS2 records only a boolean outcome (`trust_verified = true | false`) and does not measure cryptographic performance.

**Primary references**

- The Update Framework (TUF): https://theupdateframework.io/
- Uptane: https://uptane.github.io/

#### 4.4 Explainability & Human-in-the-Loop (Delegated to S5)

**Role in SS2** SS2 invokes S5 modules around S2 execution to generate structured explanations, emit audit logs, and optionally pause execution for human approval.

Explainability metrics (AL, ACR) are measured in S5 and reused in SS2.

**Primary references**

- NIST AI Risk Management Framework (AI RMF 1.0): https://www.nist.gov/itl/ai-risk-management-framework
- EU High-Level Expert Group on Trustworthy AI: https://digital-strategy.ec.europa.eu/en/policies/expert-group-ai

---

### 5. Baseline vs Agent-Enhanced SS2 (Over the Same S2 Pipeline)

| Aspect | Baseline SS2 (over S2) | Agent-Enhanced SS2 (over S2) |
| --- | --- | --- |
| Detection | Fixed rules | Learned / adaptive |
| Decisions | Deterministic mapping | Reasoned / probabilistic |
| Actions | Predefined playbooks | Dynamic playbooks |
| Recovery mechanism | Invoked from S3 | Invoked from S3 |
| Delivery mechanism | S2 OTA pipeline | S2 OTA pipeline |
| Verification | S4 verifier | S4 verifier |
| Explainability | S5 modules | S5 modules |
| Metrics | MTTD, AL, ACR | Same + reasoning metrics |

This design enables direct quantitative comparison, as both baseline and agent-enhanced SS2 operate on the exact same S2 delivery substrate and reuse the same validated recovery mechanisms from S3.

---

### 6. Baseline Implementation (Repository)

SS2 is implemented as a GitHub Actions scenario that wraps the S2 OTA activation unchanged, injects controlled incidents, measures MTTD, and then routes mitigation decisions through the S5 HITL + explainability kit.

Workflow: `.github/workflows/ss2_adaptive_threat_mitigation.yml`

Why this substrate:

- SS2 runs on the **same edge OTA substrate as S2** (manifest-driven pull/run + `/status`), so “SS2 extends S2” holds without changing the deployment mechanism. Cloud Run resilience is kept as a separate (supplemental) S3 benchmark.

Detection metric (SS2-only):

- `stage = ss2_detect` → `mttd_sample_sec` (via `baseline/scripts/ss2_detect.py`)

HITL metrics (reused from S5, recorded under `scenario_id=ss2`):

- `stage = s5_final` → `al_sec`, `acr` (via `.github/workflows/_hitl_explain_and_approve_soft.yml`)

Supported incident modes (always-all run):

- Entry point: `.github/workflows/ss2_adaptive_threat_mitigation.yml`
- Runs **all** runtime faults sequentially (matrix): `corrupt_weights`, `dead_camera`, `cpu_starvation`, `net_unstable`, `disk_full`, `wrong_arch`
- Also runs **integrity_failure variants** (auto‑block before activation).
  Integrity failures (per **TUF/Uptane** and incident‑handling best practices) include — and are **simulated** as SS2 subcases:
  - **Invalid signature** / wrong key / threshold not met
  - **Hash mismatch** (manifest checksum file does not match)
  - **Digest mismatch** (manifest digest does not exist in registry)
  - **Replay / rollback** (stale version or metadata expiry)
  - **Unauthorized delegation / target metadata** (policy‑level integrity)

Approval gate (SS2):

- **Runtime faults only:** uses an **issue/comment soft gate** (creates a HITL issue and waits for `approve` / `reject`).  
  → This is where **AL/ACR** are measured (reused from S5).
- **Integrity failures:** **auto‑block before activation** (**no approval gate**, no HITL metrics).  
  → Treated as **pre‑activation trust failures** (TUF/Uptane style), not remediation decisions.
- Allowed approvers can be constrained via repository variable `SS2_APPROVERS` (CSV); default is the workflow actor.

Recovery action (implemented & benchmarked in S3; orchestrated in SS2):

- SS2 invokes the reusable S3 rollback action `.github/workflows/_s3_edge_rollback_action.yml` (recovery itself is benchmarked in `.github/workflows/s3_edge_rollback.yml` as part of S3).

Optional PQC trust check (SS2 invokes S4 verifier without measuring S4 metrics):

PQC trust is mandatory in SS2 (thesis mode):

- SS2 requires repository variable `SS2_ENABLE_PQC=true` and signs + verifies the candidate manifest using `baseline/security/pqc/sign.py` and `baseline/security/pqc/verify.py`.

Artifact storage (canonical):

- SS2 stores artifacts in GCS under `gs://${AGENT_ARTIFACTS_BUCKET}/runs/ss2/${RUN_ID}/` (bucket is provisioned by Terraform and upserted as repo variable `AGENT_ARTIFACTS_BUCKET` via `infra_apply.yml`).

---

#### 🔑 Final takeaway (advisor & industry safe)

SS2 extends the S2 OTA delivery scenario by layering adaptive detection, orchestration, trust verification, and explainability mechanisms on top of an unchanged deployment pipeline, while invoking recovery actions validated in S3 to enable system-level adaptive threat mitigation aligned with established incident-response and SOAR practices.

---

#### Optional thesis add-ons

##### What is implemented vs measured (S2 / S3 / SS2)

| Scenario | Primary role | Implemented (capabilities) | Measured (metrics) | Explicitly not measured here |
| --- | --- | --- | --- | --- |
| S2 | OTA delivery substrate | Cloud-to-edge OTA packaging, distribution, activation, and health polling | TDL, DSR, TTD_edge | Recovery performance (MTTD/MTTR), cryptographic verification (TTV/VSR/FDR), explainability (AL/ACR) |
| S3 | Resilience & recovery benchmark | Fault injection plus validated recovery actions (e.g., rollback/hotfix) and recovery correctness checks | MTTD, MTTR | Delivery performance (TDL/DSR/TTD_edge), cryptographic verification (TTV/VSR/FDR), explainability (AL/ACR) |
| SS2 | Adaptive mitigation orchestration over S2 | Detection + playbook orchestration over the unchanged S2 pipeline; invokes S3 recovery actions; invokes S4 trust verification; invokes S5 explainability/HITL | MTTD (orchestration loop), AL, ACR (reused from S5) | Recovery efficiency (MTTR) and rollback performance (benchmarked in S3); cryptographic performance (TTV/VSR/FDR, benchmarked in S4) |

Diagram: single-page S2 → S3 → SS2 evaluation flow (ideal for the evaluation chapter)

---

## 📈 Timeline

| Month | Focus | Deliverable |
|:--:|--|--|
| **1** | **Full Baseline Implementation (S1–S5, SS1–SS2)** | Implement all baseline scenarios end-to-end: **S1 (CI/CD)**, **S2 (Edge OTA)**, **S3 (Rollback)**, **S4 (Security/PQC)**, **S5 (Explainability)**, plus **SS1/SS2 (Security & Adaptive Mitigation)**. Collect the complete set of metrics — **TTD, CFR, DF, TDL, DSR, MTTD, MTTR, TTV, VSR, FDR, AL, ACR** — and store them centrally in **BigQuery**. Deliver a unified **Baseline Metrics Report** establishing quantitative reference values before introducing the agent. |
| **2** | Baseline Consolidation | Statistical analysis & report |
| **3** | Agent Development | Reasoning engine + PQC modules |
| **4** | Evaluation | Baseline vs Agent quantitative comparison |
| **5** | Optimization & Presentation | Final PoC demo + thesis submission |

---

## 🧠 Next Steps 
- **SS2:** Adaptive threat mitigation simulation  
- **Agent Core:** Autonomous reasoning + XAI integration  

---

## 📜 License
Released under the **MIT License**.  
© 2025 CognitiveOps — All rights reserved.

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
├── functions/ingest/ # Cloud Function Gen2 for metrics ingest
├── docs/ # architecture diagrams & thesis documentation
└── README.md

---

## 🔹 Evaluation Scenarios (S1–S5 + SS1–SS2)

| ID      | Scenario                                                 | Purpose                                                                                                                                                                     |
| ------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **S1**  | **Cloud → Pipeline CI/CD Baseline**                      | Measure build–test–push–deploy agility and reliability using GitHub Actions + GCP (metrics: TTD, CFR, DF).                                                                  |
| **S2**  | **Pipeline → Edge Deployment (Functional OTA Baseline)** | Perform OTA deployment to simulated edge devices measuring OTA latency (TDL), end-to-end deploy time (TTD_edge), and deployment success rate (DSR). No security or PQC yet. |
| **S3**  | **Rollback & Hotfix Resilience**                         | Inject controlled faults and validate manual/hybrid recovery. Measure MTTD & MTTR.                                                                                          |
| **S4**  | **Security & PQC Validation**                            | Validate update authenticity and PQC signature verification using NIST FIPS 203–205 algorithms.                                                                             |
| **S5**  | **Explainability & Human-in-the-Loop**                   | Measure human approval latency (AL) and audit completeness rate (ACR).                                                                                                      |
| **SS1** | **End-to-End Security Policy Audit**                     | Execute full-pipeline OPA/Kyverno policy enforcement and ISO/NIST audit traceability.                                                                                       |
| **SS2** | **Adaptive Threat Mitigation**                           | Simulate anomaly injection; the agent performs autonomous mitigation with PQC trust chain validation.                                                                       |

---

## 🧮 Scenario–Metric Matrix

| Scenario | Operational                    | Resilience         | Security                  | Explainability  |
| -------- | ------------------------------ | ------------------ | ------------------------- | --------------- |
| **S1**   | **TTD**, **CFR**, **DF**       | –                  | –                         | –               |
| **S2**   | **TDL**, **DSR**, **TTD_edge** | –                  | –                         | –               |
| **S3**   | –                              | **MTTD**, **MTTR** | –                         | –               |
| **S4**   | –                              | –                  | **TTV**, **VSR**, **FDR** | –               |
| **S5**   | –                              | –                  | –                         | **AL**, **ACR** |
| **SS1**  | **CFR**, **DF**                | –                  | **FDR**, **ACR**          | **ACR**         |
| **SS2**  | –                              | **MTTD**, **MTTR** | **TTV**, **VSR**, **FDR** | **AL**          |

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
   → Write metrics to CSV (`baseline/metrics/s1_pipeline_runs.csv`)

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

| Script | Purpose |
|---------|----------|
| **`baseline/scripts/s1_write_metrics.py`** | Appends stage metrics (commit, test, push, deploy, health) to CSV. Scenario context (S1) replaces older epoch logic. |
| **`baseline/scripts/metrics_snapshot.py`** | Merges CSV history and computes lifetime & per-scenario CFR/DF values (no rolling window). |

All metrics are automatically collected from GitHub Actions workflows and stored under  
`baseline/metrics/` for reproducibility.

---

## 🧾 S1 Metrics Schema — CSV and BigQuery Alignment

This schema and dataflow apply **only to Scenario S1 (Cloud → Pipeline CI/CD Baseline)**.  
It captures operational metrics — **TTD**, **CFR**, and **DF** — directly from the GitHub Actions pipeline and GCP deployment events.

### 📊 Data Stores

| Layer | File / Table | Purpose |
|:------|:--------------|:--------|
| **Local CSV (GitHub Actions)** | `baseline/metrics/s1_pipeline_runs.csv` | Per-run ledger for S1 executions. |
| **BigQuery Table** | `agent_metrics.s1_pipeline_runs` | Central analytics store for S1 metrics (via Cloud Function Gen2 ingest). |

### 🧱 Schema (CSV + BigQuery)

| Field | Type | Source | Description |
|:--|:--|:--|:--|
| **run_id** | STRING | GitHub Actions | Unique workflow run ID. |
| **workflow** | STRING | Workflow name (`s1_ci`) | Identifies pipeline. |
| **scenario_id** | STRING | Static | Always `S1`. |
| **branch** | STRING | Git ref | Branch tested. |
| **env** | STRING | Variable | Runtime environment (e.g. `cloud-run`). |
| **service** | STRING | Variable | Cloud Run service (e.g. `baseline-app`). |
| **status** | STRING | GitHub Job | Final status (success / failure / cancelled). |
| **failure_stage** | STRING | Derived | First stage that failed (commit/test/push/deploy/health). |
| **commit_sha** | STRING | Git | Commit hash of deployed revision. |
| **tests_total** | INTEGER | pytest | Total test sets executed. |
| **tests_failed** | INTEGER | pytest | Failed test sets. |
| **commit_ts** | TIMESTAMP | Stage commit | Pipeline start. |
| **push_ts** | TIMESTAMP | Stage push | Docker image push. |
| **deploy_ts** | TIMESTAMP | Stage deploy | Cloud Run deployment end. |
| **ended_ts** | TIMESTAMP | Stage health | Service healthy (HTTP 200). |
| **ttd_sec** | FLOAT | Derived | Time-to-Deploy = `ended_ts − commit_ts`. |
| **inserted_at** | TIMESTAMP | BigQuery | Server ingestion timestamp. |

### 🧮 Derived Metrics

| Metric | Formula | Interpretation |
|:--|:--|:--|
| **TTD** | `ended_ts − commit_ts` | End-to-end CI/CD agility. |
| **CFR** | `failed runs / total runs × 100` | Deployment stability. |
| **DF** | `successful runs / days(active)` | Deployment throughput. |

---

### ⚙️ Collection Flow

1. **GitHub Actions Workflow** (`.github/workflows/s1_ci.yml`)  
   Stages → Build → Test → Push → Deploy → Health → writes CSV via `s1_write_metrics.py`.  
2. **Snapshot Builder** (`metrics_snapshot.py`)  
   Merges CSV history → computes lifetime CFR/DF statistics.  
3. **Cloud Function Ingest** (optional)  
   Receives row and inserts it into BigQuery.

### 📈 Example (S1 Baseline Metrics)

| Metric | Value | Meaning |
|:--|:--|:--|
| **TTD = 118 s** | Avg commit → healthy deployment. |
| **CFR = 10 %** | 1 failed run in 10. |
| **DF = 3.4 /day** | Successful deployments per day. |

---

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

Workflow sends JSON via HTTP POST to `${{ vars.SCENARIO_RUNS_INGEST_URL }}`

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
SCENARIO_RUNS_INGEST_URL
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

### 🧩 How S3 models stochastic, intermittent, multi-state faults

- **Fault models (A/B):** Bernoulli per-frame events + Poisson bursts/spikes (network, CPU), time-to-full ramp with Bernoulli write errors (disk), Bernoulli missing frames (camera), deterministic + retry cycle (wrong-arch), growing Bernoulli corruption with gradual degradation (weights).  
- **State-level:** a 3-state Markov stepper (healthy → degraded → failed → recovering) shapes base metrics before fault injection to reflect multi-state reliability.  
- **Detection (C):** non-200 responses, latency budgets, and metrics thresholds on `/status` (`fps_min`, `detection_rate_min`, `healthy` flag) drive MTTD. MTTR is time to healthy after rollback.

Threshold rationale (per matrix in `.github/workflows/s3_rollback.yml`):
- `latency_budget_sec` — used for network/CPU faults to catch slow `/status` responses from jitter/spikes (e.g., 2s for net, 3s for CPU).  
- `fps_min` — tighter for CPU (`15`) to flag throttling; relaxed (`10`) elsewhere to avoid false positives.  
- `detection_rate_min` — near-zero for camera (`0.001`) to detect black frames; default (`0.01`) for others.  
- **Calibration:** before faults, the workflow polls the healthy service and derives thresholds from observed noise (p95 latency × 3, p5 fps × 0.7, p5 detection_rate × 0.5). These calibrated values override defaults and are stored as labels in BigQuery.  
- All other metrics stay identical so baseline vs agent comparisons remain schema-compatible.

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

Example query to extract **per-run** and **summary** resilience metrics:

```sql
-- S3 – MTTD / MTTR metrics for edge_cv_app (scenario_id = 's3')
-- Source of truth: agent_metrics.runs

WITH s3_runs AS (
  SELECT
    run_id,

    -- Prefer duration_sec of the stage rows; if missing, fall back to metrics JSON (per-run samples)
    COALESCE(
      MAX(IF(stage = 's3_detect'  AND status = 'success', duration_sec, NULL)),
      MAX(CAST(JSON_VALUE(metrics, '$.ttd_sample_sec') AS FLOAT64))
    ) AS ttd_sample_sec,

    COALESCE(
      MAX(IF(stage = 's3_recover' AND status = 'success', duration_sec, NULL)),
      MAX(CAST(JSON_VALUE(metrics, '$.ttr_sample_sec') AS FLOAT64))
    ) AS ttr_sample_sec

  FROM `cogent-wall-445012-h5.agent_metrics.runs`
  WHERE scenario_id = 's3'
  GROUP BY run_id
),

summary AS (
  SELECT
    COUNTIF(ttd_sample_sec IS NOT NULL OR ttr_sample_sec IS NOT NULL)     AS successful_runs,
    AVG(ttd_sample_sec)                                                   AS mttd_avg_sec,
    APPROX_QUANTILES(ttd_sample_sec, 101)[OFFSET(50)]                     AS mttd_p50_sec,
    APPROX_QUANTILES(ttd_sample_sec, 101)[OFFSET(95)]                     AS mttd_p95_sec,
    AVG(ttr_sample_sec)                                                   AS mttr_avg_sec,
    APPROX_QUANTILES(ttr_sample_sec, 101)[OFFSET(50)]                     AS mttr_p50_sec,
    APPROX_QUANTILES(ttr_sample_sec, 101)[OFFSET(95)]                     AS mttr_p95_sec
  FROM s3_runs
)

-- Final output: per-run rows + one summary row
SELECT
  'per_run' AS row_type,
  r.run_id,
  r.ttd_sample_sec,
  r.ttr_sample_sec,
  NULL AS successful_runs,
  NULL AS mttd_avg_sec,
  NULL AS mttd_p50_sec,
  NULL AS mttd_p95_sec,
  NULL AS mttr_avg_sec,
  NULL AS mttr_p50_sec,
  NULL AS mttr_p95_sec
FROM s3_runs r

UNION ALL

SELECT
  'summary' AS row_type,
  NULL AS run_id,
  NULL AS mttd_sec,
  NULL AS mttr_sec,
  s.successful_runs,
  s.mttd_avg_sec,
  s.mttd_p50_sec,
  s.mttd_p95_sec,
  s.mttr_avg_sec,
  s.mttr_p50_sec,
  s.mttr_p95_sec
FROM summary s;
```

> Replace `PROJECT_ID` with your actual GCP project ID.
> This yields one row **per S3 run** plus one **summary row** with aggregate MTTD/MTTR.

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

Edge faults έχουν 3 χαρακτηριστικά: intermittent (έρχονται και φεύγουν), bursty (clusters), multi-state (healthy → degraded → failed → recover).

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
- **S4:** Security & PQC validation tests  
- **S5:** Explainability / Human-in-the-Loop metrics  
- **SS1:** Policy audit & compliance trace  
- **SS2:** Adaptive threat mitigation simulation  
- **Agent Core:** Autonomous reasoning + XAI integration  

---

## 📜 License
Released under the **MIT License**.  
© 2025 CognitiveOps — All rights reserved.

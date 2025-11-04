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

| ID | Scenario | Purpose |
|----|-----------|----------|
| **S1** | Cloud → Pipeline CI/CD Baseline | Measure build–test–push–deploy TTD, CFR, DF metrics via GitHub Actions + GCP. |
| **S2** | Pipeline → Edge Deployment | OTA deployment to simulated edge devices with latency & integrity metrics. |
| **S3** | Rollback & Hotfix Resilience | Fault injection → manual recovery → measure MTTD & MTTR. |
| **S4** | Security & PQC Validation | Validate update authenticity using NIST PQC algorithms (FIPS 203–205). |
| **S5** | Explainability & Human-in-the-Loop | Measure approval latency (AL) and audit completeness (ACR). |
| **SS1** | End-to-End Security Policy Audit | Execute full-pipeline OPA/Kyverno policy enforcement with ISO/NIST trace. |
| **SS2** | Adaptive Threat Mitigation | Simulate anomaly injection; agent performs autonomous mitigation with PQC trust chain. |

---

## 🧮 Scenario–Metric Matrix

| Scenario | Operational | Resilience | Security | Explainability |
|:--|:--:|:--:|:--:|:--:|
| **S1** | **TTD**, **CFR**, **DF** | – | – | – |
| **S2** | **TTD** | – | **VSR**, **TTV** | – |
| **S3** | – | **MTTD**, **MTTR** | – | – |
| **S4** | – | – | **TTV**, **VSR**, **FDR** | – |
| **S5** | – | – | – | **AL**, **ACR** |
| **SS1** | **CFR**, **DF** | – | **FDR**, **ACR** | **ACR** |
| **SS2** | – | **MTTD**, **MTTR** | **TTV**, **VSR**, **FDR** | **AL** |

---

## 🧩 Metric Definitions

| Category | Metric | Description |
|-----------|---------|-------------|
| **Operational** | **TTD** – Time to Deploy | Time from commit to healthy deployment (agility). |
|  | **CFR** – Change Failure Rate | % of failed deployments over total attempts. |
|  | **DF** – Deployment Frequency | Successful deployments per unit time (lifetime). |
| **Resilience** | **MTTD** – Mean Time to Detect | Avg time to detect a fault or anomaly. |
|  | **MTTR** – Mean Time to Recover | Avg time to restore system functionality. |
| **Security** | **TTV** – Time to Verify | Time for PQC signature validation. |
|  | **VSR** – Verification Success Rate | % of successful PQC verifications. |
|  | **FDR** – Failure Detection Rate | % of tampered artifacts detected. |
| **Explainability** | **AL** – Approval Latency | Delay in human decision loop. |
|  | **ACR** – Audit Completeness Rate | % of actions with full explainable logs. |

---

## ⚙️ Tech Stack
**Cloud:** Google Cloud Platform (GCP)  
**CI/CD:** GitHub Actions + OIDC Workload Identity Federation  
**IaC:** Terraform (v1.8+) for Artifact Registry, Cloud Run, BigQuery, IAM  
**Runtime:** Cloud Run (Managed) + Artifact Registry images  
**Edge:** Docker Compose on Raspberry Pi / Jetson Nano (simulated OTA)  
**Monitoring:** Prometheus + Grafana (+ Loki for logs)  
**Security:** Post-Quantum Crypto Validation (FIPS 203–205 – Dilithium, SPHINCS+)  
**Explainability:** Structured JSON logs + Markdown/PDF XAI reports  
**Language:** Python 3.11 / FastAPI / pytest

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
| **healthy_ts** | TIMESTAMP | Stage health | Service healthy (HTTP 200). |
| **ttd_sec** | FLOAT | Derived | Time-to-Deploy = `healthy_ts − commit_ts`. |
| **inserted_at** | TIMESTAMP | BigQuery | Server ingestion timestamp. |

### 🧮 Derived Metrics

| Metric | Formula | Interpretation |
|:--|:--|:--|
| **TTD** | `healthy_ts − commit_ts` | End-to-end CI/CD agility. |
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

🟦 **Note:** Currently only **S1** produces operational telemetry.  
Future scenarios (S2–S5, SS1–SS2) will extend the schema with additional fields (e.g., `edge_latency_ms`, `pqc_verify_time_ms`, `xai_latency_ms`, `audit_score`) to capture security, resilience, and explainability metrics.

---

## 📈 Timeline

| Month | Focus | Deliverable |
|:--:|--|--|
| **1** | Baseline & Metrics | S1 CI/CD Pipeline + initial TTD/CFR/DF metrics |
| **2** | Baseline Consolidation | Statistical analysis & report |
| **3** | Agent Development | Reasoning engine + PQC modules |
| **4** | Evaluation | Baseline vs Agent quantitative comparison |
| **5** | Optimization & Presentation | Final PoC demo + thesis submission |

---

## 🧠 Next Steps
- **S2:** Edge deployment + OTA simulation  
- **S3:** Rollback & hotfix resilience  
- **S4:** Security & PQC validation tests  
- **S5:** Explainability / Human-in-the-Loop metrics  
- **SS1:** Policy audit & compliance trace  
- **SS2:** Adaptive threat mitigation simulation  
- **Agent Core:** Autonomous reasoning + XAI integration  

---

## 📜 License
Released under the **MIT License**.  
© 2025 CognitiveOps — All rights reserved.

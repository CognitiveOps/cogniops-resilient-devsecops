# 🧠 CogniOps – Resilient DevSecOps

Repository for the MSc Thesis  
**“Autonomous Cognitive AI Agent for Resilient DevSecOps Environments”**

---

## 🎯 Overview
This repository implements the complete MSc thesis project in two main phases:

- **Baseline Implementation (Months 1–2)** — manual hybrid DevSecOps pipelines (S1–S5) and quantitative baseline metrics.  
- **Autonomous Cognitive Agent (Months 3–5)** — AI-driven reasoning, explainability, post-quantum (PQC) validation, and resilience automation.

The goal is to demonstrate how an autonomous cognitive agent can manage secure DevSecOps-to-Edge pipelines, reason about resilience and security, and validate updates with post-quantum cryptography.

---

## 📂 Repository Structure

cogniops-resilient-devsecops/
├── baseline/
│ ├── services/ # demo microservices (FastAPI, test workloads)
│ ├── edge/ # simulated edge devices, OTA updates, PQC validation
│ ├── .github/workflows/ # GitHub Actions for S1–S5 pipelines
│ ├── scripts/ # metrics collection, rollback logic, PQC signing
│ ├── metrics/ # raw and aggregated CSV/JSON data for evaluation
│ ├── dashboards/ # Prometheus / Grafana dashboards for observability
│ └── reports/ # baseline and evaluation reports
│
├── agent/
│ ├── core/ # reasoning, explainability, cognitive decision layer
│ ├── adapters/ # connectors for cloud and edge runtimes
│ ├── policies/ # ISO/NIST/DevSecOps compliance rules and policy mapping
│ └── tests/ # unit, integration, and resilience validation tests
│
├── infra/ # Terraform IaC for GCP (Artifact Registry, Cloud Run, BigQuery, WIF)
├── functions/ingest/ # Cloud Function Gen2 for metrics ingest (optional)
├── docs/ # architecture diagrams, thesis documentation
└── README.md


---

## 🔹 Evaluation Scenarios (S1–S5)

| ID | Scenario | Purpose |
|----|-----------|----------|
| **S1** | Cloud → Pipeline CI/CD Baseline | Measure build–test–push–deploy TTD, CFR, DF metrics using GitHub Actions + GCP (Artifact Registry + Cloud Run). |
| **S2** | Pipeline → Edge Deployment | OTA deployment to simulated edge devices with latency & integrity metrics. |
| **S3** | Rollback & Hotfix Resilience | Fault injection → manual recovery → measure MTTD & MTTR. |
| **S4** | Security & PQC Validation | Validate update authenticity using NIST PQC algorithms (FIPS 203–205: Dilithium / SPHINCS+). |
| **S5** | Explainability & Human-in-the-Loop | Measure approval latency (AL) and audit completeness (ACR). |

---

## ⚙️ Tech Stack

**Cloud Platform:** Google Cloud Platform (GCP)  
**CI/CD:** GitHub Actions + OIDC Workload Identity Federation  
**IaC:** Terraform (v1.8+) for Artifact Registry, Cloud Run, BigQuery, IAM  
**Runtime:** Cloud Run (Managed) + Docker Images from Artifact Registry  
**Edge:** Docker Compose on Raspberry Pi / Jetson Nano (simulated OTA)  
**Monitoring:** Prometheus + Grafana (+ Loki for logs)  
**Security:** Post-Quantum Crypto Validation (FIPS 203–205 – Dilithium, SPHINCS+)  
**Explainability:** Structured JSON logs + Markdown / PDF XAI reports  
**Language:** Python 3.11 / FastAPI / pytest  

---

## 🧩 Metrics Collected

| Category | Metric | Description |
|-----------|---------|-------------|
| Operational | **TTD**, **CFR**, **DF** | Time-to-Deploy, Change Failure Rate, Deployment Frequency |
| Resilience | **MTTD**, **MTTR** | Mean Time to Detect / Recover failures |
| Security | **TTV**, **VSR**, **FDR** | PQC verification time & success rates |
| Explainability | **AL**, **ACR** | Approval Latency & Audit Completeness Rate |

---

## 🚀 S1 – Hybrid Baseline (GitHub Actions + GCP)

### 🎯 Objective
Establish a fully automated CI/CD baseline with real **deploy** to Cloud Run and quantitative metrics for TTD, DF, CFR.

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

## 📈 Timeline

| Month | Focus | Deliverable |
|:--:|--|--|
| **1** | Baseline & Metrics | S1 CI/CD Pipeline + initial TTD/CFR measurements |
| **2** | Baseline Consolidation | Statistical analysis & report |
| **3** | Agent Development | Reasoning engine, PQC modules |
| **4** | Evaluation | Baseline vs Agent quantitative comparison |
| **5** | Optimization & Presentation | Final PoC demo + thesis submission |

---

## 🧠 Next Steps
- **S2:** Edge deployment + OTA simulation  
- **S3:** Rollback & hotfix resilience  
- **S4:** Security & PQC validation tests  
- **S5:** Explainability / Human-in-the-Loop metrics  
- **Agent Core:** autonomous reasoning + explainability integration  

---

## 📜 License
Released under the **MIT License**.  
© 2025 CognitiveOps — All rights reserved.

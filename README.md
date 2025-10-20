# 🧠 CogniOps – Resilient DevSecOps

Repository for the MSc Thesis  
**“Autonomous Cognitive AI Agent for Resilient DevSecOps Environments”**

---

## 🎯 Overview
This repository implements the full five-month MSc project:
- **Baseline Implementation (Months 1–2)** – manual DevSecOps pipelines (S1–S5) and quantitative metrics.  
- **Autonomous Cognitive Agent (Months 3–5)** – AI-driven reasoning, explainability, post-quantum (PQC) validation, and resilience automation.

The project demonstrates how an autonomous cognitive agent can manage secure CI/CD-to-Edge pipelines, perform explainable reasoning, and validate deployments through post-quantum cryptography.

---

## 📂 Repository Structure

cogniops-resilient-devsecops/
├── baseline/
│ ├── services/ # demo microservices (FastAPI)
│ ├── .github/workflows/ # GitHub Actions for S1–S5
│ ├── scripts/ # PQC, metrics, rollback, approvals
│ ├── metrics/ # raw and aggregated CSV/JSON data
│ ├── dashboards/ # Prometheus / Grafana dashboards
│ └── reports/ # Baseline and consolidation reports
├── agent/
│ ├── core/ # reasoning, explainability, memory
│ ├── adapters/ # connectors for cloud / edge systems
│ ├── policies/ # ISO/NIST/IMO compliance mapping
│ └── tests/ # unit & integration tests
├── docs/ # architecture diagrams, thesis plan, evaluation docs
└── README.md

---

## 🔹 Evaluation Scenarios (S1–S5)

| ID | Scenario | Purpose |
|----|-----------|----------|
| **S1** | Cloud → Pipeline CI/CD Baseline | Measure build-test-push TTD, CFR, DF metrics using GitHub Actions + GHCR. |
| **S2** | Pipeline → Edge Deployment | OTA deployment to edge devices (Raspberry Pi / Jetson) with latency & integrity metrics. |
| **S3** | Rollback & Hotfix Resilience | Fault injection → manual recovery → measure MTTD & MTTR baselines. |
| **S4** | Security & PQC Validation | Validate update authenticity using NIST PQC algorithms (Dilithium / SPHINCS+). |
| **S5** | Explainability & Human-in-the-Loop | Measure approval latency (AL) and audit completeness (ACR) in manual decisions. |

---

## ⚙️ Tech Stack
- **CI/CD:** GitHub Actions + GitHub App authentication (tibdex/github-app-token)  
- **Registry:** GitHub Container Registry (GHCR)  
- **Edge:** Docker / Docker Compose on Raspberry Pi or Jetson Nano  
- **Monitoring:** Prometheus + Grafana (Loki for logs)  
- **Security:** Post-Quantum Crypto validation (FIPS 203–205 – Dilithium / SPHINCS+)  
- **Explainability:** Structured JSON logs + Markdown / PDF XAI reports  
- **Language:** Python 3.11 / FastAPI / pytest  

---

## 🧩 Metrics Collected
| Category | Metric | Description |
|-----------|---------|-------------|
| Operational | **TTD**, **CFR**, **DF** | Time-to-Deploy, Change Failure Rate, Deployment Frequency |
| Resilience | **MTTD**, **MTTR** | Mean Time to Detect / Recover failures |
| Security | **TTV**, **VSR**, **FDR** | PQC verification time & success rates |
| Explainability | **AL**, **ACR** | Approval Latency & Audit Completeness Rate |

---

## 📈 Timeline
| Month | Focus | Deliverable |
|:--:|--|--|
| **1** | Baseline & Metrics | Initial CI/CD pipelines (S1) + first measurements |
| **2** | Baseline Consolidation | Statistical report + stability analysis |
| **3** | Agent Development | Reasoning, Explainability, and PQC modules |
| **4** | Evaluation | Quantitative Baseline vs Agent comparison |
| **5** | Optimization & Presentation | Final PoC demo + thesis submission |

---

## 🚀 How to Run the Baseline (S1)

> ⚙️ All required secrets (`APP_ID`, `APP_INSTALLATION_ID`, `APP_PRIVATE_KEY`) are already configured in this repository.

1. **Push any update** under `services/app/` → the `S1 CI/CD Baseline` workflow triggers automatically.  
2. **Watch execution** in **Actions → S1 CI/CD Baseline**.  
3. **Artifacts** with metrics appear under the workflow run (download `metrics/s1_s2_results.csv`).  

---

## 🧠 Next Steps
- Implement **S2** (Edge deployment and OTA bundle simulation).  
- Extend to **S3–S5** with rollback tests, PQC validation scripts, and manual approvals.  
- Begin **agent/core** development (Month 3): reasoning engine + explainability reports.  

---

## 📜 License
Released under the **MIT License**.  
© 2025 CognitiveOps – All rights reserved.

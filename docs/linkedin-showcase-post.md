# LinkedIn showcase post draft

> Use this as-is or tweak the tone. Suggested hashtags included at the end.

---

After 18 months of evenings-and-weekends research, I’m finally sharing my MSc thesis project in public.

**CogniOps** — a bounded-autonomy cognitive AI agent for resilient DevSecOps to edge environments.

Think of it as a safety-first AI teammate: it watches CI/CD, edge OTA, resilience, PQC and explainability signals, but it can only recommend or execute a small, hardcoded set of actions. No free-form changes. No structural edits. Every decision goes through deterministic guardrails (OPA policies + PQC validation) before anything touches infrastructure.

The stack: Python 3.12, FastAPI, Pydantic v2, Google ADK, Vertex AI Gemini 2.0 Flash, Terraform on GCP, BigQuery for evaluation, OPA for policy guardrails, liboqs for post-quantum crypto validation.

Two things I’m especially proud of:
- A deterministic substrate (baseline scenarios S1–S5, SS1–SS2) that never sees an LLM call.
- A 2-axis evaluation framework that measures both technical correctness *and* the operational impact of agent decisions.

Code, architecture docs, evaluation plan and the v0.1.0-alpha release are all open:
https://github.com/CognitiveOps/cogniops-resilient-devsecops

Big thanks to my supervisor Ioannis Kachris for keeping me honest on the rigour side.

If you’re working on AI agents in production — especially around safety boundaries, observability or edge ops — I’d love your feedback.

---

**Suggested hashtags:**
#AIAgents #DevSecOps #GoogleADK #VertexAI #OPA #PostQuantumCryptography #Terraform #MLOps #EdgeComputing #MScThesis #CognitiveAI

---

**Notes for posting:**
- Best posting windows (CET): Tue–Thu, 08:00–09:00 or 17:00–18:00.
- Tag supervisor if he is on LinkedIn; otherwise mention him in the comments.
- Consider adding the architecture diagram from README.md as a single image carousel slide.

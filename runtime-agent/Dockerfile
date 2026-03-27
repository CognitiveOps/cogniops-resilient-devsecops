# ── runtime-agent  Phase 0 ──
# Build context: repo root (docker build -f runtime-agent/Dockerfile .)

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (cache-friendly layer)
COPY runtime-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY runtime-agent/ .

# Copy baseline modules needed at runtime
COPY baseline/__init__.py baseline/__init__.py
COPY baseline/explainability/ baseline/explainability/
COPY baseline/security/ baseline/security/

# Cloud Run expects port 8080
EXPOSE 8080

# Run with uvicorn (single worker is fine for Phase 0)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]

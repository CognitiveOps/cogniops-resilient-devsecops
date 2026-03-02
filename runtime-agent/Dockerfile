# ── runtime-agent  Phase 0 ──
# Multi-stage build: lean production image

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies first (cache-friendly layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run expects port 8080
EXPOSE 8080

# Run with uvicorn (single worker is fine for Phase 0)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]

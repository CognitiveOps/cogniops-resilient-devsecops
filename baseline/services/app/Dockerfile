FROM python:3.11-slim

# Saner Python defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy deps first (better layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# App code
COPY app.py /app/app.py

# Create non-root user
RUN useradd -m appuser
USER appuser

EXPOSE 8080

# Healthcheck without curl (pure Python)
HEALTHCHECK --interval=10s --timeout=3s --retries=12 CMD \
  python - <<'PY' || exit 1
import urllib.request, json
try:
    with urllib.request.urlopen("http://127.0.0.1:8080/status", timeout=2) as r:
        data = json.loads(r.read().decode())
        assert data.get("ok") is True
except Exception:
    raise SystemExit(1)
PY

# Run server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

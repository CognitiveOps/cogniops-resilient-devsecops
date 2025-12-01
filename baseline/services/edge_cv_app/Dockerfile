FROM python:3.11-slim

# For OpenCV: basic libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=2s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/status')" || exit 1

CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8080"]


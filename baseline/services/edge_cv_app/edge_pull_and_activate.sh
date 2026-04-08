#!/usr/bin/env bash
set -euo pipefail

MANIFEST_JSON="$1"     # path to ota_*.json
REGION="${2:-}"
PROJECT_ID="${3:-}"

# 1) verify manifest checksum if .sha256 present
if [ -f "${MANIFEST_JSON}.sha256" ]; then
  sha256sum -c "${MANIFEST_JSON}.sha256"
fi

# 2) read image + digest from manifest
IMG=$(jq -r '.image // empty' "${MANIFEST_JSON}")
DIGEST=$(jq -r '.digest // empty' "${MANIFEST_JSON}")

echo "Manifest image : ${IMG:-<empty>}"
echo "Manifest digest: ${DIGEST:-<empty>}"

if [ -z "$IMG" ]; then
  echo "ERROR: manifest.image is empty – cannot continue"
  exit 1
fi

# 3) optional: configure docker for the registry host inferred by IMG
REG_HOST=$(echo "$IMG" | cut -d'/' -f1)
if [ -n "$REG_HOST" ]; then
  echo "Configuring docker auth for registry: $REG_HOST"
  gcloud auth configure-docker "$REG_HOST" -q || true
fi

# 4) pull by digest if present, else by tag (less safe but avoids invalid ref)
if [ -n "$DIGEST" ]; then
  echo "Pulling immutable ref: ${IMG}@${DIGEST}"
  docker pull "${IMG}@${DIGEST}"
  FINAL_REF="${IMG}@${DIGEST}"
else
  echo "WARN: digest missing in manifest – pulling by tag only"
  docker pull "${IMG}"
  FINAL_REF="${IMG}"
fi

# 5) unique container name & port per concurrent run (self-hosted runners share one Docker daemon)
CONTAINER_NAME="edge_cv_app_${GITHUB_RUN_ID:-$$}"
HOST_PORT="${EDGE_HOST_PORT:-0}"
# pick a random free port if not specified and default 0 would not work for health checks
if [ "$HOST_PORT" = "0" ]; then
  HOST_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("",0)); print(s.getsockname()[1]); s.close()')
fi

docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# 6) run new container
# Defaults match S2 semantics (MODE=real, FAIL_MODE=0). S3/SS2 may override via env vars.
EDGE_MODE="${EDGE_MODE:-real}"
EDGE_FAIL_MODE="${EDGE_FAIL_MODE:-0}"
EDGE_HEALTH_CHECK="${EDGE_HEALTH_CHECK:-1}"
S3_ENV_VARS=(
  S3_NET_FAIL_P
  S3_NET_BURST_PROB
  S3_CPU_DROP_FACTOR
  S3_CPU_SPIKE_LAMBDA
  S3_CAM_FAIL_P
  S3_MODEL_BASE_FAIL_P
  S3_MODEL_GROWTH
  S3_DISK_TIME_TO_FULL
  S3_DISK_BASE_FAIL_P
  S3_WRONG_RETRY_INTERVAL
  S3_WRONG_FAIL_WINDOW
  S3_WRONG_RETRY_SUCCESS_P
)
EXTRA_ENVS=()
for var in "${S3_ENV_VARS[@]}"; do
  if [ -n "${!var:-}" ]; then
    EXTRA_ENVS+=(-e "${var}=${!var}")
  fi
done
docker run -d --restart=no \
  --name "$CONTAINER_NAME" \
  -p "${HOST_PORT}:8080" \
  -e MODE="${EDGE_MODE}" \
  -e FAIL_MODE="${EDGE_FAIL_MODE}" \
  "${EXTRA_ENVS[@]}" \
  "$FINAL_REF"

# 7) health probe
cleanup() { docker rm -f "$CONTAINER_NAME" 2>/dev/null || true; }
trap cleanup EXIT

if [ "${EDGE_HEALTH_CHECK}" = "0" ]; then
  echo "health check skipped (EDGE_HEALTH_CHECK=0)"
  exit 0
fi
for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${HOST_PORT}/status" >/dev/null; then
    echo "healthy"
    exit 0
  fi
  sleep 2
done

echo "not healthy; container logs:"
docker logs "$CONTAINER_NAME" || true
exit 1

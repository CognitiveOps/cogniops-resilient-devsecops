#!/usr/bin/env bash
set -euo pipefail

MANIFEST_JSON="$1"     # path to ota_*.json
REGION="${2:-}"
PROJECT_ID="${3:-}"

# verify manifest checksum if .sha256 present
if [ -f "${MANIFEST_JSON}.sha256" ]; then
  sha256sum -c "${MANIFEST_JSON}.sha256"
fi

IMG=$(jq -r '.image' "${MANIFEST_JSON}")
DIGEST=$(jq -r '.digest' "${MANIFEST_JSON}")

# optional: configure docker for Artifact Registry if private
if [ -n "${REGION}" ] && [ -n "${PROJECT_ID}" ]; then
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" -q || true
fi

# pull by digest for immutability
docker pull "${IMG}@${DIGEST}"
# stop old
docker rm -f edge_cv_app || true
# run new
docker run -d --restart=always --name edge_cv_app -p 8080:8080 "${IMG}@${DIGEST}"

# health probe
for i in {1..20}; do
  if curl -fsS http://127.0.0.1:8080/status >/dev/null; then
    echo "healthy"; exit 0
  fi
  sleep 2
done
echo "not healthy"; exit 1

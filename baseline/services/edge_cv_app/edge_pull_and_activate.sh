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

# 4) pull by digest if υπάρχει, αλλιώς μόνο με tag (λιγότερο ασφαλές αλλά αποφεύγει invalid ref)
if [ -n "$DIGEST" ]; then
  echo "Pulling immutable ref: ${IMG}@${DIGEST}"
  docker pull "${IMG}@${DIGEST}"
  FINAL_REF="${IMG}@${DIGEST}"
else
  echo "WARN: digest missing in manifest – pulling by tag only"
  docker pull "${IMG}"
  FINAL_REF="${IMG}"
fi

# 5) stop old container
docker rm -f edge_cv_app || true

# 6) run new container (explicitly force real mode / no faults for S2 baseline)
docker run -d --restart=always \
  --name edge_cv_app \
  -p 8080:8080 \
  -e MODE=real \
  -e FAIL_MODE=0 \
  "$FINAL_REF"

# 7) health probe
for i in {1..20}; do
  if curl -fsS http://127.0.0.1:8080/status >/dev/null; then
    echo "healthy"
    exit 0
  fi
  sleep 2
done

echo "not healthy; container logs:"
docker logs edge_cv_app || true
exit 1

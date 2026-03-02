#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# test_publish_runtime_event.sh
#
# Publishes a manual_test_event to the runtime-events-v1 Pub/Sub topic.
# Uses the event envelope from docs/runtime-event-contract.md.
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - GCP_PROJECT_ID env var set (or passed as $1)
#
# Usage:
#   ./scripts/test_publish_runtime_event.sh [PROJECT_ID]
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
TOPIC="runtime-events-v1"
EVENT_ID="test-$(date +%s)-$(openssl rand -hex 4)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: GCP_PROJECT_ID not set. Pass as argument or export GCP_PROJECT_ID."
  exit 1
fi

# Event envelope per runtime-event-contract.md § Example Event
EVENT_JSON=$(cat <<EOF
{
  "event_id": "${EVENT_ID}",
  "event_type": "manual_test_event",
  "occurred_at": "${TIMESTAMP}",
  "source": "test-publisher",
  "context": {
    "run_id": "run-integration-test",
    "scenario_id": "S3",
    "stage": "deploy",
    "status": "fail",
    "severity": "medium"
  }
}
EOF
)

echo "Publishing to projects/${PROJECT_ID}/topics/${TOPIC}..."
echo "Event ID: ${EVENT_ID}"
echo ""

gcloud pubsub topics publish "${TOPIC}" \
  --project="${PROJECT_ID}" \
  --message="${EVENT_JSON}"

echo ""
echo "✓ Published event_id=${EVENT_ID} to ${TOPIC}"
echo ""
echo "To verify the decision row:"
echo "  ./scripts/verify_runtime_decision.sh ${PROJECT_ID} ${EVENT_ID}"

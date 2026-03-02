#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# verify_runtime_decision.sh
#
# Queries agent_metrics.runtime_decisions for a specific event_id
# and verifies the row has the correct Phase 0 decision values.
#
# Prerequisites:
#   - gcloud / bq CLI authenticated
#   - GCP_PROJECT_ID env var set (or passed as $1)
#   - EVENT_ID passed as $2 (from test_publish_runtime_event.sh output)
#
# Usage:
#   ./scripts/verify_runtime_decision.sh [PROJECT_ID] [EVENT_ID]
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
EVENT_ID="${2:-}"
DATASET="agent_metrics"
TABLE="runtime_decisions"
MAX_RETRIES=10
RETRY_INTERVAL=5

if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: GCP_PROJECT_ID not set. Pass as first argument or export GCP_PROJECT_ID."
  exit 1
fi

if [[ -z "$EVENT_ID" ]]; then
  echo "ERROR: EVENT_ID not provided. Pass as second argument."
  echo "Usage: $0 <PROJECT_ID> <EVENT_ID>"
  exit 1
fi

QUERY="
SELECT
  event_id,
  event_type,
  decision,
  decision_executed,
  mode,
  rationale,
  agentops_trace_id,
  processed_at
FROM \`${PROJECT_ID}.${DATASET}.${TABLE}\`
WHERE event_id = '${EVENT_ID}'
LIMIT 1
"

echo "Querying ${PROJECT_ID}.${DATASET}.${TABLE} for event_id=${EVENT_ID}..."
echo "(will retry up to ${MAX_RETRIES} times, ${RETRY_INTERVAL}s apart)"
echo ""

for i in $(seq 1 "$MAX_RETRIES"); do
  RESULT=$(bq query \
    --project_id="${PROJECT_ID}" \
    --use_legacy_sql=false \
    --format=json \
    "${QUERY}" 2>/dev/null || echo "[]")

  # Check if we got a row back
  ROW_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [[ "$ROW_COUNT" -gt 0 ]]; then
    echo "✓ Row found on attempt ${i}/${MAX_RETRIES}"
    echo ""
    echo "$RESULT" | python3 -m json.tool
    echo ""

    # Verify Phase 0 invariants
    DECISION=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['decision'])")
    EXECUTED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['decision_executed'])")
    MODE=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['mode'])")

    PASS=true

    if [[ "$DECISION" != "NO_OP" ]]; then
      echo "✗ FAIL: decision='${DECISION}' (expected 'NO_OP')"
      PASS=false
    fi

    if [[ "$EXECUTED" != "False" && "$EXECUTED" != "false" ]]; then
      echo "✗ FAIL: decision_executed='${EXECUTED}' (expected false)"
      PASS=false
    fi

    if [[ "$MODE" != "shadow" ]]; then
      echo "✗ FAIL: mode='${MODE}' (expected 'shadow')"
      PASS=false
    fi

    if [[ "$PASS" == "true" ]]; then
      echo "✓ All Phase 0 invariants verified:"
      echo "  decision       = NO_OP"
      echo "  executed       = false"
      echo "  mode           = shadow"
      exit 0
    else
      exit 1
    fi
  fi

  echo "  Attempt ${i}/${MAX_RETRIES}: no row yet, retrying in ${RETRY_INTERVAL}s..."
  sleep "$RETRY_INTERVAL"
done

echo ""
echo "✗ FAIL: No row found for event_id=${EVENT_ID} after ${MAX_RETRIES} attempts."
echo "  Check Cloud Run logs: gcloud run services logs read runtime-agent --project=${PROJECT_ID} --limit=20"
echo "  Check DLQ: gcloud pubsub subscriptions pull runtime-events-v1-dlq-sub --project=${PROJECT_ID} --auto-ack --limit=5"
exit 1

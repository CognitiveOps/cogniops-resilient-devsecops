#!/usr/bin/env bash
# Publish a test event to Pub/Sub and verify the runtime agent processes it.
# Usage: ./scripts/smoke_test_runtime.sh
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
TOPIC="runtime-events-v1"

EVENT_ID="smoke-$(date +%s)"
EVENT=$(cat <<EOF
{
  "event_id": "$EVENT_ID",
  "event_type": "manual_test_event",
  "occurred_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source": "smoke-test",
  "context": {"status": "testing", "scenario_id": "S1", "run_id": "$EVENT_ID"}
}
EOF
)

echo "Publishing test event: $EVENT_ID"
gcloud pubsub topics publish "$TOPIC" \
  --project="$PROJECT_ID" \
  --message="$EVENT"

echo "Waiting 15s for pipeline..."
sleep 15

echo "Querying BQ for decision row..."
bq query --use_legacy_sql=false --project_id="$PROJECT_ID" \
  "SELECT event_id, decision, mode, decision_executed, agentops_trace_id
   FROM agent_metrics.runtime_decisions
   WHERE event_id = '$EVENT_ID'
   LIMIT 1"

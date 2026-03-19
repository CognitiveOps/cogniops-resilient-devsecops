-- S1: Change Failure Rate (CFR) per variant
-- CFR = failed deploys / total deploys
--
-- Parameters:
--   @project: GCP project ID
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COUNT(*) AS total_deploys,
  COUNTIF(status = 'failure') AS failed_deploys,
  SAFE_DIVIDE(COUNTIF(status = 'failure'), COUNT(*)) AS cfr,
  COUNTIF(status = 'success') AS successful_deploys
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = 's1'
  AND stage = 's1_health'
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant
ORDER BY variant;

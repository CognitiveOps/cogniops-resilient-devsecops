-- S2: Deployment Success Rate (DSR) per variant
-- DSR = successful OTA activations / total activations
--
-- Parameters:
--   @project: GCP project ID
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COUNT(*) AS total_activations,
  COUNTIF(status = 'success') AS successful_activations,
  SAFE_DIVIDE(COUNTIF(status = 'success'), COUNT(*)) AS dsr,
  AVG(duration_sec) AS mean_tdl,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(50)] AS median_tdl,
  STDDEV(duration_sec) AS stddev_tdl
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = 's2'
  AND stage = 's2_activate'
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant
ORDER BY variant;

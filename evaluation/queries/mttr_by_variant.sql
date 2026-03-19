-- S3: Mean Time to Recover (MTTR) per variant
-- MTTR = time from rollback trigger to healthy recovery
--
-- Parameters:
--   @project: GCP project ID
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COALESCE(JSON_VALUE(labels, '$.fault_type'), 'unknown') AS fault_type,
  COUNT(*) AS n,
  AVG(duration_sec) AS mean_mttr,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(50)] AS median_mttr,
  STDDEV(duration_sec) AS stddev_mttr,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(5)] AS p5_mttr,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(95)] AS p95_mttr
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = 's3'
  AND stage = 's3_recover_edge'
  AND status = 'success'
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant, fault_type
ORDER BY variant, fault_type;

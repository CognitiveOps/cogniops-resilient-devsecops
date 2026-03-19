-- S1: Time to Deploy (TTD) per variant
-- TTD = duration from commit to healthy deployment (s1_health stage)
--
-- Parameters:
--   @project: GCP project ID
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COUNT(*) AS n,
  AVG(duration_sec) AS mean_ttd,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(50)] AS median_ttd,
  STDDEV(duration_sec) AS stddev_ttd,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(5)] AS p5_ttd,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(95)] AS p95_ttd,
  MIN(duration_sec) AS min_ttd,
  MAX(duration_sec) AS max_ttd
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = 's1'
  AND stage = 's1_health'
  AND status = 'success'
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant
ORDER BY variant;

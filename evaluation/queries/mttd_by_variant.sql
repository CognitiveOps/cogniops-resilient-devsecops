-- S3/SS2: Mean Time to Detect (MTTD) per variant
-- MTTD = time from fault injection to detection
--
-- S3 uses s3_detect_edge stage, SS2 uses ss2_detect stage.
-- Both store metric in metrics JSON (ttd_sample_sec / mttd_sample_sec).
--
-- Parameters:
--   @project: GCP project ID
--   @scenario: 's3' or 'ss2'
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COALESCE(JSON_VALUE(labels, '$.fault_type'), 'unknown') AS fault_type,
  COUNT(*) AS n,
  AVG(duration_sec) AS mean_mttd,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(50)] AS median_mttd,
  STDDEV(duration_sec) AS stddev_mttd,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(5)] AS p5_mttd,
  APPROX_QUANTILES(duration_sec, 100)[OFFSET(95)] AS p95_mttd
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = @scenario
  AND stage IN ('s3_detect_edge', 'ss2_detect')
  AND status = 'success'
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant, fault_type
ORDER BY variant, fault_type;

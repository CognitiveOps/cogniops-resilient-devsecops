-- S5/SS2: Approval Latency (AL) per variant
-- AL = t_approved - t_recommend
--
-- Parameters:
--   @project: GCP project ID
--   @scenario: 's5' or 'ss2'
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COUNT(*) AS n,
  AVG(CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64)) AS mean_al,
  APPROX_QUANTILES(
    CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64), 100
  )[OFFSET(50)] AS median_al,
  STDDEV(CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64)) AS stddev_al,
  APPROX_QUANTILES(
    CAST(JSON_VALUE(metrics, '$.al_sec') AS FLOAT64), 100
  )[OFFSET(95)] AS p95_al
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = @scenario
  AND stage IN ('s5_approve', 's5_final')
  AND status = 'success'
  AND JSON_VALUE(metrics, '$.al_sec') IS NOT NULL
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant
ORDER BY variant;

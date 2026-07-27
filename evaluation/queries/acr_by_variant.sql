-- S5/SS1/SS2: Audit Completeness Rate (ACR) per variant
-- ACR = complete audit records / total actions
--
-- Parameters:
--   @project: GCP project ID
--   @scenario: 's5', 'ss1', or 'ss2'
--   @start_ts: evaluation window start (TIMESTAMP)
--   @end_ts: evaluation window end (TIMESTAMP)

SELECT
  COALESCE(JSON_VALUE(labels, '$.variant'), 'baseline') AS variant,
  COUNT(*) AS n,
  AVG(CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)) AS mean_acr,
  APPROX_QUANTILES(
    CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64), 100
  )[OFFSET(50)] AS median_acr,
  MIN(CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)) AS min_acr,
  STDDEV(CAST(JSON_VALUE(metrics, '$.acr') AS FLOAT64)) AS stddev_acr
FROM `{project}.agent_metrics.runs`
WHERE scenario_id = @scenario
  AND stage IN ('s5_final', 'ss1_final')
  AND status = 'success'
  AND JSON_VALUE(metrics, '$.acr') IS NOT NULL
  AND t_end BETWEEN @start_ts AND @end_ts
GROUP BY variant
ORDER BY variant;

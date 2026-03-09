---
description: "Implement real anomaly detection in Perception tool. Z-score, thresholds, BQ historical baselines. Pure Python, no LLM."
agent: "agent"
---

# Step 2: Perception — Real Anomaly Detection

Read first:
- [Runtime agent instructions](../instructions/runtime-agent.instructions.md)
- [Existing perception stub](../../runtime-agent/perception/handler.py)
- [ADK perception tool](../../runtime-agent/agent/tools/perception_tool.py) (from Step 1)
- [Event contract](../../docs/runtime-event-contract.md)

## Task

Replace hardcoded severity=0.5, risk_score=0.5 with real anomaly detection. This is **pure Python + BigQuery** — NO LLM involvement.

## Implementation

### 1. Historical Baselines (`agent/tools/perception_tool.py`)

Query `agent_metrics.runs` for rolling averages per scenario:
```sql
SELECT scenario_id,
       AVG(duration_sec) as avg_duration,
       STDDEV(duration_sec) as stddev_duration,
       COUNT(*) as sample_count
FROM `agent_metrics.runs`
WHERE t_end > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND scenario_id = @scenario
  AND status = 'success'
GROUP BY scenario_id
```

### 2. Anomaly Detection Methods

**Z-score detection:**
```python
def z_score_check(value: float, mean: float, stddev: float) -> float:
    if stddev == 0:
        return 0.0
    return abs(value - mean) / stddev
```

**Threshold detection per scenario:**
| Scenario | Metric | Warning (severity 0.5-0.7) | Critical (severity 0.8-1.0) |
|----------|--------|---------------------------|----------------------------|
| S1 | TTD | >180s | >300s |
| S1 | CFR | >10% | >25% |
| S3 | MTTD | >60s | >120s |
| S3 | MTTR | >120s | >300s |
| S2 | DSR | <95% | <85% |
| S4 | FDR | <90% | <70% |

### 3. Severity Scoring
Combine z-score + threshold into final severity (0-1):
```python
severity = max(z_score_severity, threshold_severity)
risk_score = severity * context_weight  # weight by scenario criticality
```

### 4. Output
Return enhanced `AnomalyOutput` with real scores instead of hardcoded 0.5.

### 5. Tests
- `tests/test_perception_real.py`
- Mock BQ client with fixture data from `tests/fixtures/mock_bq_baselines.json`
- Test z-score detection: normal value → low severity, outlier → high severity
- Test threshold detection: within limits → ok, exceeds → warning/critical
- Test combined scoring
- Test graceful degradation: empty BQ results → fallback to threshold-only

## Constraints
- DETERMINISTIC — no LLM, no randomness
- Graceful degradation: if BQ query fails → use threshold-only detection
- Do not modify existing `perception/handler.py` (keep for backward compat)
- New logic goes in `agent/tools/perception_tool.py`

## Post-Implementation (MANDATORY)
After completing the code changes:
1. Update `README.md` § "🤖 AI Agent Architecture" to reflect:
   - Anomaly detection method (z-score + thresholds)
   - Per-scenario threshold table
   - BQ baseline query pattern
2. Update `README.md` § "📊 Implementation Progress" — mark Step 2 as ✅
3. Update `docs/system-guardrails.md` if any new safety-relevant behaviour was added

# Metrics and dashboard

## Backend

| Endpoint | Purpose |
| --- | --- |
| `GET /admin/metrics?range=15m\|1h\|24h\|7d` | Overview totals, per-provider rows, time series, health. |
| `GET /admin/metrics/stream` | Server-sent events with a snapshot every two seconds. |
| `GET /admin/events?limit=N` | Recent switch, config and breaker events. |
| `GET /metrics` | Prometheus exposition of success rate and inflight gauges. |

## Per-provider columns

Every recorded call stores provider, model, success flag, error class, latency, prompt/completion/reasoning tokens, cached tokens, estimated cost and the number of switches that preceded it.

## Dashboard

The React dashboard polls `/admin/metrics` for the selected range and renders:

- A KPI row for calls, success rate, prompt and completion tokens, cache hit rate and estimated cost.
- A traffic chart of calls and failures per time bucket.
- One card per provider with circuit state, success ring, p50/p95 latency, cost per thousand prompt tokens, cache hit rate and a concurrency gauge.
- A detail table with token and cost breakdowns.

## Cost model

Cost per call is

```
(prompt_not_cached * input_price + cached_tokens * input_price * 0.1 + completion * output_price) / 1e6
  * cost_coefficient * window_multiplier
```

prices are per million tokens and are declared per provider. Missing prices yield zero cost.

## Retention

Rollups are written to SQLite under the data directory. The dashboard queries trailing windows only; prune the database file to reset history.

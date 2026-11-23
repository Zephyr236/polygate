# Routing

## Score

Each eligible provider receives a weighted score:

```
score = w_success * success_rate
      + w_speed * speed
      + w_cost * inverse_cost
      + w_cache * cache_hit_rate
```

- `success_rate` is an exponential moving average over recorded calls.
- `speed` is `min(1, speed_target_ms / ewma_latency_ms)`; an untried provider starts at 1.
- `inverse_cost` is `1 / (cost_coefficient * window_multiplier)`; it is rescaled so the cheapest current candidate equals 1.
- `cache_hit_rate` tracks the share of calls that reported cached prompt tokens.

Candidates are ordered by `(priority, -score)`, so a lower `priority` number is always tried first within its tier.

## Hard filters

A provider is excluded before scoring when it is disabled, outside its active windows, missing from the health registry, or currently cooling down after repeated failures.

## Failover

- Within one provider, retryable failures are retried `retry.attempts` times with exponential backoff and jitter.
- After the retries are exhausted the scheduler excludes that provider and selects the next candidate.
- At most `max_switches` provider switches happen per request; the final error aggregates every attempt with its normalized error class.

## Presets

Set `routing.weights` in the TOML seed to bias the pool:

| Preset | success | speed | cost | cache |
| --- | --- | --- | --- | --- |
| Reliability first | 0.6 | 0.2 | 0.1 | 0.1 |
| Latency first | 0.3 | 0.5 | 0.1 | 0.1 |
| Cost first | 0.2 | 0.15 | 0.55 | 0.1 |
| Cache friendly | 0.3 | 0.2 | 0.15 | 0.35 |

## Lanes

`lanes` multiplies the concurrency slots a provider exposes. Providers that rate limit per session (for example a session header scoped bucket) gain a parallel slot per lane, with a distinct session id per lane when `session_mode = "uuid-per-lane"`.

## Concurrency

`max_concurrency` caps slot use per lane. Saturation is a soft exclusion: the provider is skipped for that request rather than queued, so latency-sensitive traffic is not parked behind a full channel.

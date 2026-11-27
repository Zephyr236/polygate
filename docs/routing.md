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

Candidates are ordered by `(priority, -score)` by default, so a lower `priority` number is tried first.
A client key with `respect_priority = false` orders its allowed providers by score alone, so its
per-key weights can cross global priority tiers.

## Generated keys and tiers

Keys issued in the console carry a tier and a provider allowlist. `premium` weights success and
speed most heavily and respects global priority; `standard` uses the global weights; `economy`
weights cost most heavily and sets `respect_priority = false`, so it may cross global priority tiers.
A generated key can never route outside its allowlist, even if other providers score higher.

## Per-key policy

A `[[client_key]]` narrows the candidate pool to `allowed_providers` and may override the global
`weights` with `[client_key.weights]`. Authentication resolves the key to a `ClientPolicy`; the
scheduler filters providers before scoring and uses the key's weights for that request. A client
key must list at least one provider; only the legacy `PROXY_API_KEY` policy spans every provider.
`respect_priority` defaults to `true`; set it to `false` when the key's weights should override
global tier order. `POST /admin/simulate` accepts `api_key_id` to explain the same filtered ranking.
The circuit breaker, retries, time windows and concurrency limits remain global provider state.

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

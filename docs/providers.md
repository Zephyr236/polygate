# Providers

Providers are data. Adding a channel means adding a configuration entry, not code.

## Quirk model

| Field | Values | Purpose |
| --- | --- | --- |
| `protocol` | `openai`, `anthropic` | Wire format used by the upstream. |
| `auth_style` | `bearer`, `x-api-key`, `both` | Which credential header to send. |
| `session_header` | header name or null | Header carrying a per-request or per-lane session id. |
| `session_mode` | `none`, `uuid-per-request`, `uuid-per-lane` | How the session id is generated. |
| `lanes` | integer | Parallel session buckets. |
| `max_concurrency` | integer | Slots per lane. |
| `max_tokens_min` | integer | Floor applied to `max_tokens` requests. |
| `stream_usage` | `include_usage`, `message_delta`, `none` | Where the upstream reports usage while streaming. |
| `error_rules` | list | Map payload paths or text fragments onto normalized error classes. |
| `active_windows` | list | UTC windows restricting traffic with an optional cost multiplier. |
| `cost_coefficient` | float | User-defined relative price weight. |

## Error normalization

Every failure becomes one of `rate_limited`, `concurrency_limited`, `auth_error`, `model_not_found`, `client_error`, `server_error`, `timeout`, or `transport_error`. Rules are evaluated first, then status-based defaults. Only retryable classes consume retry budget.

## Reference channels

The repository ships examples for channels measured during development:

- An OpenAI-compatible channel with a hard per-key concurrency cap that answers `tier_limit_exceeded` when saturated.
- An Anthropic-compatible channel that requires a session header on every call and rate limits per session.
- A low-cost, high-latency channel used to exercise timeout and breaker behaviour.

See `providers.example.toml` for the exact seed configuration.

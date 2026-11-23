# API

## Proxy

### `POST /v1/chat/completions`

OpenAI-compatible chat completions. Supports `stream: true`, which emits OpenAI SSE chunks followed by a usage chunk and `[DONE]`.

### `POST /v1/messages`

Anthropic-compatible messages. Streaming emits `message_start`, `content_block_*`, `message_delta` and `message_stop` events.

Both endpoints return `502` with a `providers_unavailable` envelope when every candidate fails:

```json
{
  "error": {
    "message": "all provider candidates failed",
    "type": "providers_unavailable",
    "attempts": [
      { "provider_id": "amr", "error_class": "concurrency_limited", "retryable": true, "detail": "..." }
    ]
  }
}
```

## Admin

All admin routes require `Authorization: Bearer $ADMIN_TOKEN`.

| Route | Method | Purpose |
| --- | --- | --- |
| `/admin/providers` | GET | List providers plus health snapshots. |
| `/admin/providers` | PUT | Replace the provider pool. |
| `/admin/metrics` | GET | Aggregates for a range. |
| `/admin/metrics/stream` | GET | SSE snapshot every two seconds. |
| `/admin/events` | GET | Recent operational events. |
| `/admin/simulate` | POST | Score breakdown without calling upstreams. |

## Health

| Route | Purpose |
| --- | --- |
| `/healthz` | Liveness. |
| `/readyz` | Usable providers. |
| `/metrics` | Prometheus text. |

## Status codes

| Code | Meaning |
| --- | --- |
| 200 | Success. |
| 401 | Missing or invalid credential. |
| 400 | Invalid request body or unknown range. |
| 502 | All providers failed. |
| 503 | Admin token not configured. |

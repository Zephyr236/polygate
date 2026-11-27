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

### Caller keys

`/v1/*` accepts a bearer token or `x-api-key`. The legacy `PROXY_API_KEY` grants access to every
provider with the global routing weights. A configured `[[client_key]]` instead grants only its
`allowed_providers` and applies its optional per-key `weights`. An unknown or missing key is `401`.
An unprovisioned `[[client_key]]` is inactive: its requests get `401`, while `PROXY_API_KEY` and
admin traffic keep working; startup fails when no usable proxy credential exists. Admin-only
startup is not supported because admin routes cannot repair credentials.

## Admin

The management UI uses a first-run admin password and an expiring browser session. `ADMIN_TOKEN`
remains an optional bearer credential for API automation; the UI never asks for it.

| Route | Method | Purpose |
| --- | --- | --- |
| `/admin/clients` | GET | List static caller keys, allowlists and key-presence flags. |
| `/admin/playground` | POST | Run one console chat with the legacy all-provider policy. |
| `/admin/api-keys` | GET | List generated caller key metadata (never the secret). |
| `/admin/api-keys` | POST | Generate a key; returns its plaintext token once. |
| `/admin/api-keys/{id}` | DELETE | Revoke a generated key. |
| `/admin/providers` | GET | List providers plus health snapshots. |
| `/admin/providers` | PUT | Replace the provider pool. |
| `/admin/metrics` | GET | Aggregates for a range. |
| `/admin/metrics/stream` | GET | SSE snapshot every two seconds. |
| `/admin/events` | GET | Recent operational events. |
| `/admin/simulate` | POST | Score breakdown without calling upstreams; optional `api_key_id` applies that caller's allowlist and weights. |

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

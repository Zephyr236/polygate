# Architecture

polygate is a single-process ASGI gateway that fronts several DeepSeek-compatible upstream channels and exposes them through both OpenAI and Anthropic wire formats.

## Request flow

1. A client calls `/v1/chat/completions` or `/v1/messages`.
2. The matching translator in `polygate.protocols` parses the body into an `InternalRequest`.
3. `polygate.routing.scheduler` ranks eligible providers, reserves a lane, and calls the adapter.
4. `polygate.providers.base` performs the HTTP call with the provider's auth and session quirks.
5. On failure the scheduler retries within the same lane, then fails over to the next candidate.
6. Successful calls are persisted by `polygate.storage` and surfaced by `/admin/metrics`.

## Module layers

| Layer | Modules | Rule |
| --- | --- | --- |
| Composition root | `app` | May import everything; owns lifetimes. |
| HTTP surface | `api.*` | Talks to the gateway only; never reaches into storage internals. |
| Orchestration | `gateway` | Builds the scheduler, records metrics and costs. |
| Routing | `routing.*`, `metrics` | Pure ranking and health state; no HTTP awareness. |
| Upstream adapters | `providers.*` | Protocol transport, quirks, error normalization. |
| Translation | `protocols.*` | Pure request/response and SSE mapping. |
| Foundations | `config`, `config_loader`, `storage`, `protocols.base` | No dependencies on the layers above. |

These directions are enforced by `import-linter` contracts in `backend/pyproject.toml`.

## State

- `HealthRegistry` keeps per-provider success/latency moving averages, lane occupancy and a closed/open/half-open circuit.
- `MetricsStore` keeps a SQLite rollup table plus an append-only event log and persisted provider overrides.
- Provider configuration is seeded from a TOML file and can be replaced at runtime through `PUT /admin/providers`.

## Streaming

Streaming replies are emitted with the exact frame shapes of each protocol. The gateway buffers a lane's output until the attempt completes, so a provider that fails before its first token can be replaced without corrupting the client stream. Once a delivery has started, a failure is raised instead of silently switching channels.


See [architecture-review.md](architecture-review.md) for the advisory review rubric and the
metrics ratchet.

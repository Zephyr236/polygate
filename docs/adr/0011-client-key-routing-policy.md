# ADR 0011: Caller keys carry provider allowlists and routing weights

- Status: Accepted
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The gateway had one optional `PROXY_API_KEY` and one global routing policy. Different callers need
different provider pools: a cost-sensitive caller should not be routed to an expensive provider, and
a latency-sensitive caller may weight speed differently. Reusing one global policy cannot express
that without separate deployments.

## Decision

- `[[client_key]]` entries in the TOML seed define `id`, `name`, `api_key_env`,
  `allowed_providers` and optional `[client_key.weights]`.
- Authentication resolves a presented bearer/`x-api-key` credential to a `ClientPolicy`. The legacy
  `PROXY_API_KEY` remains an all-provider policy with global weights. With no configured keys the
  proxy stays open for local development; a configured key set with no active env value fails
  closed.
- The scheduler filters the provider pool by `allowed_providers` before scoring and uses the key's
  weights for that request. `respect_priority = false` lets the key rank by score across global
  priority tiers; the default keeps the global tier order. Provider health, circuits, retries, time
  windows and concurrency remain shared provider state; a key can select within them but cannot
  disable them.
- Duplicate `api_key_env` names, duplicate resolved key values, a client key using `PROXY_API_KEY`,
  a client value equal to the legacy key, and a client-key set with no provisioned env value are
  startup errors.
- `GET /admin/clients` lists key metadata and `key_configured`, never the secret value.
- `PUT /admin/providers` rejects a pool that would strand a client allowlist, and rejects a runtime
  provider credential that aliases a client key. `POST /admin/simulate` accepts `api_key_id` and
  applies that policy; without it, simulation shows the legacy/global pool.

## Consequences

- One gateway process can serve multiple caller policies without duplicating providers.
- A missing or empty `allowed_providers` list is a startup error. Only the legacy `PROXY_API_KEY`
  spans every provider.
- Per-key policies are read at process start from TOML/env. Runtime key CRUD is not added; adding it
  later needs hashed key storage and a migration.
- Metrics remain provider-level, not caller-level. Per-key cost attribution needs a separate
  schema change.
- Key rotation is an environment change plus restart, consistent with provider secrets.

## References

- `backend/src/polygate/config.py`, `backend/src/polygate/api/auth.py`,
  `backend/src/polygate/routing/scheduler.py`
- `docs/api.md`, `docs/routing.md`, `providers.example.toml`

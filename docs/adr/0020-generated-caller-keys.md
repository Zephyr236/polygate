# ADR 0020: Generated caller keys with tiers and provider allowlists

- Status: Accepted
- Date: 2026-11-27
- Deciders: polygate maintainers

## Context

Caller keys were seeded from TOML and environment variables only. There was no way to issue a key
from the console, choose its providers, or express a service level per key. The router already
supported per-key allowlists and weights, but only for statically configured principals.

## Decision

- The admin console generates caller keys under `/admin/api-keys`. The plaintext token (`pg_…`) is
  returned exactly once; SQLite stores only its SHA-256 lookup digest and a display prefix.
- Each key stores a non-empty provider allowlist and a tier: `premium`, `standard` or `economy`.
- Authentication resolves a generated key to a `ClientPolicy` before legacy/config keys. The policy
  filters the candidate pool to the allowlist and applies the tier's scheduler weights.
  `premium` favours success and respects global priority; `standard` uses the global weights;
  `economy` favours cost and may cross priority tiers.
- Revocation takes effect on the next request. Once any generated key exists, an unconfigured
  deployment no longer falls back to open mode, even if every key is later revoked.
- Static `[[client_key]]` entries and the legacy `PROXY_API_KEY` remain supported.

## Consequences

- A leaked key can be revoked without restarting or editing TOML.
- The secret cannot be recovered; lost keys are replaced, not displayed again.
- Keys are single-tier presets rather than arbitrary per-key weight vectors; custom weight vectors
  remain available through static client-key configuration.
- The console must be reachable only by the admin; generated keys grant `/v1/*` access within their
  allowlist.

## References

- `backend/src/polygate/api_keys.py`, `backend/src/polygate/api/api_keys.py`,
  `backend/src/polygate/api/auth.py`, `frontend/src/pages/ApiKeys.tsx`, `docs/routing.md`

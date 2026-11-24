# AGENTS.md

Notes for agents (human or otherwise) picking this repository up.

## Project layout

```
backend/          Python gateway: FastAPI app, routing core, upstream adapters
  src/polygate/   app, api, gateway, routing, providers, protocols, config, storage, metrics
  tests/          unit, integration, e2e (fake upstreams on loopback)
frontend/         React SPA: dashboard, provider editor, route simulation, playground
  src/            api, state, components, pages, utils
  tests/          unit, component (MSW), e2e (Playwright)
deploy/           Dockerfile (multi-stage, all-in-one) and docker-compose.yml
docs/             Architecture, routing, providers, metrics, operations, gates, frontend, API
scripts/          gate.py plus per-tool threshold readers
```

## Invariants

- Secrets live only in environment variables. Configuration references them by name through `api_key_env`; never inline a key.
- A provider that fails before emitting its first delta may be swapped; a failure after delivery must surface to the client instead of silently switching.
- Every upstream difference must be expressible as a quirk field in `ProviderConfig`. New quirks belong in `config.py` and the provider reference doc, not in adapter if-statements.
- `src/api` is a leaf in the frontend graph, `polygate.protocols` is a leaf in the backend graph. `import-linter`, `dependency-cruiser`, `semgrep` design rules and `ast-grep` structural rules enforce both.
- When you add a layer rule, prove it fires on a deliberate violation before trusting it; a no-op rule is worse than no rule. `tach` was evaluated and dropped because its rule evaluation produced no diagnostics even for its own documented layout; `import-linter`, `semgrep` and `dependency-cruiser` carry enforcement instead.
- Cost is always `cost_coefficient * window_multiplier * price(tokens)`; the dashboard and the `cost` column must agree.

## How to run gates

```sh
uv run python scripts/gate.py --backend        # lint, types, imports, tests, CRAP, security
uv run python scripts/gate.py --frontend       # eslint, prettier, tsc, deps, tests, CRAP
uv run python scripts/gate.py --docs           # required docs, config parity, links, OpenAPI
uv run python scripts/gate.py --all --mutation --e2e
```

Mutation runs are slow. Backend uses `mutmut` on the routing/provider/protocol layers; frontend uses Stryker on `src/api` and `src/utils`.

## Adding a provider

1. Append a `[[provider]]` block to `deploy/providers.toml` (or `providers.example.toml` for the shipped sample).
2. Pick `protocol`, `auth_style`, `session_mode`, `lanes`, `max_concurrency` and timeouts to match the channel's measured behaviour.
3. Add `error_rules` for any non-standard error payloads.
4. Verify with `POST /admin/simulate` and one real request through the Playground.
5. Add a fixture under `backend/tests/e2e/fake_upstream.py` if the behaviour is novel.

## Where to change what

| Task | Files |
| --- | --- |
| Scoring or weights | `backend/src/polygate/routing/scorer.py`, `docs/routing.md` |
| Circuit breaker or cooldowns | `backend/src/polygate/routing/state.py` |
| Retry and failover order | `backend/src/polygate/routing/scheduler.py` |
| Upstream headers, sessions, errors | `backend/src/polygate/providers/base.py` |
| Request/response shape | `backend/src/polygate/protocols/*.py` |
| New endpoint | `backend/src/polygate/api/*.py` plus `docs/api.md` |
| Dashboard widgets | `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/widgets.tsx` |
| Config fields | `backend/src/polygate/config.py`, then rerun `scripts/gen_config_reference.py` |
| Layer or design rules | `rules/architecture.yml`, `rules/ast-grep/`, `.dependency-cruiser.cjs` |
| Module size limits | `scripts/size_gate.py` |
| Cohesion and duplication | `scripts/cohesion_gate.py`, `.jscpd.json` |
| Property and contract tests | `backend/tests/unit/test_state_machines.py`, `backend/tests/e2e/test_contracts.py` |
| Architectural decisions | `docs/adr/` plus `docs/adr/index.md` |

## Merge policy

`main` takes pull requests only, with **0 required reviews** (single maintainer; GitHub forbids
self-approval); the aggregated `gate` and the agent `design-review` status are required. `gate` fails
on `failure`, `cancelled` and `skipped`, so a conditional job cannot pass by not running. The design
gate fails while any blocking finding or issue remains.
Force pushes, deletions and direct pushes are blocked, including for administrators
(`enforce_admins`). Rationale: [ADR 0004](docs/adr/0004-merge-policy.md) and
[ADR 0007](docs/adr/0007-protect-main.md), and [ADR 0010](docs/adr/0010-required-design-gate.md).

## Definition of done

- `scripts/gate.py --all` is green, including docs.
- New behaviour has unit tests and at least one integration or e2e case.
- Docs that describe the changed behaviour are updated in the same commit.
- A decision that changes architecture, gating or dependencies gets a new ADR linked from `docs/adr/index.md`.
- Mutation score stays at or above threshold; refactor rather than add `# pragma: no cover`.

# polygate

A self-hosted routing gateway that pools several DeepSeek V4.1 Flash compatible channels behind one stable API. Each channel keeps its own retry, concurrency, active-window, cost and priority settings; the router picks the best candidate per request, fails over automatically, and the dashboard shows exactly how every channel is performing.

## Highlights

- **Channels are data.** Add a provider with a TOML block; no code changes. Quirks (auth style, session headers, streaming usage placement, custom error payloads) are configuration.
- **Score-based routing** over success rate, latency, user-defined cost coefficient and cache hit rate, with priority tiers, retries and failover.
- **Two wire formats.** OpenAI `/v1/chat/completions` and Anthropic `/v1/messages`, streaming included.
- **Per-channel dashboard.** Calls, success, p50/p95 latency, tokens, cache hits, cost, concurrency and circuit state, with live SSE updates.
- **One-command deploy.** `docker compose -f deploy/docker-compose.yml up -d --build` serves the SPA and API on port 8080.

## Quick start

```sh
cp .env.example .env               # set ADMIN_TOKEN and the upstream keys
docker compose -f deploy/docker-compose.yml up -d --build
open http://localhost:8080         # enter ADMIN_TOKEN, then browse the dashboard
```

Local development:

```sh
cd backend && uv sync --extra dev && uv run uvicorn polygate.app:create_app --factory
cd frontend && pnpm install && pnpm dev
```

## Configuration

Providers are seeded from `POLYGATE_CONFIG` (see `providers.example.toml`) and can be edited later in the admin UI. Keys are referenced by environment variable name, never stored inline.

```toml
[[provider]]
id = "amr"
base_url = "https://amr-link.open-design.ai/v1"
model = "deepseek-v4.1-flash-eco"
api_key_env = "AMR_API_KEY"
max_concurrency = 10
max_tokens_min = 3000
```

Full field reference: [docs/config-reference.md](docs/config-reference.md).

## Routing

```
score = w_success * success_rate + w_speed * speed + w_cost * inverse_cost + w_cache * cache_hit
```

Disabled channels, channels outside their time windows, saturated channels and cooling circuits are filtered out first. Failures retry within the channel, then switch down the ranked list. Details: [docs/routing.md](docs/routing.md).

## Dashboard

`GET /admin/metrics?range=15m|1h|24h|7d` returns overview totals, a per-provider table and a time series; `GET /admin/metrics/stream` pushes the same snapshot every two seconds. Prometheus text remains available at `/metrics`.

## Quality gates

Every merge to `main` must pass the aggregated `gate` check; the same checks run locally.

| Gate | Tool | Threshold |
| --- | --- | --- |
| backend format | ruff format --check | formatted |
| backend lint | ruff | zero findings |
| backend types | mypy --strict | zero errors |
| backend import boundaries | import-linter | all contracts kept |
| backend tests | pytest + coverage | 90% branches, 95% routing |
| backend CRAP | crap4py | ≤ 6 per function |
| backend dead code | vulture | zero findings |
| backend docstrings | interrogate | ≥ 80% |
| backend security | bandit | zero issues |
| backend deps | pip-audit (runtime set) | zero advisories |
| backend dependency hygiene | deptry | no unused or missing deps |
| backend design rules | semgrep | zero blocking findings |
| backend structural rules | ast-grep | zero findings |
| module size | size_gate.py | file ≤ 320, function ≤ 60 |
| backend cognitive complexity | flake8-cognitive-complexity | ≤ 9 per function |
| property tests | hypothesis | invariants hold |
| backend contracts | schemathesis | no 5xx |
| cohesion | cohesion_gate.py | LCOM4 ≥ 0.5 |
| duplicates | jscpd | under 5% |
| backend mutation | mutmut | ≥ 75% |
| backend E2E | pytest -m e2e | all pass |
| frontend format | prettier --check | formatted |
| frontend lint | eslint | zero findings |
| frontend types | tsc --noEmit | zero errors |
| frontend dependency boundaries | dependency-cruiser | zero violations |
| frontend dead code | knip | no unused files/exports/deps |
| frontend tests | vitest + coverage | 85% branches |
| frontend CRAP report | crap-score | report generated |
| frontend CRAP | crap-score threshold reader | ≤ 6 per function |
| frontend mutation | stryker | ≥ 70% |
| frontend E2E | playwright | all pass |
| docs | docs_gate.py | zero problems |
| secrets | gitleaks | none |

```sh
uv run python scripts/gate.py --all --mutation --e2e
```

See [docs/gates.md](docs/gates.md) for the full list and [AGENTS.md](AGENTS.md) for the maintainer map.

## Documentation

- [Architecture](docs/architecture.md)
- [Routing](docs/routing.md)
- [Providers](docs/providers.md)
- [Metrics and dashboard](docs/metrics.md)
- [Operations](docs/operations.md)
- [Frontend](docs/frontend.md)
- [API](docs/api.md)
- [Configuration reference](docs/config-reference.md)

## License

MIT.

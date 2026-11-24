# Operations

## Deploy with Docker

```sh
cp .env.example .env
docker compose -f deploy/docker-compose.yml up -d --build
```

The image builds the SPA, runs a single uvicorn process, and serves the SPA from `/`. Configuration is read from `POLYGATE_CONFIG` or the `providers` table inside the SQLite volume.

## Configure channels

```toml
[[provider]]
id = "amr"
base_url = "https://amr-link.open-design.ai/v1"
model = "deepseek-v4.1-flash-eco"
api_key_env = "AMR_API_KEY"
max_concurrency = 10
max_tokens_min = 3000
```

Keys are referenced by environment variable name. The gateway never stores secret material.

## Authentication

- `ADMIN_TOKEN` protects `/admin/*` and the management UI.
- `PROXY_API_KEY` is the legacy all-provider credential for `/v1/*`.
- `[[client_key]]` entries protect `/v1/*` with per-caller provider allowlists and weights. Once any
  client key is configured, a valid client credential is required even when `PROXY_API_KEY` is unset.
  An unprovisioned client key is inactive (`401` for that key) and does not take down legacy or
  admin traffic. Startup fails only if no usable proxy credential or admin token exists.

## Health checks

- `/healthz` reports process liveness.
- `/readyz` reports whether any provider is enabled and keyed.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `providers_unavailable` | Inspect `attempts` in the error body for per-provider classes. |
| Slow streaming start | Lower `timeouts.total_seconds` so a stalled channel fails over sooner. |
| Provider always skipped | Look for an open circuit in the dashboard or events log. |
| Constant 401 | Verify the client credential and the env var named by `api_key_env`. |
| `/v1` returns 503 | A client-key set exists but none of its `api_key_env` values are set. Fix the deployment env; startup should have caught this. |

## Metrics retention

The SQLite file grows with call volume. Use `range` endpoints for dashboards and archive or prune the database on a monthly cadence for large deployments.

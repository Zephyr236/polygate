# polygate backend

FastAPI gateway core: provider adapters, score-based routing, health state and SQLite metrics.

## Commands

```sh
uv sync --extra dev
uv run pytest tests --ignore=tests/e2e
uv run pytest tests/e2e -m e2e
uv run ruff check src tests && uv run ruff format --check src tests
uv run mypy src
uv run lint-imports
uv run python ../scripts/gate.py --backend --mutation --e2e
```

See the repository [README](../README.md) and [docs](../docs/index.md).

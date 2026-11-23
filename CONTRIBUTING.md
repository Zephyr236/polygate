# Contributing

## Workflow

1. Branch from `main`.
2. Make the change with tests and doc updates in the same commit.
3. Run `uv run python scripts/gate.py --all` locally; expect it to be green.
4. Open a pull request. The `gate` workflow must pass before merge.

## Review policy

This is a single-maintainer repository, and GitHub does not allow an author to approve their own pull
request. Branch protection therefore requires **zero approving reviews**; requiring one would deadlock every
change. The gates are the merge criterion instead:

- Pull requests are the only path to `main`, including for administrators (`enforce_admins`).
- The aggregated `gate` check must be green. It fails on `failure`, `cancelled` **and `skipped`**
  dependencies, so a gate that never ran cannot be mistaken for one that passed.
- Force pushes and branch deletion are disabled.

If a second maintainer joins, raise the review requirement to one in repository settings; nothing else
changes. The rationale is recorded in [ADR 0004](docs/adr/0004-merge-policy.md) and [ADR 0007](docs/adr/0007-protect-main.md).

## Commit style

Use imperative subjects (`add lane-aware scheduling`, not `added ...`). Keep one logical change per commit so CRAP and mutation reports stay interpretable.

## Adding tests

- Backend unit tests live in `backend/tests/unit` and must not touch the network.
- Integration tests use a scripted `httpx.MockTransport` or `respx`.
- E2E tests use the fake upstreams in `backend/tests/e2e/fake_upstream.py`.
- Frontend unit/component tests use Vitest with MSW; browser tests are Playwright specs under `frontend/e2e`.

## Documentation rule

Comments and docstrings state what a function does, not why it exists in narrative form. Keep them short and place them on public or non-obvious interfaces. `ruff` (D rules) and `eslint-plugin-jsdoc` enforce this.

## Changing configuration

Edit `backend/src/polygate/config.py`, then regenerate the reference:

```sh
cd backend && uv run --with pydantic python ../scripts/gen_config_reference.py
```

The docs gate fails if a field is undocumented.

# ADR 0003: Audit the runtime dependency set, not the development toolchain

- Status: Accepted
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

`pip-audit` against the full development environment reported advisories in packages the gateway never
ships:

- `pyjwt` 2.13.0, pulled by `semgrep` (the design-rule gate);
- `mcp` and `opentelemetry-api`, pulled by the same development tooling;
- `wcmatch`, pulled by `jscpd` and other scanners.

At the same time it reported real `starlette` advisories that do reach production, because FastAPI
0.115.14 pinned an affected Starlette. A gate that mixes both sets either blocks on advisories the
project cannot fix (no newer `pyjwt` allowed by `semgrep`'s pin) or, if skipped, hides the ones it can.

## Decision

Split the concern in two:

1. Harden the shipped set. FastAPI was raised to 0.139.2 with Starlette 1.10.0, which clears the
   `PYSEC-2026-*` Starlette advisories; `httpx2` joined the development extras for the Starlette
   TestClient.
2. Audit the runtime set. `uv export --no-dev --format requirements-txt --no-hashes` produces
   `.runtime-reqs.txt`, and `pip-audit -r .runtime-reqs.txt` is the blocking stage. It reports "No known
   vulnerabilities found". The exported requirements file is git-ignored and regenerated per run.
3. Keep development advisories visible but non-blocking. They stay in the dependency tree, are listed
   here with their owners, and are refreshed whenever a tool releases a fix.

`deptry` complements this: it fails when a dependency is declared but unused or used but undeclared,
with per-rule ignores for console entry points (`uvicorn`, `pytest`, `mutmut`, `ruff` and similar).

## Consequences

- The blocking audit is honest: it describes what the container runs.
- Toolchain advisories no longer drown out production ones; the split is explicit rather than a
  blanket skip.
- `.runtime-reqs.txt` must be regenerated before auditing, which `scripts/gate.py` does as a separate
  stage so a stale export cannot mask a regression.
- A future production dependency added to `[project.dependencies]` is audited automatically; a
  development-only one is not, which is the intended split between shipped code and tooling.

## References

- `backend/pyproject.toml` (`[project.dependencies]`, deptry ignores)
- `scripts/gate.py` (`backend deps export`, `backend deps`, `backend dependency hygiene`)
- [docs/gates.md](../gates.md)

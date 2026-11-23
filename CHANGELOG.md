# Changelog

All notable changes are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- Three architecture decision records and a docs-gate check for ADR numbering, sections and index links.
- Chinese README alongside the English one.
- Mutation gates re-measured from an empty cache: `mutmut` 80.78%, Stryker 77.78%.

### Changed

- Branch protection: pull requests required with zero approving reviews, `gate` as the sole merge
  criterion, force pushes and deletions blocked (ADR 0004).

### Fixed

- Mutation jobs ran only on pull requests, so direct pushes to `main` never exercised them; the aggregated
  `gate` check now treats a skipped dependency as a failure.
- Non-JSON or empty request bodies returned 500; `read_json` now answers 400.

## [0.1.0] - 2026-11-23

### Added

- Multi-provider routing gateway with score-based selection across success rate, latency, cost coefficient and cache hit rate.
- OpenAI and Anthropic compatible proxy endpoints, streaming included.
- Per-provider quirks for auth style, session headers, streaming usage placement and custom error payloads.
- Concurrency lanes, retries, circuit breaker and automatic failover.
- SQLite metrics rollups, event log and provider overrides.
- Admin dashboard with KPI tiles, traffic chart, provider cards and detail table.
- Provider editor, routing simulation and chat playground.
- All-in-one Docker image and compose file.
- Quality gates: ruff, mypy, import-linter, pytest coverage, crap4py, mutmut, vulture, interrogate, bandit, pip-audit, eslint, prettier, tsc, dependency-cruiser, vitest coverage, crap-score, stryker, playwright, docs gate and gitleaks.

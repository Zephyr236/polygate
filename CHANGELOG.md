# Changelog

All notable changes are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- PR-Agent workflow (`.github/workflows/pr-agent.yml`) reviews pull requests on open, reopen,
  ready-for-review and synchronize, and responds to `/review` comments. It uses the Zen
  OpenAI-compatible endpoint and `deepseek-v4.1-flash`; the review is advisory.
- ADRs 0001–0008, including ADR 0008 (custom agent gate replaced by PR-Agent) and ADR 0007
  (`main` is pull-request-only).
- Chinese README alongside the English one.
- Mutation gates re-measured from an empty cache: `mutmut` 80.78%, Stryker 77.78%.

### Changed

- Branch protection requires `gate`; force pushes, deletions and direct pushes are blocked, including
  for administrators (`enforce_admins`). Pull requests require zero approving reviews (ADR 0004,
  ADR 0007).
- Removed the custom `gate-candidate` workflow, candidate policy, acceptance/promotion scripts,
  rule-coverage helper, fixtures and tests. PR review is now PR-Agent, not a custom check.

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

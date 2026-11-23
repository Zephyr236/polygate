# Changelog

All notable changes are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- Per-change review gate: `.github/workflows/gate-candidate.md` reads the whole repository, the rule
  coverage map and the change, then creates one `gate-candidate` check. Pull requests block on it;
  direct pushes to `main` are audited after the fact. The push audit uses full history plus a
  recorded base/head range (merge base for PRs) and per-commit concurrency so no commit is
  skipped and no unrelated base commits are reviewed. Success means the change
  is covered; failure means a concrete missing rule or invariant, with file/line and a minimal fix.
- Rule coverage map (`scripts/rule_coverage.py`) and offline candidate tooling
  (`agent/policy.toml`, `scripts/accept_candidate.py`, `scripts/promote_candidate.py`) for adding a
  permanent rule or test by hand.
- ADRs 0001–0006, including the review-gate boundary in ADR 0006 (supersedes ADR 0005).
- Chinese README alongside the English one.
- Mutation gates re-measured from an empty cache: `mutmut` 80.78%, Stryker 77.78%.

### Changed

- Branch protection requires both `gate` and the agent's `gate-candidate` check; force pushes,
  deletions and direct pushes are blocked, including for administrators (`enforce_admins`). Pull
  requests require zero approving reviews (ADR 0004, ADR 0007).
- The automatic rule/test promotion workflow was removed: a finding means the code must be fixed,
  not merged as a rule (ADR 0006).

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

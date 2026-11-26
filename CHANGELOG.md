# Changelog

All notable changes are documented here. The format follows Keep a Changelog and the project uses semantic versioning.

## [Unreleased]

### Added

- Frontend redesign: sidebar shell, data-dense dashboard, card-based provider editor
  with loading/error/empty states, searchable provider pool, improved route/playground layouts,
  and a dedicated admin login screen.
- Architecture review: metrics/ratchet (`scripts/architecture_metrics.py`, `architecture_gate.py`),
  architecture principles, an advisory agent, and ADR 0018.
- Acceptance contract: `specs/requirements.yaml`, Gherkin scenarios, pytest-bdd/Cucumber
  execution, contract/capability/ADR/TLA+ gates, OpenSpec validation, ADR 0017 and CI wiring.
- Advisory design-review prototype (`scripts/design_review.py`), a multi-role panel
  (`scripts/design_panel.py`), a design-brief template, and ADR 0009. A label-gated Claude Code CI
  workflow runs the base-branch panel against the PR head as data and uploads one report per role.
  A single-agent Claude Agent SDK variant (`scripts/design_agent_sdk.py`) is available under the
  `design-review-sdk` label.
- CodeQL analysis for Python and JavaScript/TypeScript, with high/critical findings blocking the
  aggregated `gate` job.
- ADRs 0001–0008, including ADR 0008 (CI-only merge gates) and ADR 0007
  (`main` is pull-request-only).
- Chinese README alongside the English one.
- Mutation gates re-measured from an empty cache: `mutmut` 80.78%, Stryker 77.78%.

### Changed

- Removed all agent review gates and their tooling. A pull request merges only after the aggregated
  `gate` check passes; branch protection requires `gate`, and direct pushes, force pushes and
  deletions are blocked, including for administrators (ADR 0004, ADR 0007, ADR 0008).

### Fixed

- Mutation jobs ran only on pull requests, so direct pushes to `main` never exercised them; the aggregated
  `gate` check now treats a skipped dependency as a failure.
- Non-JSON or empty request bodies returned 500; `read_json` now answers 400.

## [0.1.0] - 2026-11-23

### Added

- Frontend redesign: sidebar shell, data-dense dashboard, card-based provider editor
  with loading/error/empty states, searchable provider pool, improved route/playground layouts,
  and a dedicated admin login screen.
- Multi-provider routing gateway with score-based selection across success rate, latency, cost coefficient and cache hit rate.
- OpenAI and Anthropic compatible proxy endpoints, streaming included.
- Per-provider quirks for auth style, session headers, streaming usage placement and custom error payloads.
- Concurrency lanes, retries, circuit breaker and automatic failover.
- SQLite metrics rollups, event log and provider overrides.
- Admin dashboard with KPI tiles, traffic chart, provider cards and detail table.
- Provider editor, routing simulation and chat playground.
- All-in-one Docker image and compose file.
- Quality gates: ruff, mypy, import-linter, pytest coverage, crap4py, mutmut, vulture, interrogate, bandit, pip-audit, eslint, prettier, tsc, dependency-cruiser, vitest coverage, crap-score, stryker, playwright, docs gate and gitleaks.

# Quality gates

Every merge must pass the aggregated `gate` job. Most checks run locally through `scripts/gate.py`;
CodeQL runs in CI only.

| Gate | Tool | Threshold |
| --- | --- | --- |
| Backend lint | `ruff check` | zero findings |
| Backend format | `ruff format --check` | formatted |
| Backend types | `mypy --strict` | zero errors |
| Backend import boundaries | `import-linter` | all contracts kept |
| Backend tests | `pytest` with branch coverage | 90% overall, 95% for routing |
| Backend CRAP | `crap4py` | every function ≤ 6 |
| Backend dead code | `vulture` | zero at confidence 80 |
| Backend docstrings | `interrogate` | ≥ 80% |
| Backend security | `bandit` | zero issues |
| Backend dependencies (`backend deps export`, `backend deps`) | `uv export` + `pip-audit` on the runtime set | zero advisories |
| Backend dependency hygiene | `deptry` | no unused or missing dependencies |
| Backend design rules | `semgrep` (`rules/architecture.yml`) | zero blocking findings |
| Backend structural rules | `ast-grep` (`sgconfig.yml`) | zero findings |
| Backend cognitive complexity | `flake8-cognitive-complexity` (`.flake8`) | cognitive complexity ≤ 9 per function |
| Backend property tests | `hypothesis` state machines | invariants hold over randomized operation sequences |
| Backend contracts | `schemathesis` on the OpenAPI surface | no 5xx for schema-valid input |
| Class cohesion | `scripts/cohesion_gate.py` (LCOM4) | ≥ 0.5 for behaviour classes with ≥ 3 methods |
| Duplicate code | `jscpd` over backend and frontend source | duplication under 5% |
| Module size | `scripts/size_gate.py` | file ≤ 320 lines, function ≤ 60, module ≤ 60 lines per function |
| Backend mutation | `mutmut` via `scripts/mutation_gate.py` | ≥ 75% |
| Backend E2E | `pytest -m e2e` | all pass |
| Frontend lint | `eslint` flat config | zero findings |
| Frontend format | `prettier --check` | formatted |
| Frontend types | `tsc --noEmit` | zero errors |
| Frontend dependency boundaries | `dependency-cruiser` | zero violations |
| Frontend dead code | `knip` | no unused files, exports, types or dependencies |
| Frontend tests | `vitest --coverage` | 85% branches |
| Frontend CRAP (report: `frontend CRAP report`, threshold: `frontend CRAP`) | `crap-score` plus `scripts/crap_js_gate.py` | every function ≤ 6 |
| Frontend mutation | `stryker` | break below 70 |
| Frontend E2E | `playwright` | all pass |
| Docs | `scripts/docs_gate.py` | zero problems, including ADR numbering, sections and index links |
| Security history | `gitleaks` | no leaked secrets |
| CodeQL | GitHub CodeQL (`python`, `javascript-typescript`) | analysis completes; SARIF uploaded |

## Local usage

```sh
uv run python scripts/gate.py --backend
uv run python scripts/gate.py --frontend
uv run python scripts/gate.py --docs
uv run python scripts/gate.py --all --mutation --e2e
```

## Architecture decision records

`docs/adr/` holds numbered records. The docs gate requires contiguous numbering from `0001`, the
Context / Decision / Consequences sections, a link from `docs/adr/index.md`, and a link from
`docs/index.md` to the index. See [the ADR index](adr/index.md).

## Cognitive complexity vs CRAP

CRAP combines complexity with coverage, so a complex but well-tested function can still pass. The cognitive-complexity gate measures nesting and linear flow separately, which catches deeply nested functions that tests happen to cover. Both run on every merge.

## Contracts and property tests

`hypothesis` state machines drive `HealthRegistry` and `Scheduler` through randomized sequences of successes, failures, acquisitions, releases and clock moves, asserting capacity, occupancy and outcome invariants after every step. `schemathesis` fuzzes every documented operation through an in-process ASGI app and fails on any 5xx; it caught the missing non-JSON body handling that `read_json` now returns 400 for.

## Cohesion and duplication

`cohesion_gate.py` computes LCOM4 for Python classes that define at least three methods and skips abstract bases, where placeholder methods legitimately connect nothing. `jscpd` reports clone coverage for both languages in one pass.

## Design rules as code

`rules/architecture.yml` (semgrep) encodes layer ownership and forbids function-level imports: HTTP clients only in `providers/`, FastAPI only in `api/` and `app.py`, SQLite only in `storage.py`, retry sleeps only in the scheduler, credentials always via `api_key_env`, no prints in the gateway. `rules/ast-grep/` (ast-grep) adds structural rules with test fixtures. Both rulesets are verified to fire on deliberate violations, so a new rule is never silently inert.

## Size limits

`scripts/size_gate.py` fails on: backend file > 320 lines, backend function > 60 lines, a module whose total lines exceed 60 per declared function, frontend file > 320 lines and frontend function > 70 lines. Pure type-declaration modules are exempt because they carry no logic.

## Notes

- `mutmut` only mutates the routing, provider and protocol layers so the run stays under ten minutes.
- `stryker` mutates the pure helpers and the API client.
- CRAP reuses the official tools: `crap4py` for Python and `crap-score` for TypeScript, with a thin threshold reader in `scripts/`.
- The dependency audit runs against the runtime export (`uv export --no-dev`). Dev-only tools (`semgrep` pulls `pyjwt`, `mcp` pulls `opentelemetry`, `wcmatch`) carry upstream advisories that never reach the shipped image; they still run in CI but do not gate the merge on advisories they cannot fix.
- `deptry` runs with per-rule ignores for console entry points (`uvicorn`, `pytest`, `mutmut`, `ruff`, and similar) because those tools are executed rather than imported.

## Merge policy

A pull request merges only when the aggregated `gate` check passes. See
[ADR 0008](adr/0008-ci-only-gates.md) for the CI-only policy.

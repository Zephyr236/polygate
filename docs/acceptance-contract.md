# Acceptance contract

The contract binds four artifacts with one ID:

```text
specs/requirements.yaml  ->  specs/features/*.feature  ->  tests  ->  design-review finding
```

## Requirements

`specs/requirements.yaml` is canonical. Every entry has:

- `id`: stable ID such as `AUTH-001`
- `statement`: externally visible behavior
- `severity`: `P0` (blocks), `P1` (follow-up), `P2` (advisory)
- `owner`
- `adr`: related ADRs
- `verify`: existing files that verify it

`specs/scope.yaml` lists the requirements changed by the current change. The contract gate requires
every P0 requirement in scope to have a passing `@req:<ID>` Gherkin scenario.

## Scenarios

Scenarios use tags:

```gherkin
@req:AUTH-001 @p0
Scenario: A key cannot select a provider outside its allowlist
  Given ...
  Then ...
```

- Python: `backend/tests/bdd/`, executed by pytest-bdd.
- Frontend: `frontend/tests/bdd/`, executed by Cucumber.js.
- `gherkin-lint` checks tag and scenario structure.

## Gates

```sh
cd backend && uv run pytest tests/bdd --junitxml=bdd.xml
cd .. && backend/.venv/bin/python scripts/contract_gate.py --junit backend/bdd.xml
backend/.venv/bin/python scripts/adr_gate.py
backend/.venv/bin/python scripts/capability_gate.py
backend/.venv/bin/python scripts/tla_gate.py
cd frontend && pnpm run gherkin:lint && pnpm run bdd && pnpm run openspec:validate
```

`contract_gate.py` is deterministic. It validates IDs, verification targets, P0 scenario coverage,
JUnit results and the review-finding policy. No model call is involved.

## Finding policy

A review finding must include `requirement_id` and `severity`:

- `P0`: block
- `P1`: follow-up issue; does not block
- `P2`: advisory
- P0 with an unknown or missing requirement: contract gap; block
- P1/P2 without a requirement: advisory
- An unknown requirement on a P0 finding is a contract gap and blocks; on P1/P2 it is advisory

The requirement severity is not a blanket upgrade for every finding; severity belongs to the
finding. The historical replay showed that a requirement-level max policy blocks 29/56 findings
instead of 16/56.

## TLA+

`specs/tla/gate.tla` models the review state machine: starts, stale completions, and final
publication. TLC checks that no published verdict belongs to a run whose tested head differs and
that an owner is always a run. The model is intentionally small; the workflow still needs the
capability and contract checks.

## Change process

1. Add or update a requirement in `specs/requirements.yaml`.
2. Update `specs/scope.yaml`.
3. Add a `@req:` scenario; make it pass.
4. Update the ADR if a decision changed.
5. Run the gates above.

The publish job has a per-PR concurrency group (`cancel-in-progress: false`), so publication is
serialized; `design_publish.py` additionally skips a run when a newer final status exists.

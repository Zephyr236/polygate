# Acceptance contract results

Date: 2026-11-25

## Implemented artifacts

- `specs/requirements.yaml`: 13 requirements (5 P0, 7 P1, 1 P2), each with owner and verification target.
- `specs/scope.yaml`: 10 requirements in the acceptance-contract change.
- `specs/features/`: 4 backend Gherkin scenarios and 1 frontend scenario.
- `backend/tests/bdd/`: pytest-bdd execution (10 scenarios).
- `frontend/tests/bdd/steps.ts`: Cucumber.js execution (1 scenario, 4 steps).
- `openspec/changes/acceptance-contract/`: OpenSpec proposal/spec/design/tasks.
- `docs/adr/0017-acceptance-contract.md`: MADR-compatible decision record.
- `scripts/contract_gate.py`: requirement, scenario and finding policy.
- `scripts/gate_contract.py`: pure stale-head, supersession and severity model.
- `scripts/capability_gate.py`: agent/publish workflow capability check.
- `scripts/tla_gate.py` + `specs/tla/gate.tla`: TLC model of the review state machine.
- `.github/workflows/ci.yml`: `contract` job added to the aggregate gate; frontend job runs Gherkin,
  Cucumber and OpenSpec validation.

## Final local acceptance

```text
backend pytest                     214 passed
backend + frontend + docs gates    all pass
backend BDD                        10 scenarios passed
frontend Cucumber                  1 scenario / 4 steps passed
Gherkin lint                       0 findings
OpenSpec validate --all --strict   1 change passed
ADR contract                       17 ADRs passed
capability contract                passed
TLA+ TLC                           1,782 states generated / 471 distinct / 0 errors
contract gate                      13 requirements / 10 scope / 0 problems
design finding policy              pass
```

## Historical replay (56 design-review findings, #24–#84)

Rubric: P0 = security, wrong merge verdict, or required gate unavailable/forgeable; P1 =
availability/concurrency/missing acceptance evidence; P2 = docs/process/theoretical edge.

| Rater | P0 | P1 | P2 | P0-only blocking reduction |
|---|---:|---:|---:|---:|
| Primary | 16 | 29 | 11 | 71.4% |
| Independent agent | 18 | 29 | 9 | 67.9% |

Severity agreement: 48/56 (85.7%). The two raters agree that roughly two thirds of the historical
findings should not block.

Gate activity:

```text
Design gate runs: 25
skipped: 12
failure: 12
success: 1
paid runs: 13
maximum budget exposure: 13 × $4 = $52
```

## Race simulation

160,000 random schedules, 4 pushes and 4 runs each:

| Metric | Current policy | Pinned/superseded policy |
|---|---:|---:|
| Wrong-head reviews | 43.5% | 0% |
| Duplicate reviews per head | 36.6% | 0% |
| Older verdict overwrites newer | 18.3% | 0% |
| Stale final per schedule | 0.146 | 0 |
| Reviews per schedule | 4.00 | 2.26 |

The new policy reduces review calls by 43.5% while eliminating the modelled wrong-head and
overwrite races. This is an algorithm-level simulation; issue #84 showed that the implementation
still needs the marker/capability checks above.

## Findings and limitations

- Scenarios only cover what is written; an unmodelled path can still escape.
- `adrkit`/Archgate were unavailable in this environment; MADR structure and requirement references
  are checked by the deterministic `adr_gate.py`.
- OpenSpec validates structure, not semantic correctness.
- TLA+ models the gate state machine, not the whole gateway.
- The independent labels are a second LLM rater, not human ground truth; P0 disputes need human
  adjudication.

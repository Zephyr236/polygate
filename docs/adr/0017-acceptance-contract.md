# ADR 0017: A shared acceptance contract binds requirements, scenarios and review findings

- Status: Accepted
- Date: 2026-11-25
- Deciders: polygate maintainers
- Requirements: AUTH-001, AUTH-002, ROUTE-001, CFG-001, GATE-002, GATE-003, GATE-004,
  GATE-005, GATE-006, DOC-001, TEST-001

## Context

The design gate produced real security findings but also treated documentation wording, missing
evidence and theoretical edge cases as equal blocking events. Across 56 historical findings, only
16 were P0 under the acceptance rubric; the remaining 40 were P1/P2. There was no machine-readable
requirement catalog, no requirement-to-scenario traceability, and no severity policy. The gate
therefore had to infer what "correct" meant, and the developer and reviewer could not point at the
same clause.

## Decision

- `specs/requirements.yaml` is the canonical requirement catalog: unique ID, statement, severity,
  owner, ADR references and existing verification targets.
- Gherkin features in `specs/features/` carry `@req:<ID>` and `@p0`/`@p1` tags. Python scenarios run
  with pytest-bdd; frontend scenarios run with Cucumber.js.
- `scripts/contract_gate.py` is deterministic: it validates the catalog, P0 scenario coverage and
  JUnit results, and applies the finding policy.
- Review findings must include `requirement_id` and `severity`. P0 blocks; P1 becomes a follow-up;
  P2 is advisory. A P0 finding without a known requirement is a contract gap and blocks.
- `scripts/capability_gate.py` checks the agent/publish workflow split; `specs/tla/gate.tla` models
  the stale-head and overwrite state machine.
- OpenSpec validates the proposal/spec structure; MADR is the ADR format. The requirement ID is the
  join key between all artifacts.
- A requirement's severity does not automatically upgrade every finding on it; severity belongs to
  the finding. The requirement severity is used for coverage and as a fallback when the finding
  omits severity.

## Consequences

- A first-class P0 requirement needs at least one executable scenario; otherwise the contract gate
  fails.
- Documentation and brief findings no longer block when they are P2; they still produce advisory
  output.
- The gate can still miss an unmodelled failure; scenarios are only as good as the Gherkin.
- The contract adds a small deterministic gate, not a formal proof. TLA+ covers the gate state
  machine; OPA-style capability checks cover the workflow permissions.
- Severity is per finding, not per requirement. The replay experiment showed that a
  requirement-level max policy blocks 29/56 findings instead of 16/56, because one broad
  requirement class mixes P0 failures with P1 boundaries.

## References

- `specs/requirements.yaml`, `specs/features/`, `scripts/contract_gate.py`,
  `scripts/gate_contract.py`, `scripts/capability_gate.py`, `specs/tla/gate.tla`
- OpenSpec change `openspec/changes/acceptance-contract/`
- ADR 0011, 0014, 0016

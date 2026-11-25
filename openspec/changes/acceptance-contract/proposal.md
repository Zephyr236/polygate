# Proposal

## Why

The design gate produced 56 findings across 25 runs. About half concerned the gate's own
`workflow_run`, token and publication mechanics; there was no shared machine-readable acceptance
language, so a documentation wording issue and a forged status could both block a merge.

## What Changes

- Add a canonical requirement catalog with stable IDs, severity, owner and verification targets.
- Add Gherkin scenarios and pytest-bdd/Cucumber execution for the changed requirements.
- Add a deterministic contract gate for requirement coverage, scenario results and review-finding
  severity.
- Add a TLA+ model for the design-gate state machine and a capability check for its workflow.
- Add MADR-compatible acceptance-contract ADR and CI jobs.

## Capabilities

### New Capabilities

- `acceptance-contract`: traceable requirements, executable scenarios and severity-aware review.

### Modified Capabilities

- None.

## Impact

Affected: `specs/`, `scripts/contract_gate.py`, `scripts/gate_contract.py`,
`scripts/capability_gate.py`, `scripts/tla_gate.py`, backend BDD tests, frontend Cucumber tests,
CI, ADR 0017 and docs.

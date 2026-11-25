# Design

## Context

The contract is a small deterministic layer, not a language runtime. Requirement IDs are the join
key between ADR, Gherkin, tests and review findings.

## Decisions

- `specs/requirements.yaml` is canonical; OpenSpec describes the capability, not the product IDs.
- `pytest-bdd` executes Python scenarios; Cucumber.js executes frontend scenarios.
- `contract_gate.py` parses Gherkin tags and JUnit results; no model call.
- `gate_contract.py` applies the severity policy; P0 blocks, P1 follows up, P2 is advisory.
- `capability_gate.py` checks the workflow permissions; TLA+ checks the stale/overwrite state machine.

## Risks

- Scenarios can be tautological; P0 scenarios need independent review.
- The contract can over-block if severity is attached to a requirement rather than a finding; the
  replay experiment measured this.

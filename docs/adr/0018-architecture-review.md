# ADR 0018: A separate advisory architecture review

- Status: Accepted
- Date: 2026-11-25
- Deciders: polygate maintainers
- Requirements: ARCH-001, TEST-001

## Context

The design gate reviews requirements and failure modes. It does not consistently review global
structure: dependency direction, cycles, coupling, duplication, testability and evolvability. Adding
those questions to the design reviewer would mix business decisions with architecture and would
increase the chance of endless style findings.

## Decision

- A separate architecture reviewer reads `docs/architecture.md`, `specs/architecture.yaml`, the ADRs,
  the diff and a metrics JSON.
- Deterministic checks come first: import-linter, dependency-cruiser, size, LCOM, duplication, CRAP
  and the new `architecture_gate.py` ratchet.
- The agent findings carry `principle_id`, `severity` and `doc_ref`; findings without a principle or
  doc reference are advisory.
- The review is **advisory** initially. P0 structural violations are reported as blocking advisory
  findings, but the status is not required. It is promoted only after measured false-positive rates
  are below 20% for two weeks.
- It runs only after CI succeeds, only for architecture-sensitive changed paths, with a USD 2 budget
  and at most five findings.
- `scripts/architecture_gate.py` is the ratchet: it reads the base branch baseline, and a PR may
  not exceed its largest module or add a dependency cycle. A missing baseline fails closed.

## Consequences

- Architecture concerns get a dedicated review without polluting business design review.
- The deterministic metrics prevent "architecture taste" from becoming a blocking gate.
- The advisory status limits blast radius while the prompt is tuned.
- A new cycle or a size regression has a visible failing deterministic check before the agent runs.
- The middleware still needs human judgment for large refactors; the agent is not a proof.

## References

- `docs/architecture.md`, `docs/architecture-review.md`, `specs/architecture.yaml`
- `scripts/architecture_metrics.py`, `scripts/architecture_gate.py`
- ADR 0017

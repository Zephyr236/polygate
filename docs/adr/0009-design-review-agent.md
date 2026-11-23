# ADR 0009: Design review agent is advisory

- Status: Provisional (prototype)
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The CI gates catch mechanical and local problems, but they do not record why a design was chosen,
which alternatives were rejected, or which assumptions the change relies on. Formal verification
can prove an implementation against a specification, but it does not choose or justify the
specification. A language-model reviewer can read the diff and the design documents and ask those
questions, but its output is heuristic and can rationalize a weak design.

## Decision

- `scripts/design_review.py` is a local, advisory prototype. It reads the merge-base diff and the
  design docs, calls an OpenAI-compatible model, and emits a structured report.
- It is not part of `ci.yml`, `gate` or branch protection. It cannot approve, reject or merge.
- The model credential is supplied through the environment; the script redacts obvious secret
  assignments but treats repository text as untrusted.
- The report is an input to a human review. Missing evidence and questions are the useful outputs;
  the verdict is not an authority.

## Consequences

- The prototype can surface missing rationale, alternatives and failure modes that green gates do
  not show.
- It can also generate convincing but wrong rationale. It must be evaluated on known changes before
  any blocking use.
- Keeping it outside branch protection avoids flaky gates and keeps the CI-only merge policy from
  ADR 0008 intact.
- If the prototype proves useful, the next step is to measure its precision/recall, link reports to
  ADRs and specs, and only then consider a non-blocking PR comment workflow.

## References

- `scripts/design_review.py`, `docs/design-review.md`
- [ADR 0008](0008-ci-only-gates.md)

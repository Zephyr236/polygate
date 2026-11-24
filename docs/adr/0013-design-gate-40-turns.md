# ADR 0013: Raise the design gate to 40 turns

- Status: Accepted
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The 20-turn gate from ADR 0012 still terminated with `error_max_turns` on the caller-key feature.
The diff spans auth, config, scheduler, admin, tests and docs; the agent spent its turns reading
the repository instead of deciding.

## Decision

- Raise the gate to 40 turns and USD 4.
- Prompt the agent to read only files needed to verify the diff, keep tool use under twelve calls,
  and return `needs-changes` with questions instead of continuing to read when evidence is
  insufficient.
- Keep fail-closed behavior: exhausting the bound still blocks merge and creates an issue.

## Consequences

- Large multi-file features have room to finish; worst-case cost doubles again.
- A very large diff can still exhaust 40 turns; the next step is to split the PR rather than keep
  raising the bound.
- The bound remains an operational setting, not a quality guarantee.

## References

- [ADR 0012](0012-design-gate-bounds.md), `.github/workflows/design-gate.yml`,
  `scripts/design_gate.py`

# ADR 0013: Remove the design gate turn limit

- Status: Accepted
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The 20-turn gate from ADR 0012 still terminated with `error_max_turns` on the caller-key feature.
The diff spans auth, config, scheduler, admin, tests and docs; the agent spent its turns reading
the repository instead of deciding.

## Decision

- Remove the turn limit. The agent may keep reading until it can decide.
- Keep a USD 4 budget as the only cost bound, and prompt the agent to read only files needed to
  verify the diff, prefer at most twelve tool calls, and return `needs-changes` with questions when
  evidence is insufficient.
- Keep fail-closed behavior: a budget exhaustion, agent error or missing status still blocks merge
  and creates an issue.

## Consequences

- Large multi-file features are not cut off by an arbitrary turn count; worst-case cost is bounded
  by USD 4 rather than turns.
- A budget exhaustion still blocks; the next step is to split the PR or raise the budget, not to
  remove the cost guard.
- The budget remains an operational setting, not a quality guarantee.

## References

- [ADR 0012](0012-design-gate-bounds.md), `.github/workflows/design-gate.yml`,
  `scripts/design_gate.py`

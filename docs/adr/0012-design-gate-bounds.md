# ADR 0012: Design gate bounds and emergency repair

- Status: Accepted
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The required design gate was introduced with an 8-turn limit. On the caller-key feature it terminated
with `error_max_turns`, so the gate failed closed without a decision. Its workflow job was also named
`gate`, which collided with the aggregated CI check of the same name. Fixing either problem required
changing the gate while the gate was blocking its own repair.

## Decision

- The gate agent gets 20 turns and a USD 2 budget. The failing run's terminal reason was
  `error_max_turns`; the budget was not the reported binding limit. A later run that exhausts either
  limit still fails closed.
- The workflow job is `design_gate`; the required status context remains `design-review`. The job
  name must not reuse `gate`.
- Emergency repair of the gate itself may temporarily remove required status checks. The operator
  must record the exact prior contexts, merge only the gate repair, restore `gate` and
  `design-review` immediately, and verify the restored protection. This is an explicit, logged
  exception, not a normal path.
- The 20-turn/2-USD bound is revisable by ADR if the observed failure rate or cost changes.

## Consequences

- A multi-file feature has enough turns to read the repository; a very large PR can still exhaust
  the bound and stays blocked.
- The emergency path is manual. The design gate cannot verify its own restoration; a future
  automation could compare the live protection against the documented contexts.
- The job rename removes a false conflict between the CI aggregate check and the design gate.
- The gate remains heuristic and fail-closed; this ADR records the operational bound and the
  exception procedure, not a proof of review quality.

## References

- `.github/workflows/design-gate.yml`, `scripts/design_gate.py`
- [ADR 0010](0010-required-design-gate.md)

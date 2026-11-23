# Architecture decision records

Decisions that shaped the gateway and its gate suite, recorded so a future maintainer can see what was
considered and what was rejected.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-crap-and-cognitive-complexity.md) | CRAP and cognitive complexity run as parallel gates | Accepted |
| [0002](0002-boundary-tools.md) | Boundaries enforced only by tools proven to fail on a probe | Accepted |
| [0003](0003-runtime-dependency-audit.md) | Audit the exported runtime set; dev advisories stay non-blocking | Accepted |
| [0004](0004-merge-policy.md) | Pull requests required, zero required reviews; `gate` decides the merge | Accepted |
| [0005](0005-agent-candidate-promotion.md) | Agent candidates are accepted by oracle, promoted, then auto-merged after `gate` | Superseded by 0008 |
| [0006](0006-pr-review-gate.md) | Agent runs per PR as a required check; findings block until the code is fixed | Superseded by 0008 |
| [0007](0007-protect-main.md) | `main` is pull-request-only, including for administrators | Accepted |
| [0008](0008-ci-only-gates.md) | Merge only on the aggregated CI gate; no agent review | Accepted |
| [0009](0009-design-review-agent.md) | Design review agent is a local, advisory prototype | Provisional |

## Writing a new ADR

1. Copy the shape of an existing file: title, status, date, context, decision, consequences, references.
2. Number it `NNNN-short-slug.md`, continuing from the highest existing number.
3. Link it from this index and from `docs/index.md`.
4. The docs gate fails when an ADR is unindexed, misnumbered, missing a section, or broken by a dead
   relative link.

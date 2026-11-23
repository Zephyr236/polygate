# ADR 0008: Merge only on the aggregated CI gate

- Status: Accepted (supersedes [0005](0005-agent-candidate-promotion.md) and [0006](0006-pr-review-gate.md))
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

The repository tried two agent review designs: a custom `gate-candidate` check with a candidate
policy and promotion pipeline, and later PR-Agent. Both added an LLM to the merge decision. The
custom gate was complex and produced expensive-to-triage findings; PR-Agent was useful but still
produced false positives and needed its own blocking wrapper. The project already has a broad,
deterministic CI suite.

## Decision

- There is no agent review gate in CI. The active workflows are `.github/workflows/ci.yml` and the
  non-blocking `.github/workflows/e2e-real.yml`.
- The `gate` job in `ci.yml` depends on every CI job (`backend`, `design-rules`, `backend-e2e`,
  `backend-mutation`, `frontend`, `frontend-mutation`, `frontend-e2e`, `docs`, `secrets`,
  `docker`, `codeql`). It fails when any dependency is not `success`, including `cancelled` and
  `skipped`. CodeQL analyzes Python and JavaScript/TypeScript, uploads SARIF, and fails the job on any
  unsuppressed high or critical finding.
- Branch protection on `main` requires a pull request and the `gate` check, with `strict`; zero
  approving reviews; `enforce_admins` true; force pushes, deletions and direct pushes blocked.
- Agent review tooling, workflows, scripts, tests and documentation are removed.

## Consequences

- A pull request can merge only after every CI gate passes; there is no separate agent signal.
- Review is optional and human. CI remains deterministic and its failures are reproducible.
- No model credential or quota is part of the merge path.
- Main is pull-request-only for everyone, including administrators. Emergency recovery still
  requires temporarily disabling protection, an explicit and logged action (ADR 0007).
- If an agent reviewer is reintroduced later, it must be a separate, explicit decision and must
  not replace or weaken the CI gate.

## References

- `.github/workflows/ci.yml` (`gate` job)
- [ADR 0004](0004-merge-policy.md), [ADR 0007](0007-protect-main.md)

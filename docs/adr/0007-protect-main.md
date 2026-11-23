# ADR 0007: Main is pull-request-only, including for administrators

- Status: Accepted (supersedes the `enforce_admins` part of [0004](0004-merge-policy.md); agent-review detail superseded by [0008](0008-ci-only-gates.md))
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

ADR 0004 left `enforce_admins` off so the owner could recover the repository by pushing directly to
`main`. In practice that bypassed both the `gate` check and the agent review: a direct push is already
complete before any check can run, so it cannot be blocked or reverted by the normal flow. The
the branch protection decision is independent of any agent review; the aggregated CI gate is the
merge criterion.

## Decision

Branch protection on `main`:

- pull requests required, with **0 approving reviews** (single maintainer; self-approval is not
  allowed);
- required checks: `gate`, with `strict` (branch must be up to date);
- `enforce_admins: true` — administrators cannot bypass the pull-request requirement;
- force pushes and branch deletion disabled.

Recovery from a broken state is an explicit, temporary operation: disable protection in repository
settings, push the recovery commit, then restore the same settings. That action is visible in the
audit log and is not part of the normal workflow.

## Consequences

- Every change, including a one-line docs fix, goes through a pull request and both checks.
- A direct `git push` to `main` is rejected for everyone, including the owner. The push-triggered
  agent review still runs on PR merges (and on an exceptional push made while protection is
  temporarily disabled) as an audit.
- Emergency recovery takes one extra settings toggle. This is deliberate friction: bypassing the
  gates should require an explicit, logged action, not a routine push.
- The push trigger no longer makes direct pushes safe; it only records a check on a commit that
  already reached the branch.

## References

- [ADR 0004](0004-merge-policy.md) (zero-review policy; `enforce_admins` superseded here)
- [ADR 0006](0006-pr-review-gate.md)
- `.github/workflows/ci.yml`
- `CONTRIBUTING.md`, `AGENTS.md`

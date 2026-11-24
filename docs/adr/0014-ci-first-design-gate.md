# ADR 0014: The design gate runs only after CI succeeds

- Status: Accepted
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The design gate is a paid model call. It previously ran directly on every pull-request event,
including PRs whose deterministic CI was already failing. Those PRs cannot merge, so the review
spend bought nothing and delayed feedback. The gate also could run for an older head while a newer
CI run was pending.

## Decision

- `.github/workflows/design-gate.yml` triggers on the `ci` workflow's `completed` event, not on the
  pull-request event itself.
- It runs only when the CI conclusion is `success`, the event was a pull request, and a PR number is
  present. A failing CI run produces no `design-review` status and no model call; the required
  `gate` check already blocks the PR.
- The resolve job compares the initiating CI run's pull-request head with the current PR head, then
  waits up to fifteen minutes for that head's `gate` status. A stale run is skipped without a model
  call; a failed gate skips immediately; a pending gate is polled; a timeout leaves the status
  missing (fail closed).
- The gate status remains required. If CI succeeds but the gate workflow fails or the status is
  missing, the PR stays blocked (fail closed).

## Consequences

- No model spend on a PR whose CI is red; the expensive review starts only after the deterministic
  gate passes.
- A PR whose CI is fixed by a rerun of the same commit may need that CI run to complete again to
  trigger the gate; a new push always does.
- Fork PRs have an empty `workflow_run.pull_requests` array. The resolve job falls back to the
  commit-to-pulls API; if no PR is found it posts a failure status on the head SHA. Concurrency is
  keyed by the triggering CI head SHA; the resolve job skips a trigger whose PR head is stale, so
  an old completion cannot review the current head or cancel its run.
- The design gate is one step behind CI, so its feedback arrives later. This is the intended cost
  trade-off.
- The bridge uses `workflow_run`; workflows created by `GITHUB_TOKEN` cannot trigger further
  workflows, but `ci` is a normal PR workflow, so this bridge is valid.

## References

- `.github/workflows/design-gate.yml`, `.github/workflows/ci.yml`
- [ADR 0010](0010-required-design-gate.md), [ADR 0013](0013-design-gate-no-turn-limit.md)

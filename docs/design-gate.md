# Required design gate

`main` requires a `design-review` status in addition to `gate`. The status is produced by one
Claude Agent SDK agent, not by a panel and not by five models.

## What happens on a PR

1. After the `ci` workflow succeeds for the current PR head, `.github/workflows/design-gate.yml`
   checks out the base commit and runs the trusted base script. A failing CI run does not call the
   model; its `gate` check already blocks the PR.
2. The PR head is fetched into a worktree. With the full toolset the agent may execute PR code;
   the runner has `contents: read` but is not a security sandbox (ADR 0016).
3. The PR body is used as the design brief.
4. The agent returns `pass`, `needs-changes` or `insufficient-context` with structured findings.
5. Every finding becomes a `design-review-blocking` issue; resolved findings are closed on the next
   review.
6. The workflow writes the `design-review` commit status. It is `success` only for `pass` with no
   findings; otherwise it is `failure`. A missing status blocks merge. This is a commit status, not
   a check run; branch protection reads the status context.

## Resolving a blocked PR

- Read the blocking issues and the gate report artifact.
- Change the design or code, or add the missing rationale/evidence to the PR brief.
- Push again. The agent re-reviews, closes resolved issues, and updates the status.
- The PR can merge only when the status is `success` and no blocking issues remain.

There is no waiver label. Emergency recovery is temporarily disabling branch protection, which is
an explicit, logged action. The resolve job compares the initiating CI run's PR head with the current
PR head, then waits for that head's `gate` status: success runs the gate, failure skips without a
model call, and a timeout leaves the status missing (fail closed). A stale CI completion is skipped.
Fork CI runs resolve the PR from the commit-to-pulls API; if no PR is found, the head SHA gets a
failure status.

## Limits

- The gate is heuristic; a false positive blocks merge. The brief must include problem, constraints,
  alternatives, criteria, assumptions, falsifiers and reversibility.
- One model means one perspective. It is cheaper than a panel but does not provide independent
  opinions.
- Trusted PRs (`OWNER`/`MEMBER`/`COLLABORATOR`) run with `bypassPermissions` and the full toolset,
  including Bash, web tools and the `Agent` subagent. Fork PRs get only `Read`, `Grep`, `Glob` and a
  read-only `Agent` subagent. Every agent job has only `contents: read` and `pull-requests: read`; a
  separate `publish` job holds the write token, never executes PR code, and refuses a pass report
  unless the agent job ended successfully. The agent may modify its local worktree but cannot push.
  The gate removes GitHub/provider credentials from the agent environment, but trusted PR code can
  run with the model key present; this is not a security sandbox. See ADR 0016.
- The agent is bounded by a USD 4 budget and no turn limit.
- If the workflow, model or status publication fails, the status is missing or failed and the PR
  stays blocked (fail closed).

The gate reads the `ci-head` check-run marker written by the CI gate job (`tested_head=<sha>`),
resolves fork PRs through the commit-to-pulls API, and fails closed if the marker is missing. It
re-checks the head after the gate wait and again before fetching the worktree, so a push cannot make
it review the wrong tree. The gate is keyed by the triggering CI head SHA; stale triggers skip, and
publish ignores a superseded run when a newer final status already exists. See
[ADR 0014](adr/0014-ci-first-design-gate.md) for the trigger rules.

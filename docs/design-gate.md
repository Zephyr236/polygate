# Required design gate

`main` requires a `design-review` status in addition to `gate`. The status is produced by one
Claude Agent SDK agent, not by a panel and not by five models.

## What happens on a PR

1. `.github/workflows/design-gate.yml` checks out the base commit and runs the trusted base script.
2. The PR head is fetched into a worktree for the agent to read; PR code is never executed.
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
an explicit, logged action. The blocking path is tested by opening a PR without a design brief.

## Limits

- The gate is heuristic; a false positive blocks merge. The brief must include problem, constraints,
  alternatives, criteria, assumptions, falsifiers and reversibility.
- One model means one perspective. It is cheaper than a panel but does not provide independent
  opinions.
- The agent is read-only (`Read`/`Grep`/`Glob`) and bounded by turns and budget.
- If the workflow, model or status publication fails, the status is missing or failed and the PR
  stays blocked (fail closed).

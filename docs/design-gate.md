# Required design gate

`main` requires a `design-review` status in addition to `gate`. The status is produced by one
Claude Agent SDK agent, not by a panel and not by five models.

## What happens on a PR

1. After the `ci` workflow succeeds for the current PR head, `.github/workflows/design-gate.yml`
   checks out the base commit and runs the trusted base script. A failing CI run does not call the
   model; its `gate` check already blocks the PR.
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
an explicit, logged action. The resolve job waits for the current PR head's `gate` status: success runs the gate, failure
skips without a model call, and a timeout leaves the status missing (fail closed). Fork CI runs resolve the PR from the commit-to-pulls API; if no PR is found,
the head SHA gets a failure status.

## Limits

- The gate is heuristic; a false positive blocks merge. The brief must include problem, constraints,
  alternatives, criteria, assumptions, falsifiers and reversibility.
- One model means one perspective. It is cheaper than a panel but does not provide independent
  opinions.
- Trusted PRs give the agent an allowlisted read-only Bash (`git`, `rg`, `ls`, `cat`, `pytest`) and a
  `verifier` subagent; fork PRs stay read-only with `Read`/`Grep`/`Glob`. Edit/Write/WebFetch/WebSearch
  and NotebookEdit remain disallowed. The gate removes GitHub/provider credentials from the agent
  environment, but Bash can run PR code with the model key present; this is not a security sandbox.
- The agent is bounded by a USD 4 budget and no turn limit.
- If the workflow, model or status publication fails, the status is missing or failed and the PR
  stays blocked (fail closed).

The gate is keyed by the CI head SHA; fork PRs resolve through the commit-to-pulls API.
See [ADR 0014](adr/0014-ci-first-design-gate.md) for the trigger rules.

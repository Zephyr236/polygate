# ADR 0010: A single agent is a required design gate

- Status: Superseded by [0014](0014-ci-first-design-gate.md) (trigger) and
  [0016](0016-review-agent-bypass.md) (tool policy) (supersedes [0008](0008-ci-only-gates.md))
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

ADR 0008 made CI the only merge criterion because agent reviews were advisory and sometimes noisy.
The maintainer now wants one agent, not several models, to be the design gate: a pull request may
merge only when the agent finds no design problem, and its findings must be tracked as issues that
are completed before merge.

A single model is affordable and simple to configure. The trade-off is that the gate is heuristic:
it can be wrong, can be prompt-injected, and is not a formal proof.

## Decision

- `scripts/design_gate.py` runs one Claude Agent SDK agent on the design decision. It uses the Zen
  `deepseek-v4.1-flash` model, a rich design-review system prompt, JSON-schema structured output,
  a USD budget, and the tool policy recorded in [0016](0016-review-agent-bypass.md).
- `.github/workflows/design-gate.yml` runs on every `pull_request_target` open/synchronize/reopen/
  ready event. It checks out the base commit, runs the trusted base script, and gives the agent a
  worktree at the PR head for reading. It does not execute PR-controlled code.
- The agent returns `pass`, `needs-changes` or `insufficient-context`. Any finding blocks. Each
  finding creates or updates a `design-review-blocking` issue with a stable fingerprint and a PR
  marker. Resolved findings close automatically on the next review.
- The workflow writes a commit status named `design-review` on the PR head. It is `success` only
  when the agent returns `pass` and has no findings; otherwise `failure`. A missing status is
  fail-closed. The status is a required check on `main`, together with `gate`.
- The PR body is the design brief. Without a brief, the agent returns `insufficient-context` and
  creates a blocking issue.
- There is no waiver label. Emergency recovery remains temporarily disabling branch protection, an
  explicit and logged action.

## Consequences

- Every push to a PR spends one model call. Label-based opt-in is removed for this gate.
- A false positive blocks merge until the agent changes its finding or a maintainer uses the
  emergency protection override. The brief and evidence requirements are the main mitigation.
- An agent outage leaves the status missing or failed, so merges stop rather than bypass the gate.
- The required status and issues are visible on the PR; `gate` still covers all deterministic CI.
- Under [0016](0016-review-agent-bypass.md), trusted PRs get full tool access and may execute PR
  code; fork PRs remain read-only with `Read`/`Grep`/`Glob` and a read-only verifier. The runner
  has `contents: read`, but this is not a security sandbox.
- Design quality still depends on human judgment; the agent is a reviewer, not a proof.

## References

- `scripts/design_gate.py`, `.github/workflows/design-gate.yml`
- `docs/design-gate.md`
- [ADR 0008](0008-ci-only-gates.md) (superseded)

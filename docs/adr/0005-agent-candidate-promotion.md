# ADR 0005: Agent-proposed gates are promoted only after deterministic acceptance

- Status: Superseded by [0008](0008-ci-only-gates.md)
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

Static gates cover syntax, layering, size and known invariants, but not every business rule or
design boundary. An LLM can read the whole repository and propose a missing rule or test, but its
output varies between runs and it cannot be trusted to judge its own work. Writing directly to
`rules/` or the test suite would let a random process alter the gate specification itself.

At the same time, requiring a human to translate every proposal into a gate defeats the purpose.
The repository has a single maintainer, zero required reviews and a strict `gate` check.

## Decision

Split the loop into four deterministic stages:

1. **Proposal.** `.github/workflows/gate-candidate.md` runs on pull requests. It reads the whole
   repository, the rule coverage map and the PR diff, and opens at most one issue containing a
   candidate JSON and a patch. The agent is read-only; its only write is the bounded
   `create-issue` safe output.
2. **Acceptance.** `scripts/accept_candidate.py` applies the oracles from `agent/policy.toml`:
   rules must fire on a positive fixture and stay silent on a negative fixture and the current
   source trees; tests must fail at `pre_fix_commit` and pass at `post_fix_commit`; fixture
   commands must fail on the bad fixture and pass on the good one. Schema, paths, duplicate,
   overfit and budget checks run for every candidate.
3. **Promotion.** Accepted rules and tests move into the active suite (`rules/promoted.yml`,
   `rules/ast-grep/`, `backend/tests/agent_accepted/`) and are recorded in `agent/accepted.json`.
   Test candidates are promoted only when the candidate test passes on `origin/main`, so a test
   cannot land before its fix, including after a squash merge.
4. **Merge.** `agent-accept` opens `agent/<id>` and a PR, then enables squash auto-merge. The PR's
   own `gate` run is the final check. A write-capable `AGENT_PROMOTE_TOKEN` is used because PRs
   created with `GITHUB_TOKEN` do not trigger CI.

Artifacts with no mechanical oracle (ADR, policy proposal, gap report) and checks without a
promotion target stay as accepted issues and require a human.

## Consequences

- The agent never edits active rules, gate scripts, thresholds or workflows. The worst case of a
  compromised proposal is a rejected candidate or a reverting PR.
- Auto-merge is safe only because the promoted artifact has already passed an oracle and the PR
  still passes `gate`; a rule that is too broad will make the PR red and never merge.
- Rule and test debt is possible: a promoted rule can become noisy. `agent/accepted.json` records
  the source issue, fixtures and oracle, and `rules/promoted.yml` is a single small file that can
  be edited or reverted. A future shadow phase can run new rules as warnings before they block.
- The promotion token is a long-lived write credential. It must be rotated and scoped to this
  repository; losing it only disables promotion, not acceptance.
- Design and policy questions are explicitly not automated: they have no oracle and remain with a
  human.

## References

- `agent/policy.toml`, `scripts/agent_gate/accept.py`, `scripts/agent_gate/promote.py`
- `.github/workflows/gate-candidate.md`, `.github/workflows/agent-accept.yml`
- `rules/promoted.yml`, `agent/accepted.json`, `backend/tests/agent_accepted/`
- [ADR 0008](0008-ci-only-gates.md)

# Agent gate

The repository runs an AI agent as a **per-pull-request review check**. The agent reads the whole
repository and the diff. If it finds a concrete problem that the existing gates miss, it reports a
finding and the pull request fails; the author adjusts the code and pushes again until the agent
reports no finding.

## Trigger

`.github/workflows/gate-candidate.md` (compiled to `gate-candidate.lock.yml`) runs on pull-request
`opened`, `synchronize` and `reopened`, on every push to `main`, and on manual dispatch. Every push
to a pull request runs it again with the full repository, `reports/rule-coverage.json`, the existing
rules and the PR diff. A push to `main` reviews the pushed commit against its parent and records the
same check; it is an audit because the push has already happened.

The agent is read-only. Its only write is `create-check-run`; it cannot edit files, push, or open
issues or pull requests.

## Check outcomes

The workflow always creates exactly one check run named `gate-candidate` on the triggering commit.

- **No finding:** `conclusion: success`, title `No new gate required`, summary
  `The change is covered by the existing gates.`
- **Finding(s):** `conclusion: failure`, title `<n> gate finding(s)`, and a summary listing for each:
  - `path:line` and the changed behavior;
  - the invariant or rule that is missing;
  - why the existing gates miss it;
  - the proposed rule or test and the minimal code fix.

Branch protection requires both `gate` and `gate-candidate` on pull requests. A failure blocks the
merge; fixing the code and pushing creates a new check on the new commit. An agent or workflow outage
leaves the check missing, which also blocks the merge (fail closed). A `gate-candidate` failure on a
push to `main` is visible on the commit but cannot block that push; it is an audit.

## What counts as a finding

A finding is valid only when all of these hold:

1. the change introduces or exposes a concrete defect, leaves a named business invariant untested,
   or uses a pattern no existing static rule covers;
2. the agent names the invariant or rule and cites `path:line` in the changed code;
3. the existing gates (`docs/gates.md`) demonstrably miss it;
4. a minimal fix exists.

Style, naming, formatting, wording, speculation and pre-existing issues unrelated to the diff are
out of scope. Uncertainty resolves to success: a false failure causes churn, so the prompt is
deliberately conservative.

## Forks

Fork pull requests do not receive the model secret, so the agent does not run on them by default.
They remain blocked by the required `gate-candidate` check until a maintainer reruns the workflow
from the base repository.

## Offline tooling for permanent rules

`agent/policy.toml`, `scripts/accept_candidate.py` and `scripts/promote_candidate.py` remain as
offline tooling for a human who wants to add a permanent rule or test. They classify a gap, verify
the artifact against the matching oracle (rule must-fire/must-not-fire, test pre-fix/post-fix,
fixture command), and can move an accepted artifact into `rules/promoted.yml`,
`rules/ast-grep/` or `backend/tests/agent_accepted/`. They are not triggered by pull requests and
do not auto-merge anything.

The offline tooling is exercised by `backend/tests/agent_gate/` (`test_policy.py`,
`test_accept.py`, `test_issue.py`, `test_rule_coverage.py`, `test_promote.py`).

## What this is not

- It does not merge rules or tests automatically.
- It does not add a test merely to have a test: an offline candidate without a named invariant and
  a failing-before/passing-after (or fires-on-bad/silent-on-good) proof is rejected.
- It does not let an agent modify active rules, thresholds, workflows or gate scripts.
- It does not turn a design question into a rule. Design proposals and policy proposals stay in
  `docs/proposals/` and require a human decision.

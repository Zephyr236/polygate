# ADR 0006: The agent is a per-PR review check, not a rule merger

- Status: Accepted (supersedes [0005](0005-agent-candidate-promotion.md))
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

The intended loop is: every push or pull request runs the agent; the agent reviews the whole
repository and the diff. If it finds a concrete problem that the existing gates miss, it reports a
finding and the pull request fails; the author adjusts the code and pushes again until the agent
reports no finding. The agent's proposed rule is evidence of a defect in the change, not an artifact
to merge.

The earlier proposal (ADR 0005) promoted accepted rules and tests automatically. That is the wrong
shape for this loop: it can merge a rule while the code that motivated it is still wrong, and it
makes the agent a source of gate configuration rather than a reviewer.

## Decision

- `.github/workflows/gate-candidate.md` runs on pull-request `opened`, `synchronize` and `reopened`,
  on every push to `main`, and on manual dispatch. It always creates exactly one check run named
  `gate-candidate` on the triggering commit:
  - `conclusion: success` when the change is covered by the existing gates, with a one-line summary;
  - `conclusion: failure` otherwise, with `path:line`, the missing invariant or rule, why the
    existing gates miss it, the proposed rule or test, and the minimal fix.
- A finding is only valid when it is caused or exposed by the diff, names a concrete invariant or
  rule, cites a changed location, and has a minimal fix. Style, naming, formatting, speculation and
  unrelated pre-existing issues are explicitly out of scope; uncertainty resolves to success.
- Branch protection on `main` requires both `gate` and `gate-candidate` for pull requests. A failing
  check blocks the merge until the code is fixed and the new commit passes the agent again. A push
  to `main` is audited after the fact; its check cannot block the already-completed push. Direct
  pushes are blocked by ADR 0007; the push trigger audits merges.
- The agent is read-only. It cannot edit rules, tests, workflows or gate configuration; the only
  write is the bounded `create-check-run` safe output.
- The rule/test promotion pipeline from ADR 0005 is removed from CI. `agent/policy.toml`,
  `scripts/agent_gate/` and the acceptance/promotion scripts remain as offline tooling for a human
  who wants to add a permanent rule; they are not triggered by pull requests.

## Consequences

- The agent's verdict is part of the merge decision, so its prompt is a gate specification. It is
  deliberately conservative: evidence is required, and "unsure" passes, because false failures
  cause churn and rerun-until-green behaviour.
- A new permanent rule is still written by a human (or by offline tooling); the agent only proposes
  it in the check text. This keeps the gate suite reviewable and avoids a random process editing
  the specification.
- Zen outages or a broken workflow leave the check missing, which blocks merges (fail closed). The
  check can be rerun manually; the workflow is independent of `gate`.
- Fork pull requests do not run the agent by default because they cannot receive the model secret;
  they remain blocked by the required check until a maintainer runs it from the base repository.

## References

- `.github/workflows/gate-candidate.md`, `.github/workflows/gate-candidate.lock.yml`
- `docs/agent-gate.md`, `docs/gates.md`
- [ADR 0005](0005-agent-candidate-promotion.md) (superseded)

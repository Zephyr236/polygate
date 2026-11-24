# ADR 0009: Design review agent is advisory

- Status: Provisional (the required gate is ADR 0010)
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The CI gates catch mechanical and local problems, but they do not record why a design was chosen,
which alternatives were rejected, or which assumptions the change relies on. Formal verification
can prove an implementation against a specification, but it does not choose or justify the
specification. A language-model reviewer can read the diff and the design documents and ask those
questions, but its output is heuristic and can rationalize a weak design.

## Decision

- `scripts/design_review.py` is a local, advisory prototype. It reads the merge-base diff and the
  design docs, calls an OpenAI-compatible model, and emits a structured report.
- `scripts/design_panel.py` runs independent role reviewers (`problem`, `architecture`, `failure`,
  `security`, `evidence`) and writes one report per role plus an index. The reports are not averaged
  into a single verdict.
- `.github/workflows/design-review.yml` runs the panel with the Claude Code CLI in CI when a PR has
  the `design-review` label. It uses `pull_request_target`, runs the base-branch script, and fetches
  the PR head only as git data; it is advisory and is not a required check.
- `scripts/design_agent_sdk.py` is a single-agent variant built on the Claude Agent SDK. It may use
  `Read`, `Grep` and `Glob`, is bounded by `--max-turns` and `--budget-usd`, and writes one report.
  `.github/workflows/design-review-sdk.yml` runs it from the base branch against a PR-head worktree
  when the `design-review-sdk` label is present.
- It is not part of `ci.yml`, `gate` or branch protection. It cannot approve, reject or merge.
- The model credential is supplied through the environment; the script redacts obvious secret
  assignments but treats repository text as untrusted.
- The report is an input to a human review. Missing evidence and questions are the useful outputs;
  the verdict is not an authority.

## Consequences

- The prototype can surface missing rationale, alternatives and failure modes that green gates do
  not show.
- It can also generate convincing but wrong rationale. It must be evaluated on known changes before
  any blocking use.
- Keeping it outside branch protection avoids flaky gates and keeps the CI-only merge policy from
  ADR 0008 intact. The label gate bounds token cost and keeps the review opt-in.
- If the prototype proves useful, the next step is to measure its precision/recall, link reports to
  ADRs and specs, and only then consider a non-blocking PR comment workflow.

## References

- `scripts/design_review.py`, `scripts/design_panel.py`, `docs/design-review.md`,
  `docs/templates/design-brief.md`
- [ADR 0008](0008-ci-only-gates.md)

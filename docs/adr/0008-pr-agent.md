# ADR 0008: Replace the custom agent gate with PR-Agent

- Status: Accepted (supersedes [0006](0006-pr-review-gate.md))
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

The custom gh-aw gate tried to turn an LLM review into a deterministic `gate-candidate` check, with
a policy, candidate format, acceptance oracles and a promotion pipeline. It was complex, produced
findings that were sometimes valid but expensive to triage, and still missed issues because the
prompt and the diff range were part of the same code being changed. The repository needs a mature,
maintained PR reviewer rather than a bespoke gate implementation.

PR-Agent (`the-pr-agent/pr-agent`) is an open-source PR review agent with a GitHub Action, support
for OpenAI-compatible models, automatic review on PR events and `/review` commands.

## Decision

- Remove the custom `gate-candidate` workflow, its required check, the candidate policy, acceptance
  and promotion scripts, rule-coverage helper, fixtures and tests.
- Add `.github/workflows/pr-agent.yml` using `the-pr-agent/pr-agent@v0.50.0` on PR `opened`,
  `reopened`, `ready_for_review` and `synchronize`, plus `issue_comment` for `/review`.
- Use the Zen OpenAI-compatible endpoint with model `openai/deepseek-v4.1-flash`
  (`ZEN_API_KEY`) and the required `x-opencode-session` header, no fallback model, and a 32k custom
  context limit. The AMR channel was tried first but its wallet balance was exhausted.
- Enable automatic review only; leave describe and improve off. PR-Agent posts a review comment and
  is **advisory** initially. Branch protection requires only `gate`.
- Do not auto-add rules or tests from the review. Findings are for the author to act on.

## Consequences

- Review quality and format come from PR-Agent; the repository no longer maintains a custom review
  gate or its acceptance/promotion code.
- PR-Agent comments do not block a merge by themselves. If the workflow fails to run, `gate` still
  blocks on CI; making PR-Agent required is a later decision after observing its signal/noise.
- The review uses the Zen channel and its key; the Zen session limit applies. Fork PRs do not
  receive repository secrets, so external contributions need a maintainer to run `/review` from the
  base repository or a separate trusted workflow.
- Main remains PR-only with zero required reviews and `gate` required (ADR 0004, ADR 0007).

## References

- `.github/workflows/pr-agent.yml`
- `docs/pr-agent.md`
- [the-pr-agent/pr-agent](https://github.com/the-pr-agent/pr-agent)
- [ADR 0006](0006-pr-review-gate.md) (superseded)

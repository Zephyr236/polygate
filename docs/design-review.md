# Design review agent (prototype)

`scripts/design_review.py` is an **advisory** design review of a git diff. It reads the
repository's design documents and the change, then produces a structured report about intent,
assumptions, invariants, alternatives, risks, missing evidence and questions for the author.

It is not a CI gate and does not approve or reject a merge. It exists to surface the "why" that
lint, coverage and mutation gates cannot see. See [ADR 0009](adr/0009-design-review-agent.md).

## Single report

```sh
set -a; . ./.env; set +a
uv run --project backend python scripts/design_review.py \
  --base origin/main --head HEAD --out reports/design-review.md
```

## Panel: independent role reports

`scripts/design_panel.py` runs the same diff and design brief through independent reviewers:
`problem`, `architecture`, `failure`, `security` and `evidence`. Each role gets its own prompt and
writes its own report; disagreements are intentionally preserved rather than averaged.

```sh
uv run --project backend python scripts/design_panel.py \
  --brief docs/design-briefs/my-change.md \
  --base origin/main --head HEAD \
  --out-dir reports/design-review
```

The output is:

```text
reports/design-review/
  index.md          # role -> verdict, confidence, top finding
  problem.md/.json
  architecture.md/.json
  failure.md/.json
  security.md/.json
  evidence.md/.json
```

Use `--roles problem,architecture` to choose a subset and `--max-workers 3` to bound concurrency.
Without a brief the `problem` reviewer should return `insufficient-context` and ask for one; the
other roles still review the diff. Start from
[the design brief template](templates/design-brief.md).

Each role is a separate model call. They share the same model and context, so their blind spots can
still be correlated; use different models or providers if you need genuinely independent opinions.

## CI with Claude Code

`.github/workflows/design-review.yml` runs the panel in CI when a pull request has the
`design-review` label. It uses `pull_request_target`, checks out the **base** commit and runs the
trusted base script; the pull request head is fetched only as git data for the diff and docs. It
never executes PR-controlled code with the model secret. It installs Claude Code, uses the PR body
as the design brief, passes `--engine claude-code`, uploads the reports as an artifact, and
comments the index on the PR.

The workflow uses the Zen endpoint through `ZEN_API_KEY`; it is **advisory** and is not a required
check. It is limited to same-repository PRs because fork PRs do not receive the secret. Add the label
when you want a review; remove it to stop future synchronize runs.

Other forms:

```sh
# Review a saved diff without a git repository
uv run --project backend python scripts/design_review.py --diff-file change.diff

# Print the exact prompt; makes no model call
uv run --project backend python scripts/design_review.py --base HEAD~1 --head HEAD --dry-run

# Machine-readable report
uv run --project backend python scripts/design_review.py --base HEAD~1 --head HEAD --format json
```

| Environment | Default |
| --- | --- |
| `DESIGN_REVIEW_API_KEY` (falls back to `ZEN_API_KEY`) | required |
| `DESIGN_REVIEW_API_BASE` | `https://opencode.ai/zen/go/v1` |
| `DESIGN_REVIEW_MODEL` | `deepseek-v4.1-flash` |
| `DESIGN_REVIEW_SESSION` | fixed UUID for the Zen session header |
| `--max-tokens` | 12000; reasoning models can spend much of this before the JSON |

## Report shape

- **Intent**: the problem and constraints inferred from the change and docs.
- **Assumptions** and **Invariants**: what the change relies on and must preserve.
- **Alternatives**: at least two options with trade-offs.
- **Risks**: concrete failure modes, coupling and operational concerns.
- **Missing evidence**: tests, proofs, benchmarks or observations.
- **Questions**: specific questions for the author.
- **Verdict**: `coherent`, `needs-discussion` or `insufficient-context`.

## Limits

- The model can produce a plausible rationale after the fact. A report is not evidence and not a
  proof; the author owns the decision.
- It reads a bounded diff and a fixed set of docs. It can miss code outside that context.
- The panel produces multiple reports, not a vote. Do not treat a majority verdict as evidence.
- Repository content is untrusted input. Obvious secret assignments are redacted, but review the
  report before sharing it.
- Do not wire this into branch protection until it has been evaluated against known good and bad
  changes; see ADR 0009.

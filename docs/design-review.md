# Design review agent (prototype)

`scripts/design_review.py` is an **advisory** design review of a git diff. It reads the
repository's design documents and the change, then produces a structured report about intent,
assumptions, invariants, alternatives, risks, missing evidence and questions for the author.

It is not a CI gate and does not approve or reject a merge. It exists to surface the "why" that
lint, coverage and mutation gates cannot see. See [ADR 0009](adr/0009-design-review-agent.md).

## Usage

```sh
set -a; . ./.env; set +a
uv run --project backend python scripts/design_review.py \
  --base origin/main --head HEAD --out reports/design-review.md
```

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
- Repository content is untrusted input. Obvious secret assignments are redacted, but review the
  report before sharing it.
- Do not wire this into branch protection until it has been evaluated against known good and bad
  changes; see ADR 0009.

# ADR 0004: Merge policy — pull requests with zero required reviews

- Status: Accepted (the `enforce_admins` decision is superseded by [0007](0007-protect-main.md))
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

`main` is protected by the aggregated `gate` check. The first configuration also required one approving
review. That requirement is unsatisfiable here: GitHub does not let an author approve their own pull
request, and the repository has a single maintainer. Every change would either deadlock or, as happened in
practice, be pushed directly to `main` — which bypasses protection entirely and makes the protection look
stricter than the workflow actually is.

A gate that cannot be satisfied is not a stronger gate; it is a gate people route around.

## Decision

Configure branch protection on `main` as:

- required status check: `gate`, with `strict` (branch must be up to date before merge);
- pull requests required, **0 approving reviews**;
- force pushes and branch deletion disabled;
- `enforce_admins` left off, so the owner can still recover the repository from a broken state.

`gate` itself fails on `failure`, `cancelled` and `skipped` dependencies, so a conditional job that does
not run cannot pass the merge. The gates, not a human click, are the merge criterion.

## Consequences

- The PR flow works for one person: open the PR, wait for `gate`, merge.
- Review quality is not enforced by the platform. It is partially compensated by `code-review` style
  checks and by the gates themselves; a second maintainer would add a human review on top.
- If a second maintainer joins, raise the review count to one in repository settings. Nothing else in the
  workflow changes, and this ADR should be superseded rather than edited.
- The settings are documented here and in `CONTRIBUTING.md`, so the policy can be verified against the
  live configuration instead of inferred from behaviour.

## References

- `CONTRIBUTING.md` (Review policy)
- `.github/workflows/ci.yml` (`gate` job)
- [docs/gates.md](../gates.md)

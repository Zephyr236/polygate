# ADR 0002: Enforce architecture boundaries with tools that actually evaluate rules

- Status: Accepted
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

The gateway depends on a strict layering: `protocols` translate wire formats and must stay pure,
`routing` scores providers, `providers` own transport, `api` is the HTTP surface and `app` is the
composition root. Several tools claim to enforce this.

Evaluating them against a deliberate violation (a probe file importing outside its allowed layer) gave:

| Tool | Version | Verdict |
| --- | --- | --- |
| `tach` | 0.35.3 | `tach check` returned 0 for its own documented `lab/a` → `lab/b` layout; only `tach report` saw usages |
| `eslint-plugin-boundaries` | 7.2.0 / 7.4.4 | `boundaries/dependencies` reported nothing with `checkInternals: true`, even for the plugin's quick-start policy |
| `import-linter` | 2.17 | Broke the contract and named the importing module |
| `dependency-cruiser` | 18.8 | Reported `api-layer-is-leaf: src/api/probe.ts → src/pages/Login.tsx` |

A gate that never fires looks green while enforcing nothing, which is worse than no gate: the
architecture silently drifts and the CI signal is false.

## Decision

Enforce boundaries only with tools proven to fail on a probe:

- `import-linter` layered and forbidden contracts for the backend (`backend/pyproject.toml`).
- `dependency-cruiser` for the frontend (`frontend/.dependency-cruiser.cjs`), including the orphan
  rule that caught an unreferenced module during evaluation.
- `semgrep` design rules for ownership that is not a pure layering fact: HTTP client only in
  `providers/`, FastAPI only in `api/` and `app.py`, SQLite only in `storage.py`, retries sleeps only in
  the scheduler, credentials only through `api_key_env`, no function-level imports.
- `ast-grep` structural rules for the same contracts where AST shape matters (`rules/ast-grep/`).

`tach` and `eslint-plugin-boundaries` are not dependencies. The `design-rules` CI job runs the semgrep
and ast-grep rulesets and the module-size gate.

## Consequences

- Every rule ships with a probe: `AGENTS.md` requires proving the rule fails before trusting it.
- Two overlapping mechanisms (semgrep and ast-grep) exist on purpose for the function-import ban; both
  are verified independently so a tool regression cannot silently disable the ban.
- Dropped tools are recorded here rather than lost, so a future maintainer does not re-evaluate them
  expecting the same outcome without re-running the probe.

## References

- `rules/architecture.yml`, `rules/ast-grep/`, `frontend/.dependency-cruiser.cjs`
- `backend/pyproject.toml` `[tool.importlinter]`
- [docs/gates.md](../gates.md)

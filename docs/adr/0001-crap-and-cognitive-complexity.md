# ADR 0001: Keep CRAP and cognitive complexity as parallel gates

- Status: Accepted
- Date: 2026-11-23
- Deciders: polygate maintainers

## Context

The repository gates every function on CRAP (`crap4py` for Python, `crap-score` for TypeScript) at
`≤ 6`. CRAP multiplies cyclomatic complexity by an uncovered-branch penalty, so a deeply nested
function that happens to be fully covered still scores 1.0 beyond its complexity term and can pass.
The routing, adapter and trace-reporting code contains precisely this shape: nested conditionals whose
branches are all exercised by table-driven tests.

## Decision

Run a second, coverage-independent gate in parallel with CRAP:

- `flake8-cognitive-complexity` with `max-cognitive-complexity = 9` in `backend/.flake8`, wired as the
  `backend cognitive complexity` stage.
- CRAP stays at `≤ 6` for both languages.

Complexity limits are not a substitute for each other: CRAP answers "is this risky to change given its
tests?", cognitive complexity answers "can a person follow the control flow at all?".

## Consequences

- `iter_openai_deltas` was flagged at 8 > 7 on the first run and was split into `_frame_body` plus the
  loop, which also removed a duplicated `startswith`/slice pair.
- A well-covered but deeply nested function now fails the merge even when CRAP passes.
- Refactors are cheaper than suppressions: the gate has no `# noqa` escape for cognitive complexity,
  because the fix is always a small extraction.
- The threshold sits at 9 rather than the Sonar default of 15 so extraction pressure stays real on
  small modules; revisit if legitimate control flow (state machines) starts tripping it.

## References

- `backend/.flake8`
- `scripts/gate.py` (`backend cognitive complexity`)
- [docs/gates.md](../gates.md)

# Architecture review

The architecture review is a separate, advisory agent. It does not review business behavior; it
looks at structure, dependency direction, boundaries, coupling, duplication, testability and
evolvability.

## Scope

- Changed modules and their dependency neighborhood, not a full-repository sweep.
- `docs/architecture.md`, `specs/architecture.yaml`, ADRs and `architecture-baseline.json` are the
  source of truth.
- Skip docs-only, test-only and release-only changes.

## Principles

`specs/architecture.yaml` maps each principle to a deterministic metric:

- `ARCH-LAYER-001`: import directions (import-linter)
- `ARCH-CYCLE-001`: no new cycles (architecture_gate.py)
- `ARCH-SIZE-001`: module size
- `ARCH-COHESION-001`: LCOM
- `ARCH-DUP-001`: duplication
- `ARCH-CRAP-001`: complexity/coverage
- `ARCH-EDGE-001`: side effects and credentials at edges

## Finding schema

```json
{
  "title": "API reaches into storage internals",
  "path": "backend/src/polygate/api/proxy.py",
  "line": 42,
  "principle_id": "ARCH-LAYER-001",
  "severity": "P0",
  "doc_ref": "docs/architecture.md#module-layers",
  "evidence": "edge api -> storage; dependency-cruiser violation",
  "why": "the HTTP surface bypasses the gateway boundary",
  "fix": "move the query behind a gateway port",
  "effort": "S"
}
```

## Policy

- `P0`: a concrete structural violation or new cycle; reported as a blocking advisory finding.
- `P1`: architecture debt that should be scheduled; follow-up.
- `P2`: observation; ignored for merge.
- A finding without a `principle_id` or `doc_ref` is advisory.
- The gate is **advisory** initially and is not a required status. Promote only after two weeks of
  measured false-positive rate below 20%.

## Ratchet

`scripts/architecture_gate.py` compares the **base branch's** `specs/architecture-baseline.json`
with current metrics. A PR may improve the baseline; it may not increase the largest module or add a
cycle. The baseline is updated by `--update` after a reviewed improvement. A missing base baseline
is an error; the first PR that introduces the ratchet is the only bootstrap exception.

## Cost control

- CI-first: no model call when CI is red.
- Skip docs-only changes.
- USD 2 budget, at most five findings, changed scope only.
- The agent gets the metrics JSON, architecture docs and diff; it does not re-run the whole
  deterministic gate suite.

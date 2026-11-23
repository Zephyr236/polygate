# Agent gate candidates

This page defines how an agent-proposed rule or test is judged. The agent may propose; the
policy and the acceptance script decide. Nothing here lets an agent write an active gate
directly.

## Decision policy

`agent/policy.toml` maps a **gap type** to the **artifact kinds** that may address it, and each
artifact to its acceptance oracle.

| Gap type | Allowed artifacts | Oracle |
| --- | --- | --- |
| `static_pattern` | `semgrep_rule`, `ast_grep_rule` | rule |
| `business_invariant` | `property_test`, `stateful_test`, `e2e_test` | pre/post |
| `module_boundary` | `architecture_rule`, `architecture_test` | fixture command |
| `doc_contract` | `doc_assertion` | fixture command |
| `deployment_policy` | `deploy_check`, `policy_proposal` | fixture command / human |
| `internal_design` | `adr_proposal` | human |
| `unknown` | `gap_report` | human |

An artifact that is not listed for a gap type is rejected. A gap that cannot be expressed as a
deterministic check must produce a proposal or gap report, never a synthetic rule or test.

## Candidate layout

```text
agent/candidates/<id>/candidate.json
agent/fixtures/<name>/...                 # positive and negative fixtures
rules/candidates/<name>.yml               # rule candidates (not loaded by the gate)
backend/tests/agent/<name>.py             # test candidates (not run by default)
docs/proposals/<name>.md                  # design and policy proposals
```

A candidate is a JSON object:

```json
{
  "id": "candidate-2026-11-23-001",
  "gap_type": "business_invariant",
  "artifact": "e2e_test",
  "summary": "provider edits survive a restart",
  "incident_ref": "docs/incidents.md#config-restart",
  "invariant": "PUT /admin/providers takes effect after a restart",
  "test_file": "backend/tests/agent/test_restart_persistence.py",
  "pre_fix_commit": "3ee205e",
  "post_fix_commit": "HEAD"
}
```

Required fields are defined per artifact in `agent/policy.toml`.

## Acceptance

```sh
uv run --project backend python scripts/accept_candidate.py --candidate agent/candidates/<id>/candidate.json --repo .
uv run --project backend python scripts/accept_candidate.py --candidate ... --json --soak 3
```

The script needs Python 3.11+ for `tomllib`, so run it through the backend environment. Candidate
rules in `rules/candidates/` are never loaded by the gate; promotion is a separate, explicit step.

| Oracle | Checks |
| --- | --- |
| rule | fires on the positive fixture; silent on the negative fixture and on `backend/src` + `frontend/src` |
| pre/post | test fails at `pre_fix_commit`, passes at `post_fix_commit` (optionally soaked) |
| fixture command | command exits non-zero on the positive fixture and zero on the negative fixture |
| human | schema, path and budget checks only; no mechanical oracle |

Additional checks for every candidate: schema, gap/artifact compatibility, allowed paths, file
existence, duplicate fingerprint, and candidate budget. Tests are also parsed and rejected if
they import `socket`, `subprocess`, `requests`, `httpx` or `urllib`, or call `time.sleep`.

Rules are rejected when they contain absolute paths, commit hashes, an over-long
`pattern-regex`, or a `paths` entry naming a single file. A rule that embeds the incident text
is rejected as overfit.

Exit codes: `0` pass, `1` fail, `2` needs a human decision.

## What this is not

- It does not add a test merely to have a test: a candidate without a named invariant and a
  failing-before/passing-after (or fires-on-bad/silent-on-good) proof fails.
- It does not let an agent modify active rules, thresholds, workflows or gate scripts.
- It does not turn a design question into a rule. Design proposals and policy proposals stay in
  `docs/proposals/` and require a human decision.

## Future workflow

A GitHub workflow may run the agent on pull requests and call this script. Until that workflow
exists, the script is exercised by
`backend/tests/unit/test_agent_gate_policy.py` and `backend/tests/unit/test_agent_gate_accept.py`.

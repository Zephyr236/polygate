---
on:
  pull_request:
    types: [opened, synchronize, reopened]
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
engine:
  id: claude
  model: deepseek-v4.1-flash
  env:
    ANTHROPIC_BASE_URL: https://opencode.ai/zen/go
    ANTHROPIC_API_KEY: ${{ secrets.ZEN_API_KEY }}
network:
  allowed: [defaults, github, opencode.ai]
steps:
  - name: Build rule coverage map
    run: |
      python3 scripts/rule_coverage.py \
        --json reports/rule-coverage.json \
        --markdown reports/rule-coverage.md
tools:
  github:
    toolsets: [repos, issues, pull_requests, actions]
  edit:
  bash:
    - "git *"
    - "rg *"
    - "ls *"
    - "cat *"
    - "python3 *"
    - "python *"
safe-outputs:
  create-issue:
    max: 1
    labels: [agent-candidate]
    expires: 14d
---

# Gate candidate

You are the repository's gate-candidate agent. On every pull request you look at the change,
read the whole repository, and propose **one** deterministic check that the current gates do not
cover.

## Read first

- `AGENTS.md`, `docs/agent-gate.md`, `agent/policy.toml`
- `docs/gates.md`, `docs/architecture.md`, `docs/routing.md`, `docs/providers.md`
- `reports/rule-coverage.json` and `reports/rule-coverage.md`
- `rules/` and `rules/ast-grep/` (existing rules)
- `backend/src/`, `backend/tests/`, `frontend/src/`
- the pull request diff from the GitHub tool `get_pull_request_diff`

Use the whole repository to understand the business rule the diff touches. The diff is the
trigger, not the only input.

## Choose one gap

Classify the gap and pick at most one artifact allowed by `agent/policy.toml`:

- `static_pattern` -> semgrep or ast-grep rule
- `business_invariant` -> property, stateful or e2e test
- `module_boundary` -> architecture rule or architecture test
- `doc_contract` -> doc assertion
- `deployment_policy` -> deploy check
- `internal_design` -> ADR proposal only (no mechanical oracle)
- `unknown` -> gap report only

If the change is already covered, or no deterministic check is justified, stop. Do not invent a
test just to produce output.

## Produce the candidate

Create exactly these files:

- `agent/candidates/<id>/candidate.json` (required fields are in `agent/policy.toml`;
  also include `base_commit` with the output of `git rev-parse HEAD`)
- the artifact:
  - `rules/candidates/<id>.yml` for a rule
  - `backend/tests/agent/test_<id>.py` for a test
  - `scripts/agent_checks/<id>.py` plus a test for a fixture-command check
  - `docs/proposals/<id>.md` for a proposal or gap report
- positive and negative fixtures under `agent/fixtures/<id>-bad/` and `agent/fixtures/<id>-good/`
  when the artifact uses an oracle

For a test, the metadata must name `invariant`, `pre_fix_commit` (the parent of the fixing
commit) and `post_fix_commit`. For a rule, the positive fixture must fail the rule and the
negative fixture must pass it.

Do not modify: `rules/` (active), `scripts/gate.py`, `backend/pyproject.toml`, `.github/`,
`.flake8`, `.bandit`, `.jscpd.json`, `.gitleaks.toml`, `frontend/package.json`, or any existing
test outside `backend/tests/agent/`.

## Self-check

Run the static checks and fix failures, up to three attempts:

```sh
python3 scripts/accept_candidate.py --candidate agent/candidates/<id>/candidate.json --repo . --static-only
```

If it still fails, do not open a candidate issue. Open a gap report instead.

## Build the patch

```sh
git add -N agent rules/candidates backend/tests/agent docs/proposals scripts/agent_checks
git diff --no-color -- agent rules/candidates backend/tests/agent docs/proposals scripts/agent_checks
```

Keep the patch under 120 lines and 60 KB. If it is larger, narrow the candidate.

## Open one issue

Create exactly one issue titled `[gate-candidate] <id>` with this body:

```
<!-- agent-candidate:v1 -->
## Candidate

- id:
- gap type:
- artifact:
- summary:
- self-check: pass / skipped (reason)

```json
<candidate.json>
```

```diff
<the git diff output>
```
```

Do not push, do not comment on the pull request, and do not open a pull request. If no candidate
is justified, call `noop` with a short reason.

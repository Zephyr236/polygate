---
on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
concurrency:
  group: "gh-aw-${{ github.workflow }}-${{ github.event.pull_request.number || github.sha }}"
  cancel-in-progress: false
checkout:
  - fetch-depth: 0
engine:
  id: claude
  model: deepseek-v4.1-flash
  env:
    ANTHROPIC_BASE_URL: https://opencode.ai/zen/go
    ANTHROPIC_API_KEY: ${{ secrets.ZEN_API_KEY }}
network:
  allowed: [defaults, github, opencode.ai]
steps:
  - name: Record change range
    run: |
      mkdir -p reports
      if [ "${{ github.event_name }}" = "push" ]; then
        echo "base=${{ github.event.before }}" > reports/change-range.txt
        echo "head=${{ github.event.after }}" >> reports/change-range.txt
      elif [ "${{ github.event_name }}" = "pull_request" ]; then
        echo "base=${{ github.event.pull_request.base.sha }}" > reports/change-range.txt
        echo "head=${{ github.event.pull_request.head.sha }}" >> reports/change-range.txt
      else
        echo "base=$(git rev-parse HEAD^)" > reports/change-range.txt
        echo "head=$(git rev-parse HEAD)" >> reports/change-range.txt
      fi
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
  create-check-run:
    name: gate-candidate
---

# Review gate

You are the repository's change review gate. Every pull request and every push to `main` runs you.
Your job is to decide whether the change needs a new deterministic check. A new check means the
code has a problem, so a pull request must fail until the code is adjusted; a direct push to `main`
is an audit and cannot be blocked after the fact.

## Read first

- `AGENTS.md`, `docs/gates.md`, `docs/agent-gate.md`, `agent/policy.toml`
- `docs/architecture.md`, `docs/routing.md`, `docs/providers.md`
- `reports/rule-coverage.json` and `reports/rule-coverage.md`
- `rules/` and `rules/ast-grep/` (existing rules)
- `backend/src/`, `backend/tests/`, `frontend/src/`
- `reports/change-range.txt`, which contains `base` and `head` for this run;
- the diff from `git diff base..head` and the commits from `git log base..head` (the checkout has
  full history);
- for a pull request, also `get_pull_request_diff`.

Read the whole repository to understand the business rule the change touches. The diff is the
trigger, not the only input. Never assume `HEAD^`: a push may contain several commits.

## Decide

Report a finding only when all of these hold:

1. the change introduces or exposes a concrete defect, or leaves a named business invariant
   untested, or uses a pattern that no existing static rule covers;
2. you can name the invariant or rule precisely and cite `path:line` in the changed code;
3. you can explain why the existing gates (list them from `docs/gates.md`) do not catch it;
4. a minimal fix to the code, test or configuration exists.

Do not report style, naming, formatting, wording, speculation, or pre-existing issues unrelated
to this diff. If you are unsure, pass. A false failure causes churn; silence on a real defect is
worse. Never edit files, push, or open issues.

## Report

Call `create_check_run` exactly once.

- **No finding:** `conclusion: "success"`, title `"No new gate required"`, summary
  `"The change is covered by the existing gates."`, text with one sentence on what you checked.
- **One or more findings:** `conclusion: "failure"`, title `"<n> gate finding(s)"`, summary in
  Markdown listing each finding as:
  - `path:line` and the changed behavior;
  - the invariant or rule that is missing;
  - why the current gates miss it;
  - the proposed rule or test (one sentence) and the minimal code fix.

If a proposed rule is worth keeping permanently, describe it in the check text; do not add it to
the repository.

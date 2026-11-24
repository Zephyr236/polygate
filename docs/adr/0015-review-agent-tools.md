# ADR 0015: Give the design agent read-only Bash and a verifier subagent

- Status: Accepted
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The design gate could only read files. It could not run `git diff`, inspect history, execute a
targeted test, or spawn an independent verifier, so it sometimes asked for evidence it could have
collected itself. Actions gives the workflow `contents: read`; Bash cannot push or change the
repository, but it can execute code from the PR worktree and read the runner environment.

## Decision

- For pull requests whose author association is `OWNER`, `MEMBER` or `COLLABORATOR`, the gate agent
  gets an allowlisted Bash: `git status/diff/log/show`, `rg`, `ls`, `cat`, `head`, `tail`, `pytest`,
  and `uv run pytest`. It also gets an `Agent` tool and a read-only `verifier` subagent with the same
  tools.
- Fork or otherwise untrusted PRs still receive a read-only `Read/Grep/Glob` review; they do not get
  Bash.
- The gate process removes `GITHUB_TOKEN`, `GH_TOKEN`, `ADMIN_TOKEN`, `PROXY_API_KEY`,
  `DESIGN_REVIEW_API_KEY`, `ZEN_API_KEY`, `AMR_API_KEY` and `OK8888_API_KEY` from the agent's
  inherited environment before the SDK starts. The Anthropic model key remains in the Claude Code
  subprocess because the CLI needs it; Bash can in principle read it.
- Edit, Write, WebFetch, WebSearch and NotebookEdit remain disallowed.

## Consequences

- Trusted PRs can run targeted tests and inspection; the agent can gather evidence instead of
  guessing.
- Bash executes PR code with the model key in the environment. The command allowlist and removed
  GitHub/provider credentials reduce the impact, but do not eliminate exfiltration risk; this gate
  is not a security sandbox.
- Fork PRs remain reviewable without Bash; their status is still required.
- A command outside the allowlist is denied and the agent must decide from available evidence.

## References

- `scripts/design_gate.py`, `.github/workflows/design-gate.yml`
- [ADR 0010](0010-required-design-gate.md), [ADR 0014](0014-ci-first-design-gate.md)

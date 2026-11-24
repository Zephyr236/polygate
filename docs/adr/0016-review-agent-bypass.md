# ADR 0016: The design reviewer runs with bypass permissions

- Status: Accepted (supersedes the tool restrictions in [0015](0015-review-agent-tools.md))
- Date: 2026-11-24
- Deciders: polygate maintainers

## Context

The design reviewer was restricted to a read-only tool list and a small Bash allowlist. That limited
its ability to run tests, inspect unknown tooling and delegate independent checks. The repository
already removes GitHub and provider credentials before the agent starts, and the workflow has
`contents: read`; the agent cannot push or otherwise change the repository.

## Decision

- Run the gate agent with `permission_mode = "bypassPermissions"` and the full Claude Code toolset,
  including Bash, web tools and the `Agent` subagent tool. No tool or command allowlist is applied.
- Keep `GITHUB_TOKEN`, `GH_TOKEN`, `ADMIN_TOKEN`, `PROXY_API_KEY`, `DESIGN_REVIEW_API_KEY`,
  `ZEN_API_KEY`, `AMR_API_KEY` and `OK8888_API_KEY` out of the agent's inherited environment.
- Keep the Anthropic model credential in the Claude Code process because the CLI needs it.
- The agent may modify its local worktree, but it has no write-capable GitHub credential and the
  workflow does not push its changes.

## Consequences

- The reviewer can execute tests, inspect history and use subagents without permission prompts,
  which improves the evidence it can collect.
- PR code can execute with the model key in the environment. Bash, web tools and subagents make
  exfiltration technically possible; this is explicitly **not a security sandbox**.
- Fork PRs receive the same full tool access. A maintainer who does not accept that risk should
  disable the gate for untrusted contributors or restore the restricted mode.
- The gate remains fail-closed on agent errors, budget exhaustion, missing status or any finding.

## References

- `scripts/design_gate.py`, `.github/workflows/design-gate.yml`
- [ADR 0015](0015-review-agent-tools.md) (superseded)

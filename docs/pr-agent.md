# PR review with PR-Agent

Pull requests are reviewed by [PR-Agent](https://github.com/the-pr-agent/pr-agent), an open-source
review agent. The workflow is `.github/workflows/pr-agent.yml`.

## What runs

- On PR `opened`, `reopened`, `ready_for_review` and `synchronize`, PR-Agent posts a review comment.
- A comment containing `/review` (or another PR-Agent command) on a PR triggers the action again.
- Automatic `describe` and `improve` are disabled; review is the only automatic command.

PR-Agent is **advisory**. It does not create a required status check, and its findings do not block a
merge by themselves. The required checks are `gate` (all CI gates) and the pull-request policy.

## Model and credentials

The action uses the AMR OpenAI-compatible endpoint:

| Setting | Value |
| --- | --- |
| `OPENAI__API_BASE` | `https://amr-link.open-design.ai/v1` |
| `CONFIG__MODEL` | `openai/deepseek-v4.1-flash-eco` |
| `OPENAI__KEY` | `AMR_API_KEY` repository secret |
| `CONFIG__CUSTOM_MODEL_MAX_TOKENS` | `32000` |

No fallback model is configured. The AMR channel has a concurrency limit, so several simultaneous
PR reviews queue at the provider.

## Commands

```sh
gh pr comment <number> --body "/review"
gh pr comment <number> --body "/describe"
gh pr comment <number> --body "/help"
```

## Limitations

- Fork PRs do not receive repository secrets, so PR-Agent cannot run on them by default. A
  maintainer can run `/review` from the base repository.
- The review is model-generated. Treat it as a second opinion, not a deterministic gate.
- The action needs `issues: write` and `pull-requests: write` to post comments.

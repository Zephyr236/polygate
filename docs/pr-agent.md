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

The action uses the Zen OpenAI-compatible endpoint:

| Setting | Value |
| --- | --- |
| `OPENAI__API_BASE` | `https://opencode.ai/zen/go/v1` |
| `CONFIG__MODEL` | `openai/deepseek-v4.1-flash` |
| `OPENAI__KEY` | `ZEN_API_KEY` repository secret |
| `LITELLM__EXTRA_HEADERS` | `{"x-opencode-session": "11111111-1111-4111-8111-111111111111"}` |
| `CONFIG__CUSTOM_MODEL_MAX_TOKENS` | `32000` |

No fallback model is configured. Zen requires the `x-opencode-session` header; the fixed UUID keeps
all PR-Agent calls in one session. The AMR channel was tried first but its wallet balance was
exhausted.

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

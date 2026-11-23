# polygate

**A self-hosted routing gateway that turns several uneven DeepSeek V4.1 Flash channels into one reliable API.**

[![ci](https://github.com/Zephyr236/polygate/actions/workflows/ci.yml/badge.svg)](https://github.com/Zephyr236/polygate/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Node ≥22](https://img.shields.io/badge/node-%3E%3D22.12-339933)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Gates: 30](https://img.shields.io/badge/gates-30%20enforced-brightgreen)

English | [简体中文](#中文说明)

---

## Why

Cheap DeepSeek channels come with uneven quality. One caps concurrency at ten and answers
`tier_limit_exceeded` when you exceed it. Another rate limits per session, requires a session header, and caches
prompts inside that session. A third is dirt cheap but takes twenty seconds and folds under load. Pointing an
application at any one of them means inheriting whichever failure mode that channel happens to have today.

polygate pools them. It speaks OpenAI and Anthropic wire formats, scores every candidate on success rate,
latency, a user-defined cost coefficient and cache-hit rate, then retries and fails over on its own. Each
channel keeps its own concurrency, retry, time-window, timeout and cost settings, and each channel's
behaviour is visible on a dashboard.

## Features

- **Channels are data, not code.** Add a provider with a TOML block or in the admin UI. Auth style, session
  headers, stream-usage placement and custom error payloads are configuration fields, not branches in an adapter.
- **Score-based routing.** Weighted blend of success rate, latency, inverse cost and cache hits, with priority
  tiers, retries with jittered backoff, a circuit breaker and automatic failover.
- **Two protocols, one pool.** `POST /v1/chat/completions` (OpenAI) and `POST /v1/messages` (Anthropic), streaming
  included, with usage and cache accounting normalized across channels.
- **Concurrency lanes.** Each channel exposes `lanes × max_concurrency` slots. Per-session rate limits become
  independent lanes with their own session id.
- **Per-channel analytics.** Calls, success, p50/p95 latency, tokens, cache hits, cost, switches and circuit state,
  with live SSE updates and a Prometheus endpoint.
- **One-command deploy.** A multi-stage image builds the SPA and serves it from the same process as the API.

## Quick start

### Docker (recommended)

```sh
git clone https://github.com/Zephyr236/polygate.git && cd polygate
cp .env.example .env                 # set ADMIN_TOKEN and your channel keys
docker compose -f deploy/docker-compose.yml up -d --build
```

Open <http://localhost:8080>, enter `ADMIN_TOKEN`, and the dashboard appears.

### Local development

```sh
cd backend
uv sync --extra dev
uv run uvicorn polygate.app:create_app --factory --port 8080

cd frontend                            # proxies /admin and /v1 to :8080
pnpm install
pnpm dev                               # http://localhost:5173
```

## Usage

```sh
curl http://localhost:8080/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{
    "model": "deepseek-v4.1-flash",
    "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
    "max_tokens": 4000
  }'
```

```json
{
  "id": "polygate-amr",
  "object": "chat.completion",
  "model": "deepseek-v4.1-flash-eco",
  "choices": [{ "index": 0, "message": { "role": "assistant", "content": "PONG" }, "finish_reason": "stop" }],
  "usage": { "prompt_tokens": 36, "completion_tokens": 11, "total_tokens": 47 }
}
```

Pass `"stream": true` for SSE. When every candidate fails the gateway answers `502` with an envelope listing each
attempt and its normalized error class, so a caller can see exactly what was tried.

## Configuration

Providers are seeded from `POLYGATE_CONFIG` (see [`providers.example.toml`](providers.example.toml)) and can be
edited in the admin UI afterwards. **Keys are referenced by environment variable name and never stored inline.**

```toml
[[provider]]
id = "amr"
base_url = "https://amr-link.open-design.ai/v1"
model = "deepseek-v4.1-flash-eco"
api_key_env = "AMR_API_KEY"        # the key itself lives in the environment
max_concurrency = 10               # measured per-key cap
max_tokens_min = 3000              # reasoning models eat small budgets
priority = 1

[provider.retry]
attempts = 2
base_delay_ms = 200

[[provider.error_rules]]
json_path = "error.code"
match = "tier_limit_exceeded"
error_class = "concurrency_limited"
retryable = true
```

Full field reference: [docs/config-reference.md](docs/config-reference.md).

## How routing works

```
score = w_success · success_rate
      + w_speed   · speed          (target_latency / observed_latency, clamped)
      + w_cost    · inverse_cost   (rescaled so the cheapest candidate scores 1)
      + w_cache   · cache_hit_rate
```

Hard filters run first: disabled channels, channels outside their UTC windows, saturated channels and cooling
circuits are skipped. Failures retry inside the channel, then walk down the ranked list, up to `max_switches`.
Formulas, presets and lane semantics: [docs/routing.md](docs/routing.md).

## Architecture

```text
client ──▶ /v1/chat/completions | /v1/messages
              │
              ▼
        protocols/*   pure translation for both wire formats
              │
              ▼
        routing/      scorer → scheduler → health (EMA, lanes, open/half-open/closed)
              │
              ▼
        providers/    auth · session · transport · error normalization
              │
              ▼
        amr-link · opencode zen · … (any OpenAI- or Anthropic-compatible channel)
```

| Layer | Modules | Rule enforced |
| --- | --- | --- |
| Composition root | `app` | may import everything |
| HTTP surface | `api.*` | gateway only |
| Orchestration | `gateway` | builds the scheduler, records cost |
| Routing | `routing.*`, `metrics` | pure, clock-injected |
| Adapters | `providers.*` | sole owner of `httpx` |
| Translation | `protocols.*` | leaf, no framework |
| Foundations | `config`, `storage` | leaf |

The table is not aspirational: `import-linter` (backend) and `dependency-cruiser` (frontend) fail the build when it
is broken, and `semgrep` / `ast-grep` rules cover ownership facts that are not mere layering. See
[docs/architecture.md](docs/architecture.md).

## Dashboard

| Endpoint | Purpose |
| --- | --- |
| `GET /admin/metrics?range=15m\|1h\|24h\|7d` | overview totals, per-provider rows, time series, health |
| `GET /admin/metrics/stream` | SSE snapshot every two seconds |
| `GET /admin/events` | recent switch, config and breaker events |
| `GET` / `PUT /admin/providers` | read and replace the provider pool |
| `POST /admin/simulate` | score breakdown without calling upstreams |
| `GET /metrics` | Prometheus text |

All `/admin/*` routes require `Authorization: Bearer $ADMIN_TOKEN`. `/v1/*` requires `PROXY_API_KEY` when set;
leave it unset for loopback-only use.

## Quality gates

Merge to `main` requires the aggregated `gate` check. Every job in it is a real gate; `gate` fails on any
`failure`, `cancelled` **and `skipped`** result, so a conditional job can never turn the pipeline green by not
running.

| Area | Gate | Threshold |
| --- | --- | --- |
| Backend | `ruff` lint and format | clean |
| | `mypy --strict` | zero errors |
| | `import-linter` | 5 contracts kept |
| | `pytest` branch coverage | ≥ 90% (97.3%) |
| | `crap4py` | ≤ 6 per function |
| | `mutmut` mutation score | ≥ 75% (80.6%) |
| | `vulture` and `interrogate` | no dead code, ≥ 80% docstrings |
| | `bandit` and `pip-audit` (runtime set) | clean |
| | `deptry` | no unused or missing deps |
| | `semgrep` and `ast-grep` | design and structural rules |
| | `hypothesis` state machines | invariants hold |
| | `schemathesis` contracts | no 5xx |
| | `flake8-cognitive-complexity` | ≤ 9 per function |
| | `pytest -m e2e` | 10 pass |
| Frontend | `eslint`, `prettier`, `tsc` | clean |
| | `dependency-cruiser` and `knip` | zero violations, no dead exports |
| | `vitest` branch coverage | ≥ 85% (88.5%) |
| | `crap-score` | ≤ 6 per function |
| | `stryker` mutation score | ≥ 70% (77.8%) |
| | `playwright` | 4 browser tests pass |
| Repo-wide | module size, LCOM cohesion, `jscpd` | file ≤ 320, function ≤ 60 · ≥ 0.5 · < 5% |
| | docs gate (incl. ADR shape) and `gitleaks` | zero problems, no secrets |
| | CodeQL (`python`, `javascript-typescript`) | analysis completes; SARIF uploaded |

Reproduce the whole set locally:

```sh
uv run python scripts/gate.py --all --mutation --e2e
```

Full table with the reasoning behind each tool: [docs/gates.md](docs/gates.md). Decisions that shaped the suite:
[docs/adr/index.md](docs/adr/index.md).

## Repository layout

```text
backend/     FastAPI gateway, routing core, adapters, SQLite metrics, tests (unit/integration/e2e)
frontend/    React SPA: dashboard, provider editor, route simulation, playground
deploy/      Multi-stage Dockerfile and compose file (one image, SPA served by the API process)
rules/       semgrep and ast-grep rule sets for architecture and ownership contracts
docs/        Architecture, routing, providers, metrics, operations, gates, API, ADRs
scripts/     gate.py plus threshold readers for CRAP, mutation, docs, size, cohesion
```

## Documentation

- [Architecture](docs/architecture.md)
- [Routing](docs/routing.md)
- [Providers](docs/providers.md)
- [Metrics and dashboard](docs/metrics.md)
- [Operations](docs/operations.md)
- [API](docs/api.md)
- [Frontend](docs/frontend.md)
- [Quality gates](docs/gates.md)
- [Configuration reference](docs/config-reference.md)
- [Architecture decision records](docs/adr/index.md)

Maintainer notes for humans and agents: [AGENTS.md](AGENTS.md) · [CONTRIBUTING.md](CONTRIBUTING.md).

## Contributing

Pull requests are the only path to `main`. The aggregated `gate` check decides the merge, and it fails on a
failed, cancelled **or skipped** job, so a gate that does not run is never mistaken for one that passed.
This is a single-maintainer repository, and GitHub forbids self-approval, so the review requirement is
**0**: the gates carry the weight. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[ADR 0004](docs/adr/0004-merge-policy.md).

## Roadmap

- Weighted least-connections queue behind a saturated channel instead of an immediate skip.
- Multi-key pools per channel with independent breaker state.
- Per-call trace export for offline replay.

## License

[MIT](LICENSE).

---

## 中文说明

**把几家质量参差、限额各异的 DeepSeek V4.1 Flash 渠道,聚合成一个稳定可用的 API。**

[English](README.md) | 简体中文

### 为什么做这个

便宜的 DeepSeek 渠道质量并不齐整:有的并发硬顶 10,超了直接回 `tier_limit_exceeded`;有的按会话限流,
必须带会话头,而且同一个会话内的提示缓存可以命中;还有的很便宜但要跑二十秒、一上量就超时。把应用直接
指向其中任意一家,就等于把这家渠道当天的故障模式变成你自己服务的故障模式。

polygate 把它们池化:对外提供 OpenAI 与 Anthropic 两种协议,按成功率、延迟、用户自定义成本系数与缓存命中
给每个候选打分,失败自动换源;每个渠道保留自己的并发、重试、可用时段、超时与成本设置,并在看板上呈现每个
渠道的真实表现。

### 特性

- **渠道即数据,不是代码。** 新增一个渠道 = 一段 TOML 或管理台表单。鉴权方式、会话头、流式 usage 的位置、
  非标准错误体都是配置字段,而不是适配器里的 if 分支。
- **打分路由。** 成功率、延迟、成本倒数、缓存命中加权求和;再叠加优先级分层、带抖动的指数退避重试、
  熔断器和自动切换。
- **一套池,两种协议。** `POST /v1/chat/completions`(OpenAI)与 `POST /v1/messages`(Anthropic),都支持流式,
  usage 与缓存计数已归一。
- **并发车道。** 每个渠道暴露 `lanes × max_concurrency` 个槽位;对按会话限流的渠道,每条车道就是独立会话。
- **按渠道的数据看板。** 调用量、成功率、p50/p95 延迟、token、缓存命中、成本、切换次数与熔断状态,
  支持 SSE 实时推送,并保留 Prometheus 端点。
- **一条命令部署。** 多阶段镜像构建 SPA,并由同一个进程同时提供 API 与静态页面。

### 快速开始

```sh
git clone https://github.com/Zephyr236/polygate.git && cd polygate
cp .env.example .env                  # 填 ADMIN_TOKEN 与各渠道密钥
docker compose -f deploy/docker-compose.yml up -d --build
```

浏览器打开 <http://localhost:8080>,输入 `ADMIN_TOKEN` 即可进入管理台。

本地开发:

```sh
cd backend && uv sync --extra dev
uv run uvicorn polygate.app:create_app --factory --port 8080
cd frontend && pnpm install && pnpm dev   # http://localhost:5173
```

### 调用示例

```sh
curl http://localhost:8080/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"deepseek-v4.1-flash","messages":[{"role":"user","content":"Reply with exactly: PONG"}],"max_tokens":4000}'
```

加 `"stream": true` 走 SSE。所有候选都失败时返回 `502`,响应体里列出每一次尝试及其归一后的错误类型,
调用方可以直接看出试过哪些渠道、各自为何失败。

### 配置

渠道从 `POLYGATE_CONFIG` 指向的种子文件加载(示例见 [`providers.example.toml`](providers.example.toml)),
之后可在管理台里直接增删改。**密钥只以环境变量名引用,仓库内从不存放明文密钥。**

```toml
[[provider]]
id = "amr"
base_url = "https://amr-link.open-design.ai/v1"
model = "deepseek-v4.1-flash-eco"
api_key_env = "AMR_API_KEY"    # 真正的密钥在环境变量里
max_concurrency = 10           # 实测的 per-key 并发上限
max_tokens_min = 3000          # 推理模型会吃掉过小的预算
priority = 1
```

完整字段说明:[docs/config-reference.md](docs/config-reference.md)。

### 路由算法

```
score = w_success · 成功率
      + w_speed   · 速度      (目标延迟 / 观测延迟,截断到 0..1)
      + w_cost    · 成本倒数  (归一化:最便宜的候选记 1)
      + w_cache   · 缓存命中率
```

先做硬过滤:停用、不在可用时段、并发已满、熔断中的渠道直接剔除;渠道内失败按退避重试,仍失败则按排名
往下切换,单请求最多切换 `max_switches` 次。公式、三套预设权重与车道语义见 [docs/routing.md](docs/routing.md)。

### 质量门禁

合并到 `main` 必须通过聚合检查 `gate`,并且 `gate` 会把 `failure`、`cancelled` **以及 `skipped`** 都判为失败 ——
条件 job 不能靠"不运行"把流水线刷成绿色。

| 范围 | 门禁 | 阈值 |
| --- | --- | --- |
| 后端 | `ruff` 与格式检查 | 0 违规 |
| | `mypy --strict` | 0 错误 |
| | `import-linter` | 5 条契约全保持 |
| | `pytest` 分支覆盖率 | ≥ 90%(当前 97.3%) |
| | `crap4py` | 每函数 CRAP ≤ 6 |
| | `mutmut` 变异分数 | ≥ 75%(当前 80.6%) |
| | `vulture` / `interrogate` | 无死代码 / docstring ≥ 80% |
| | `bandit` / `pip-audit`(运行时依赖集) | 0 问题 |
| | `deptry` | 无多余或缺失依赖 |
| | `semgrep` / `ast-grep` | 设计规则与结构规则 |
| | `hypothesis` 状态机 | 不变量成立 |
| | `schemathesis` 契约 | 无 5xx |
| | `flake8-cognitive-complexity` | 每函数 ≤ 9 |
| | `pytest -m e2e` | 10 个全过 |
| 前端 | `eslint` / `prettier` / `tsc` | 0 违规 |
| | `dependency-cruiser` / `knip` | 0 越界 / 无死导出 |
| | `vitest` 分支覆盖率 | ≥ 85%(当前 88.5%) |
| | `crap-score` | 每函数 ≤ 6 |
| | `stryker` 变异分数 | ≥ 70%(当前 77.8%) |
| | `playwright` | 4 个浏览器用例全过 |
| 全仓库 | 模块体积 / LCOM 内聚 / `jscpd` 重复 | 文件 ≤ 320 行、函数 ≤ 60 行 · ≥ 0.5 · < 5% |
| | 文档门禁(含 ADR 结构)· `gitleaks` | 0 问题 · 无密钥 |
| | CodeQL(`python`、`javascript-typescript`) | 分析完成,SARIF 已上传 |

本地一键复现:

```sh
uv run python scripts/gate.py --all --mutation --e2e
```

每一条门禁为什么存在:[docs/gates.md](docs/gates.md);影响门禁体系的关键决策记录在 [docs/adr/index.md](docs/adr/index.md)。

### 目录结构

```text
backend/     FastAPI 网关、路由核心、适配器、SQLite 指标与测试(unit/integration/e2e)
frontend/    React 管理台:数据看板、渠道编辑、路由试跑、Playground
deploy/      多阶段 Dockerfile 与 compose 文件(单镜像,API 进程同时提供 SPA)
rules/       semgrep 与 ast-grep 规则:架构与归属契约
docs/        架构、路由、渠道、指标、运维、门禁、API、ADR
scripts/     gate.py 以及 CRAP / 变异 / 文档 / 体积 / 内聚阈值读取脚本
```

### 贡献

`main` 只接受 Pull Request。合并与否由聚合检查 `gate` 决定,它对 `failure`、`cancelled` **以及 `skipped`**
都判失败 —— 没有运行的 job 不会被误当成通过。本仓库为单人维护,而 GitHub 不允许作者自审,因此 review
要求为 **0**:把关的是门禁本身。详见 [CONTRIBUTING.md](CONTRIBUTING.md) 与
[ADR 0004](docs/adr/0004-merge-policy.md)。

### 说明

- 本仓库公开,但**不含任何真实渠道密钥**;密钥只存在于本地 `.env` 与 GitHub Actions secrets。
- 若只在本机使用,可以不设 `PROXY_API_KEY`;一旦对外暴露端口请务必设置。
- 代码注释遵循"只写功能描述"的约定,由 `ruff` 的 D 规则集与 `eslint-plugin-jsdoc` 把关。

## License / 许可

[MIT](LICENSE)。

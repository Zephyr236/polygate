# Frontend

The frontend is a React 19 single-page app served by the gateway in production and by Vite in development.

## Stack

| Concern | Choice |
| --- | --- |
| Runtime | React 19, TypeScript 5.9 |
| Build | Vite 7 |
| Data | TanStack Query 5 |
| Charts | Recharts 3 |
| Tests | Vitest 4, Testing Library, MSW 2 |
| Mutation | Stryker 10 with the Vitest runner |
| Browser E2E | Playwright 1.65 |

## Pages

- **Dashboard**: KPI tiles, traffic chart, provider cards and a detail table.
- **Providers**: searchable, editable provider cards for ids, URLs, protocol, auth, session headers,
  lanes, concurrency, cost, priority and tags.
- **Routes**: simulation of candidate scores and eligibility reasons.
- **Playground**: live chat through `/v1/chat/completions`, streaming or not.

## Layering

`dependency-cruiser` enforces these boundaries:

- `src/api` may not import pages, components or state.
- `src/utils` stays pure and may not import React or the API client.
- `src/state` may not import pages.
- Production code may not import test tooling or the `tests/` tree.
- `knip` fails on unused files, exports, types and dependencies.

`eslint-plugin-boundaries` was evaluated for statement-level rules but its selector matching proved inert on this stack (its own documented example produced no diagnostics), so the boundaries live in `dependency-cruiser` instead. See `docs/gates.md`.

## Development

```sh
pnpm install
pnpm dev        # proxies /admin and /v1 to 127.0.0.1:8080
pnpm test       # unit and component tests with coverage
pnpm run e2e    # Playwright against a preview build
```

## Coverage and CRAP

Coverage is emitted as Istanbul JSON so `crap-score` can compute per-function risk. `scripts/crap_js_gate.py` reads that report and fails when any function exceeds CRAP 6.

## Language and visual system

- Default locale is simplified Chinese; the top bar switches to English and persists the choice in
  `localStorage`.
- All UI copy lives in `src/i18n/zh-CN.json` and `src/i18n/en.json`; components use `useI18n`.
- The visual system is Blueprint Grid: cool paper background, a faint engineering grid, cobalt
  actions, thin borders, compact data typography and IBM Plex Mono for numbers.
- Every form control has a visible label, focus state and inline validation message.

## API keys

The **API keys** tab generates scoped caller credentials. A secret is shown once; each key stores
its provider allowlist and tier (`premium`, `standard`, `economy`) and can be revoked immediately.

The shell uses a persistent left sidebar for navigation; below 900px it collapses into a horizontally scrollable header. API key provider selection is a searchable multi-select with removable chips, not a checkbox wall, so large provider pools stay usable.

Provider editing uses expandable list rows; API keys and their generated secrets are also shown as full-width list rows.

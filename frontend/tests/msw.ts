/**
 * MSW server factory and baseline handlers for admin and proxy endpoints.
 */

import { http, HttpResponse, delay } from "msw";
import { setupServer } from "msw/node";

import type { MetricsResponse, ProviderConfig, ProviderHealth } from "@/api/types";

/** Provider fixtures used across component tests. */
export const providerFixtures: ProviderConfig[] = [
  {
    id: "amr",
    base_url: "https://amr.example",
    protocol: "openai",
    model: "deepseek-v4.1-flash-eco",
    aliases: [],
    api_key_env: "AMR_API_KEY",
    auth_style: "bearer",
    session_header: null,
    session_mode: "none",
    lanes: 1,
    max_concurrency: 10,
    max_tokens_min: 3000,
    stream_usage: "none",
    cost_coefficient: 1,
    priority: 1,
    enabled: true,
    tags: [],
    api_key_configured: true,
  },
  {
    id: "zen",
    base_url: "https://zen.example/zen/go",
    protocol: "anthropic",
    model: "deepseek-v4.1-flash",
    aliases: [],
    api_key_env: "ZEN_API_KEY",
    auth_style: "bearer",
    session_header: "x-opencode-session",
    session_mode: "uuid-per-request",
    lanes: 1,
    max_concurrency: 4,
    max_tokens_min: 0,
    stream_usage: "message_delta",
    cost_coefficient: 1,
    priority: 2,
    enabled: true,
    tags: ["test"],
    api_key_configured: true,
  },
];

/** Health fixtures keyed to provider fixtures. */
export const healthFixtures: ProviderHealth[] = [
  {
    id: "amr",
    state: "closed",
    success_rate: 0.98,
    latency_ms: 2100,
    cache_hit_rate: 0.2,
    calls: 20,
    failures: 1,
    cooldown_seconds: 0,
    inflight: 3,
    capacity: 10,
    enabled: true,
  },
  {
    id: "zen",
    state: "half_open",
    success_rate: 0.71,
    latency_ms: 1400,
    cache_hit_rate: 0.6,
    calls: 12,
    failures: 4,
    cooldown_seconds: 5,
    inflight: 1,
    capacity: 4,
    enabled: true,
  },
];

/** Metrics fixture with two providers and two buckets. */
export const metricsFixture: MetricsResponse = {
  range: "1h",
  overview: {
    calls: 32,
    failures: 5,
    success_rate: 0.84,
    prompt_tokens: 1200,
    completion_tokens: 400,
    cache_hit_rate: 0.3,
    cost_usd: 0.004,
    providers: 2,
  },
  providers: [
    {
      provider_id: "amr",
      calls: 20,
      ok: 19,
      failures: 1,
      avg_latency: 2100,
      max_latency: 3500,
      prompt_tokens: 800,
      completion_tokens: 250,
      reasoning_tokens: 40,
      cache_read_tokens: 160,
      cost: 0.003,
      switches: 2,
    },
    {
      provider_id: "zen",
      calls: 12,
      ok: 8,
      failures: 4,
      avg_latency: 1400,
      max_latency: 2600,
      prompt_tokens: 400,
      completion_tokens: 150,
      reasoning_tokens: 10,
      cache_read_tokens: 120,
      cost: 0.001,
      switches: 3,
    },
  ],
  series: [
    { provider_id: "amr", bucket: 1_800_000_000, calls: 10, ok: 9, failures: 1, avg_latency: 2000 },
    { provider_id: "zen", bucket: 1_800_000_000, calls: 6, ok: 4, failures: 2, avg_latency: 1500 },
    { provider_id: "amr", bucket: 1_800_000_300, calls: 10, ok: 10, failures: 0, avg_latency: 2200 },
  ],
  health: healthFixtures,
};

/** Baseline handlers; tests override individual routes per case. */
const handlers = [
  http.get("/admin/providers", () =>
    HttpResponse.json({ providers: providerFixtures, health: healthFixtures }),
  ),
  http.put("/admin/providers", async ({ request }) => {
    const body = (await request.json()) as { providers: ProviderConfig[] };
    return HttpResponse.json({ providers: body.providers });
  }),
  http.get("/admin/metrics", ({ request }) => {
    const range = new URL(request.url).searchParams.get("range") ?? "1h";
    return HttpResponse.json({ ...metricsFixture, range });
  }),
  http.get("/admin/events", () => HttpResponse.json({ events: [] })),
  http.post("/admin/simulate", async () =>
    HttpResponse.json({
      model: "deepseek-v4.1-flash",
      prompt_length: 5,
      ranking: [
        {
          provider_id: "amr",
          success: 0.98,
          speed: 1,
          cost: 1,
          cache: 0.2,
          total: 0.94,
          priority: 1,
        },
      ],
      decisions: [{ provider_id: "amr", model: "m", eligible: true, reasons: [] }],
    }),
  ),
  http.post("/v1/chat/completions", async ({ request }) => {
    const body = (await request.json()) as { stream?: boolean };
    if (body.stream) {
      const frames = [
        'data: {"choices":[{"delta":{"content":"PO"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"NG"}}],"model":"amr"}',
        "",
        'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}',
        "",
        "data: [DONE]",
        "",
      ].join("\n");
      return new HttpResponse(frames, { headers: { "content-type": "text/event-stream" } });
    }
    await delay(1);
    return HttpResponse.json({
      model: "amr",
      choices: [{ message: { content: "PONG" } }],
      usage: { prompt_tokens: 5, completion_tokens: 2, prompt_tokens_details: { cached_tokens: 1 } },
    });
  }),
];

/** Create an MSW node server with the baseline handlers. */
export function createServer() {
  return setupServer(...handlers);
}

/**
 * Wire types mirrored from the polygate admin and proxy API.
 */

/** Health snapshot for one provider. */
export interface ProviderHealth {
  id: string;
  state: "closed" | "open" | "half_open";
  success_rate: number;
  latency_ms: number;
  cache_hit_rate: number;
  calls: number;
  failures: number;
  cooldown_seconds: number;
  inflight: number;
  capacity: number;
  enabled: boolean;
}

/** One upstream channel configuration. */
export interface ProviderConfig {
  id: string;
  base_url: string;
  protocol: "openai" | "anthropic";
  model: string;
  aliases: string[];
  api_key_env: string;
  auth_style: "bearer" | "x-api-key" | "both";
  session_header: string | null;
  session_mode: "none" | "uuid-per-request" | "uuid-per-lane";
  lanes: number;
  max_concurrency: number;
  max_tokens_min: number;
  stream_usage: "include_usage" | "message_delta" | "none";
  cost_coefficient: number;
  priority: number;
  enabled: boolean;
  tags: string[];
  api_key_configured?: boolean;
}

/** Per-provider aggregate row from the metrics endpoint. */
export interface ProviderMetrics {
  provider_id: string;
  calls: number;
  ok: number;
  failures: number;
  avg_latency: number;
  max_latency: number;
  prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  cache_read_tokens: number;
  cost: number;
  switches: number;
}

/** Time-bucket row for dashboard charts. */
export interface SeriesPoint {
  provider_id: string;
  bucket: number;
  calls: number;
  ok: number;
  failures: number;
  avg_latency: number;
}

/** Gateway-wide totals. */
export interface Overview {
  calls: number;
  failures: number;
  success_rate: number;
  prompt_tokens: number;
  completion_tokens: number;
  cache_hit_rate: number;
  cost_usd: number;
  providers: number;
}

/** Metrics endpoint response. */
export interface MetricsResponse {
  range: string;
  overview: Overview;
  providers: ProviderMetrics[];
  series: SeriesPoint[];
  health: ProviderHealth[];
}

/** Score breakdown for one routing candidate. */
export interface ScoreBreakdown {
  provider_id: string;
  success: number;
  speed: number;
  cost: number;
  cache: number;
  total: number;
  priority: number;
}

/** Simulated routing decision. */
export interface SimulateResponse {
  model: string;
  prompt_length: number;
  ranking: ScoreBreakdown[];
  decisions: { provider_id: string; model: string; eligible: boolean; reasons: string[] }[];
}

/** Operational event entry. */
export interface EventEntry {
  at: number;
  kind: string;
  provider_id: string | null;
  detail: string;
}

/** Result of a proxy chat call. */
export interface ChatResult {
  content: string;
  provider: string;
  promptTokens: number;
  completionTokens: number;
  cachedTokens: number;
}

/** Tier that controls scheduler weights and priority handling. */
export type ApiKeyTier = "premium" | "standard" | "economy";

/** One generated caller API key, without its secret. */
export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  tier: ApiKeyTier;
  allowed_providers: string[];
  enabled: boolean;
  created_at: number;
  last_used_at: number | null;
  revoked_at: number | null;
}

/** Response returned only when a key is first generated. */
export interface CreatedApiKey extends Omit<
  ApiKey,
  "enabled" | "created_at" | "last_used_at" | "revoked_at"
> {
  token: string;
}

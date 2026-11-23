/**
 * Typed fetch client that attaches the admin bearer token.
 */

import type {
  ChatResult,
  EventEntry,
  MetricsResponse,
  ProviderConfig,
  ProviderHealth,
  SimulateResponse,
} from "./types";

const TOKEN_KEY = "polygate.adminToken";

/** Load the stored admin token. */
export function getToken(): string {
  try {
    return window.localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Persist the admin token for later admin calls. */
export function setToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage may be unavailable in private mode */
  }
}

/** Clear the stored admin token. */
export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage may be unavailable in private mode */
  }
}

/** Error carrying the HTTP status of a failed request. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function authHeaders(): HeadersInit {
  const token = getToken();
  return token ? { authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...authHeaders(), ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { error?: { message?: string }; detail?: string };
      detail = body.error?.message ?? body.detail ?? detail;
    } catch {
      /* non JSON error body */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

/** Fetch provider configs and health. */
export function fetchProviders(): Promise<{ providers: ProviderConfig[]; health: ProviderHealth[] }> {
  return request("/admin/providers");
}

/** Replace the provider pool. */
export function saveProviders(providers: ProviderConfig[]): Promise<{ providers: ProviderConfig[] }> {
  return request("/admin/providers", { method: "PUT", body: JSON.stringify({ providers }) });
}

/** Fetch aggregated metrics for a range. */
export function fetchMetrics(range: string): Promise<MetricsResponse> {
  return request(`/admin/metrics?range=${encodeURIComponent(range)}`);
}

/** Fetch recent operational events. */
export function fetchEvents(limit = 50): Promise<{ events: EventEntry[] }> {
  return request(`/admin/events?limit=${limit}`);
}

/** Simulate routing decisions for a prompt. */
export function simulate(model: string, prompt: string): Promise<SimulateResponse> {
  return request("/admin/simulate", { method: "POST", body: JSON.stringify({ model, prompt }) });
}

/** Run one chat completion through the router. */
export async function chat(model: string, prompt: string, stream: boolean): Promise<ChatResult> {
  const response = await postChat(model, prompt, stream);
  if (stream) {
    return readStream(response);
  }
  return parseChatBody(response);
}

async function postChat(model: string, prompt: string, stream: boolean): Promise<Response> {
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: { "content-type": "application/json", ...authHeaders() },
    body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }], stream }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text.slice(0, 400), response.status);
  }
  return response;
}

interface ChatBody {
  model: string;
  choices: { message: { content?: string } }[];
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    prompt_tokens_details?: { cached_tokens?: number };
  };
}

async function parseChatBody(response: Response): Promise<ChatResult> {
  const body = (await response.json()) as ChatBody;
  return {
    content: body.choices[0]?.message.content ?? "",
    provider: body.model,
    promptTokens: body.usage?.prompt_tokens ?? 0,
    completionTokens: body.usage?.completion_tokens ?? 0,
    cachedTokens: body.usage?.prompt_tokens_details?.cached_tokens ?? 0,
  };
}

/** Accumulated stream state while decoding SSE frames. */
interface StreamAccumulator {
  content: string;
  provider: string;
  promptTokens: number;
  completionTokens: number;
  cachedTokens: number;
}

interface StreamChunk {
  model?: string;
  choices?: { delta?: { content?: string } }[];
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    prompt_tokens_details?: { cached_tokens?: number };
  };
}

function parseFrame(body: string): StreamChunk | undefined {
  try {
    return JSON.parse(body) as StreamChunk;
  } catch {
    return undefined;
  }
}

function absorbChunk(state: StreamAccumulator, chunk: StreamChunk): void {
  state.content += chunk.choices?.[0]?.delta?.content ?? "";
  state.provider = chunk.model ?? state.provider;
  if (chunk.usage) mergeUsage(state, chunk.usage);
}

function mergeUsage(state: StreamAccumulator, usage: NonNullable<StreamChunk["usage"]>): void {
  state.promptTokens = usage.prompt_tokens ?? state.promptTokens;
  state.completionTokens = usage.completion_tokens ?? state.completionTokens;
  state.cachedTokens = usage.prompt_tokens_details?.cached_tokens ?? state.cachedTokens;
}

async function readStream(response: Response): Promise<ChatResult> {
  const state: StreamAccumulator = {
    content: "",
    provider: "",
    promptTokens: 0,
    completionTokens: 0,
    cachedTokens: 0,
  };
  for (const line of (await response.text()).split("\n")) {
    const body = line.startsWith("data:") ? line.slice(5).trim() : "";
    if (!body || body === "[DONE]") continue;
    const chunk = parseFrame(body);
    if (chunk) absorbChunk(state, chunk);
  }
  return state;
}

/** Verify the admin token by calling a protected endpoint. */
export async function verifyToken(token: string): Promise<boolean> {
  const response = await fetch("/admin/providers", { headers: { authorization: `Bearer ${token}` } });
  return response.ok;
}

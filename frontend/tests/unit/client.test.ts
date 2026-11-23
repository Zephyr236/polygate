/**
 * Unit tests for the API client, token storage and stream parsing.
 */

import { describe, expect, it, vi } from "vitest";

import {
  ApiError,
  chat,
  clearToken,
  fetchEvents,
  fetchMetrics,
  fetchProviders,
  getToken,
  saveProviders,
  setToken,
  simulate,
  verifyToken,
} from "@/api/client";
import { providerFixtures } from "../msw";

describe("token storage", () => {
  it("persists and clears the token", () => {
    setToken("abc");
    expect(getToken()).toBe("abc");
    clearToken();
    expect(getToken()).toBe("");
  });

  it("survives storage failures", () => {
    const original = window.localStorage.setItem;
    window.localStorage.setItem = vi.fn(() => {
      throw new Error("denied");
    });
    expect(() => setToken("x")).not.toThrow();
    window.localStorage.setItem = original;
  });

  it("returns empty when storage read throws", () => {
    const original = window.localStorage.getItem;
    window.localStorage.getItem = vi.fn(() => {
      throw new Error("denied");
    });
    expect(getToken()).toBe("");
    window.localStorage.getItem = original;
  });
});

describe("admin requests", () => {
  it("sends the bearer token on admin calls", async () => {
    setToken("tok");
    const seen: string[] = [];
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    server.events.on("request:start", ({ request }) => seen.push(request.headers.get("authorization") ?? ""));
    await fetchProviders();
    server.close();
    expect(seen[0]).toBe("Bearer tok");
  });

  it("maps error bodies onto ApiError", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    const { http, HttpResponse } = await import("msw");
    server.use(
      http.get("/admin/providers", () =>
        HttpResponse.json({ detail: "invalid admin token" }, { status: 401 }),
      ),
    );
    await expect(fetchProviders()).rejects.toBeInstanceOf(ApiError);
    try {
      await fetchProviders();
    } catch (error) {
      expect((error as ApiError).status).toBe(401);
      expect((error as ApiError).message).toBe("invalid admin token");
    }
    server.use(http.get("/admin/providers", () => HttpResponse.text("boom", { status: 500 })));
    try {
      await fetchProviders();
    } catch (error) {
      expect((error as ApiError).message).toBe("Internal Server Error");
    }
    server.close();
  });

  it("loads metrics for the requested range", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    const data = await fetchMetrics("7d");
    expect(data.range).toBe("7d");
    server.close();
  });

  it("loads events and saves providers", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    expect((await fetchEvents()).events).toEqual([]);
    const saved = await saveProviders(providerFixtures);
    expect(saved.providers).toHaveLength(2);
    server.close();
  });

  it("verifies an admin token", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    expect(await verifyToken("tok")).toBe(true);
    server.close();
  });
});

describe("simulate", () => {
  it("posts the model and prompt", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    const data = await simulate("deepseek-v4.1-flash", "hi");
    expect(data.decisions[0]?.eligible).toBe(true);
    server.close();
  });
});

describe("chat", () => {
  it("parses a non-streaming completion", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    const result = await chat("m", "hi", false);
    expect(result.content).toBe("PONG");
    expect(result.cachedTokens).toBe(1);
    expect(result.completionTokens).toBe(2);
    server.close();
  });

  it("concatenates streamed deltas and usage", async () => {
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    const result = await chat("m", "hi", true);
    expect(result.content).toBe("PONG");
    expect(result.provider).toBe("amr");
    expect(result.promptTokens).toBe(5);
    expect(result.completionTokens).toBe(2);
    server.close();
  });

  it("raises ApiError on upstream failure", async () => {
    const { http, HttpResponse } = await import("msw");
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    server.use(
      http.post("/v1/chat/completions", () => HttpResponse.text("providers_unavailable", { status: 502 })),
    );
    await expect(chat("m", "hi", false)).rejects.toBeInstanceOf(ApiError);
    server.close();
  });

  it("ignores malformed stream frames", async () => {
    const { http, HttpResponse } = await import("msw");
    const server = (await import("../msw")).createServer();
    server.listen({ onUnhandledRequest: "error" });
    const body = 'data: not-json\ndata: {"choices":[{"delta":{"content":"X"}}]}\n\ndata: [DONE]\n';
    server.use(http.post("/v1/chat/completions", () => new HttpResponse(body)));
    const result = await chat("m", "hi", true);
    expect(result.content).toBe("X");
    server.close();
  });
});

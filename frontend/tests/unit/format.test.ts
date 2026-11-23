/**
 * Unit tests for formatting helpers.
 */

import { describe, expect, it } from "vitest";

import { clockTime, latency, percent, tokens, usd } from "@/utils/format";

describe("percent", () => {
  it("formats ratios with default precision", () => {
    expect(percent(0.1234)).toBe("12.3%");
    expect(percent(1)).toBe("100.0%");
    expect(percent(0)).toBe("0.0%");
  });

  it("honours the requested digits", () => {
    expect(percent(0.987, 0)).toBe("99%");
    expect(percent(0.98765, 3)).toBe("98.765%");
  });
});

describe("latency", () => {
  it("renders sub-second values in milliseconds", () => {
    expect(latency(0)).toBe("—");
    expect(latency(420.6)).toBe("421ms");
    expect(latency(999)).toBe("999ms");
  });

  it("renders seconds for long latencies", () => {
    expect(latency(1000)).toBe("1.00s");
    expect(latency(2350)).toBe("2.35s");
  });
});

describe("tokens", () => {
  it("formats thousands and rounds", () => {
    expect(tokens(1234.7)).toBe("1,235");
    expect(tokens(0)).toBe("0");
    expect(tokens(1_000_000)).toBe("1,000,000");
  });
});

describe("usd", () => {
  it("handles zero, small and regular amounts", () => {
    expect(usd(0)).toBe("$0");
    expect(usd(0.000123)).toBe("$0.000123");
    expect(usd(0.0123)).toBe("$0.0123");
  });
});

describe("clockTime", () => {
  it("formats epoch seconds as a time string", () => {
    const formatted = clockTime(1_800_000_000);
    expect(formatted).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });
});

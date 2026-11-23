/**
 * Unit tests for dashboard metric derivations.
 */

import { describe, expect, it } from "vitest";

import type { ProviderMetrics, SeriesPoint } from "@/api/types";
import { aggregate, bucketTotals, costPerThousand, p95Estimate, providerColor } from "@/utils/metrics";
import { metricsFixture } from "../msw";

const rows: ProviderMetrics[] = metricsFixture.providers;

describe("aggregate", () => {
  it("sums every numeric column", () => {
    const totals = aggregate(rows);
    expect(totals.calls).toBe(32);
    expect(totals.failures).toBe(5);
    expect(totals.promptTokens).toBe(1200);
    expect(totals.completionTokens).toBe(400);
    expect(totals.cacheRead).toBe(280);
    expect(totals.cost).toBeCloseTo(0.004);
  });

  it("returns zero totals for no rows", () => {
    expect(aggregate([])).toEqual({
      calls: 0,
      failures: 0,
      promptTokens: 0,
      completionTokens: 0,
      cacheRead: 0,
      cost: 0,
    });
  });
});

describe("p95Estimate", () => {
  it("returns zero when a provider has no calls", () => {
    expect(p95Estimate({ ...rows[0]!, calls: 0 })).toBe(0);
  });

  it("blends the max latency into the estimate", () => {
    expect(p95Estimate(rows[0]!)).toBeCloseTo(2100);
    expect(p95Estimate({ ...rows[0]!, avg_latency: 5000, max_latency: 1000 })).toBe(5000);
  });
});

describe("costPerThousand", () => {
  it("returns zero when there are no prompt tokens", () => {
    expect(costPerThousand({ ...rows[0]!, prompt_tokens: 0 })).toBe(0);
  });

  it("scales cost by prompt tokens", () => {
    expect(costPerThousand(rows[0]!)).toBeCloseTo(0.00375, 5);
  });
});

describe("bucketTotals", () => {
  it("merges provider points per bucket", () => {
    const totals = bucketTotals(metricsFixture.series);
    expect(totals).toEqual([
      { bucket: 1_800_000_000, calls: 16, failures: 3 },
      { bucket: 1_800_000_300, calls: 10, failures: 0 },
    ]);
  });

  it("handles an empty series", () => {
    expect(bucketTotals([])).toEqual([]);
  });

  it("keeps buckets ordered by time", () => {
    const series: SeriesPoint[] = [
      { provider_id: "a", bucket: 3, calls: 1, ok: 1, failures: 0, avg_latency: 1 },
      { provider_id: "a", bucket: 1, calls: 1, ok: 0, failures: 1, avg_latency: 1 },
    ];
    expect(bucketTotals(series)[0]!.bucket).toBe(1);
  });
});

describe("providerColor", () => {
  it("cycles through the palette", () => {
    expect(providerColor(0)).toBe("#2563eb");
    expect(providerColor(5)).toBe("#0891b2");
    expect(providerColor(6)).toBe("#2563eb");
  });
});

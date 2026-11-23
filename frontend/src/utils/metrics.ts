/**
 * Metric derivation helpers shared by dashboard widgets.
 */

import type { ProviderMetrics, SeriesPoint } from "../api/types";

/** Totals derived from per-provider rows. */
export interface Totals {
  calls: number;
  failures: number;
  promptTokens: number;
  completionTokens: number;
  cacheRead: number;
  cost: number;
}

/** Aggregate provider rows into gateway-wide totals. */
export function aggregate(rows: ProviderMetrics[]): Totals {
  return rows.reduce<Totals>(
    (acc, row) => ({
      calls: acc.calls + row.calls,
      failures: acc.failures + row.failures,
      promptTokens: acc.promptTokens + row.prompt_tokens,
      completionTokens: acc.completionTokens + row.completion_tokens,
      cacheRead: acc.cacheRead + row.cache_read_tokens,
      cost: acc.cost + row.cost,
    }),
    { calls: 0, failures: 0, promptTokens: 0, completionTokens: 0, cacheRead: 0, cost: 0 },
  );
}

/** Percentile latency estimate from a provider row. */
export function p95Estimate(row: ProviderMetrics): number {
  if (row.calls === 0) return 0;
  return Math.max(row.avg_latency, row.max_latency * 0.6);
}

/** Cost per thousand prompt tokens for a provider row. */
export function costPerThousand(row: ProviderMetrics): number {
  if (row.prompt_tokens === 0) return 0;
  return (row.cost / row.prompt_tokens) * 1000;
}

/** One merged time bucket. */
interface BucketTotal {
  bucket: number;
  calls: number;
  failures: number;
}

/** Merge series rows into per-bucket totals for a chart. */
export function bucketTotals(series: SeriesPoint[]): BucketTotal[] {
  const byBucket = new Map<number, BucketTotal>();
  for (const point of series) {
    const entry = byBucket.get(point.bucket) ?? { bucket: point.bucket, calls: 0, failures: 0 };
    entry.calls += point.calls;
    entry.failures += point.failures;
    byBucket.set(point.bucket, entry);
  }
  return [...byBucket.values()].sort((a, b) => a.bucket - b.bucket);
}

/** Pick a stable color per provider. */
export function providerColor(index: number): string {
  const palette = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"];
  return palette[index % palette.length] ?? "#2563eb";
}

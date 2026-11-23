/**
 * Dashboard page: KPI row, per-provider cards and time-series charts.
 */

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { MetricsResponse, ProviderHealth, ProviderMetrics } from "../api/types";
import { CapacityBar, HealthBadge, KpiCard, Panel, SuccessRing } from "../components/widgets";
import { clockTime, latency, percent, tokens, usd } from "../utils/format";
import type { Totals } from "../utils/metrics";
import { aggregate, bucketTotals, costPerThousand, p95Estimate, providerColor } from "../utils/metrics";

/** Time-range selector options. */
const RANGES = ["15m", "1h", "24h", "7d"] as const;

/** Range switch buttons. */
function RangePicker({ range, onRangeChange }: { range: string; onRangeChange: (range: string) => void }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      {RANGES.map((item) => (
        <button
          key={item}
          className="action"
          style={{ background: item === range ? "var(--accent)" : "var(--panel-alt)" }}
          onClick={() => onRangeChange(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}

/** KPI tiles for the selected range. */
function KpiRow({
  totals,
  success,
  cacheRate,
  providers,
}: {
  totals: Totals;
  success: number;
  cacheRate: number;
  providers: number;
}) {
  return (
    <div className="kpis">
      <KpiCard label="Calls" value={tokens(totals.calls)} hint={`${providers} providers`} />
      <KpiCard label="Success" value={percent(success)} hint={`${totals.failures} failures`} />
      <KpiCard label="Prompt tokens" value={tokens(totals.promptTokens)} />
      <KpiCard label="Completion tokens" value={tokens(totals.completionTokens)} />
      <KpiCard label="Cache hits" value={percent(cacheRate)} />
      <KpiCard label="Est. cost" value={usd(totals.cost)} />
    </div>
  );
}

/** Guarded ratio helper that yields zero for empty denominators. */
function ratio(numerator: number, denominator: number): number {
  return denominator > 0 ? numerator / denominator : 0;
}

/** Traffic chart of calls and failures per bucket. */
function TrafficChart({ buckets }: { buckets: ReturnType<typeof bucketTotals> }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={buckets}>
        <XAxis dataKey="bucket" tickFormatter={(value) => clockTime(Number(value))} fontSize={11} />
        <YAxis fontSize={11} allowDecimals={false} />
        <Tooltip labelFormatter={(value) => clockTime(Number(value))} />
        <Line type="monotone" dataKey="calls" stroke="var(--accent)" dot={false} />
        <Line type="monotone" dataKey="failures" stroke="var(--bad)" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Per-provider numeric detail table. */
function DetailTable({ rows }: { rows: ProviderMetrics[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Provider</th>
          <th>Calls</th>
          <th>Failures</th>
          <th>Switches</th>
          <th>Prompt</th>
          <th>Completion</th>
          <th>Reasoning</th>
          <th>Cached</th>
          <th>Cost</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.provider_id}>
            <td>{row.provider_id}</td>
            <td>{tokens(row.calls)}</td>
            <td>{tokens(row.failures)}</td>
            <td>{tokens(row.switches)}</td>
            <td>{tokens(row.prompt_tokens)}</td>
            <td>{tokens(row.completion_tokens)}</td>
            <td>{tokens(row.reasoning_tokens)}</td>
            <td>{tokens(row.cache_read_tokens)}</td>
            <td>{usd(row.cost)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Provider cards grid. */
function ProviderGrid({
  rows,
  healthById,
}: {
  rows: ProviderMetrics[];
  healthById: Map<string, ProviderHealth>;
}) {
  return (
    <div className="providers-grid">
      {rows.map((row, index) => (
        <ProviderCard
          key={row.provider_id}
          row={row}
          index={index}
          health={healthById.get(row.provider_id)}
        />
      ))}
    </div>
  );
}

/** One provider metric card. */
function ProviderCard({
  row,
  index,
  health,
}: {
  row: ProviderMetrics;
  index: number;
  health: ProviderHealth | undefined;
}) {
  return (
    <div className="card" data-testid={`provider-${row.provider_id}`}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ color: providerColor(index) }}>{row.provider_id}</h3>
        {health ? <HealthBadge state={health.state} /> : null}
      </div>
      <div style={{ display: "flex", gap: 16, alignItems: "center", margin: "8px 0" }}>
        <SuccessRing rate={ratio(row.calls - row.failures, row.calls)} />
        <div style={{ flex: 1, fontSize: 13, lineHeight: 1.7 }}>
          <div>
            p50 {latency(row.avg_latency)} · p95 {latency(p95Estimate(row))}
          </div>
          <div>cost/1k prompt {usd(costPerThousand(row))}</div>
          <div>cache {percent(ratio(row.cache_read_tokens, row.prompt_tokens))}</div>
        </div>
      </div>
      {health ? <CapacityBar inflight={health.inflight} capacity={health.capacity} /> : null}
    </div>
  );
}

/** Render the metrics dashboard for a selected range. */
export function Dashboard({
  data,
  range,
  onRangeChange,
}: {
  data: MetricsResponse | undefined;
  range: string;
  onRangeChange: (range: string) => void;
}) {
  const rows = data?.providers ?? [];
  const totals = aggregate(rows);
  const success = ratio(totals.calls - totals.failures, totals.calls);
  const cacheRate = ratio(totals.cacheRead, totals.promptTokens);
  const buckets = bucketTotals(data?.series ?? []);
  const healthById = new Map((data?.health ?? []).map((item) => [item.id, item]));

  return (
    <div className="main">
      <RangePicker range={range} onRangeChange={onRangeChange} />
      <KpiRow
        totals={totals}
        success={success}
        cacheRate={cacheRate}
        providers={data?.overview.providers ?? 0}
      />
      <Panel title="Traffic (calls per bucket)">
        <TrafficChart buckets={buckets} />
      </Panel>
      <ProviderGrid rows={rows} healthById={healthById} />
      <Panel title="Per-provider detail">
        <DetailTable rows={rows} />
      </Panel>
    </div>
  );
}

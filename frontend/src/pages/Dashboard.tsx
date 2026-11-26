/**
 * Dashboard page: KPI row, per-provider cards and time-series charts.
 */

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
      <KpiCard label="Calls" value={tokens(totals.calls)} hint={`${providers} providers`} icon="pulse" />
      <KpiCard label="Success" value={percent(success)} hint={`${totals.failures} failures`} icon="check" />
      <KpiCard label="Prompt tokens" value={tokens(totals.promptTokens)} icon="server" />
      <KpiCard label="Completion tokens" value={tokens(totals.completionTokens)} icon="server" />
      <KpiCard label="Cache hits" value={percent(cacheRate)} icon="refresh" />
      <KpiCard label="Est. cost" value={usd(totals.cost)} icon="route" />
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
      <LineChart data={buckets} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--border-soft)" vertical={false} />
        <XAxis
          dataKey="bucket"
          tickFormatter={(value) => clockTime(Number(value))}
          fontSize={11}
          stroke="var(--muted)"
        />
        <YAxis fontSize={11} allowDecimals={false} stroke="var(--muted)" />
        <Tooltip
          labelFormatter={(value) => clockTime(Number(value))}
          contentStyle={{
            background: "var(--panel-alt)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            color: "var(--text)",
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12, color: "var(--muted)" }} />
        <Line
          type="monotone"
          dataKey="calls"
          name="calls"
          stroke="var(--accent)"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="failures"
          name="failures"
          stroke="var(--bad)"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Per-provider numeric detail table. */
function DetailTable({ rows }: { rows: ProviderMetrics[] }) {
  return (
    <div className="table-wrap">
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
    </div>
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

/** Loading placeholder for the dashboard. */
function DashboardLoading() {
  return (
    <div className="main">
      <div className="skeleton" style={{ height: 46, width: 260 }} />
      <div className="kpis">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="skeleton" key={index} style={{ height: 112 }} />
        ))}
      </div>
      <Panel title="Traffic (calls per bucket)">
        <div className="skeleton" style={{ height: 220 }} />
      </Panel>
    </div>
  );
}

/** Traffic panel with an explicit empty state. */
function TrafficPanel({ buckets }: { buckets: ReturnType<typeof bucketTotals> }) {
  return (
    <Panel title="Traffic (calls per bucket)">
      {buckets.length > 0 ? (
        <TrafficChart buckets={buckets} />
      ) : (
        <div className="empty-state" style={{ minHeight: 180 }}>
          <strong>No traffic yet</strong>
          <span>Send a request through the Playground or your application to populate this chart.</span>
        </div>
      )}
    </Panel>
  );
}

/** Provider cards or an empty state. */
function ProviderSection({
  rows,
  healthById,
}: {
  rows: ProviderMetrics[];
  healthById: Map<string, ProviderHealth>;
}) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <strong>No provider metrics in this range</strong>
        <span>Choose a wider range or send a request through a configured provider.</span>
      </div>
    );
  }
  return <ProviderGrid rows={rows} healthById={healthById} />;
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
  if (!data) return <DashboardLoading />;
  return <DashboardContent data={data} range={range} onRangeChange={onRangeChange} />;
}

/** Dashboard content once metrics are available. */
function DashboardContent({
  data,
  range,
  onRangeChange,
}: {
  data: MetricsResponse;
  range: string;
  onRangeChange: (range: string) => void;
}) {
  const rows = data.providers ?? [];
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
      <TrafficPanel buckets={buckets} />
      <ProviderSection rows={rows} healthById={healthById} />
      {rows.length > 0 ? (
        <Panel title="Per-provider detail">
          <DetailTable rows={rows} />
        </Panel>
      ) : null}
    </div>
  );
}

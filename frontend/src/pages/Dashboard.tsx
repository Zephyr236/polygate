/**
 * Dashboard page: KPI row, per-provider cards and time-series charts.
 */

import type { MetricsResponse, ProviderHealth, ProviderMetrics } from "../api/types";
import { useI18n, type MessageKey } from "../i18n";
import { DetailTable, TrafficChart } from "./dashboardCharts";
import { CapacityBar, HealthBadge, KpiCard, Panel, SuccessRing } from "../components/widgets";
import { latency, percent, tokens, usd } from "../utils/format";
import type { Totals } from "../utils/metrics";
import { aggregate, bucketTotals, costPerThousand, p95Estimate, providerColor } from "../utils/metrics";

/** Time-range selector options. */
const RANGES: { value: string; key: MessageKey }[] = [
  { value: "15m", key: "dashboard.range.15m" },
  { value: "1h", key: "dashboard.range.1h" },
  { value: "24h", key: "dashboard.range.24h" },
  { value: "7d", key: "dashboard.range.7d" },
];

/** Range switch buttons. */
function RangePicker({ range, onRangeChange }: { range: string; onRangeChange: (range: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="range-picker">
      {RANGES.map((item) => (
        <button
          key={item.value}
          className={item.value === range ? "active" : ""}
          onClick={() => onRangeChange(item.value)}
        >
          {t(item.key)}
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
  const { t } = useI18n();
  return (
    <div className="kpis">
      <KpiCard
        label={t("dashboard.calls")}
        value={tokens(totals.calls)}
        hint={t("dashboard.providers", { count: providers })}
        icon="pulse"
      />
      <KpiCard
        label={t("dashboard.success")}
        value={percent(success)}
        hint={t("dashboard.failures", { count: totals.failures })}
        icon="check"
      />
      <KpiCard label={t("dashboard.promptTokens")} value={tokens(totals.promptTokens)} icon="server" />
      <KpiCard
        label={t("dashboard.completionTokens")}
        value={tokens(totals.completionTokens)}
        icon="server"
      />
      <KpiCard label={t("dashboard.cacheHits")} value={percent(cacheRate)} icon="refresh" />
      <KpiCard label={t("dashboard.cost")} value={usd(totals.cost)} icon="route" />
    </div>
  );
}

/** Guarded ratio helper that yields zero for empty denominators. */
function ratio(numerator: number, denominator: number): number {
  return denominator > 0 ? numerator / denominator : 0;
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
  const { t } = useI18n();
  return (
    <Panel title={t("dashboard.trafficTitle")}>
      {buckets.length > 0 ? (
        <TrafficChart buckets={buckets} />
      ) : (
        <div className="empty-state" style={{ minHeight: 180 }}>
          <strong>{t("dashboard.noTrafficTitle")}</strong>
          <span>{t("dashboard.noTrafficBody")}</span>
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
  const { t } = useI18n();
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <strong>{t("dashboard.noMetricsTitle")}</strong>
        <span>{t("dashboard.noMetricsBody")}</span>
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
  const { t } = useI18n();
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
        <Panel title={t("dashboard.detailTitle")}>
          <DetailTable rows={rows} />
        </Panel>
      ) : null}
    </div>
  );
}

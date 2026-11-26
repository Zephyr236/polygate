/**
 * Dashboard chart and detail-table pieces.
 */

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { ProviderMetrics } from "../api/types";
import { useI18n } from "../i18n";
import { clockTime, tokens, usd } from "../utils/format";
import type { bucketTotals } from "../utils/metrics";

/** Traffic chart of calls and failures per bucket. */
export function TrafficChart({ buckets }: { buckets: ReturnType<typeof bucketTotals> }) {
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
export function DetailTable({ rows }: { rows: ProviderMetrics[] }) {
  const { t } = useI18n();
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{t("dashboard.table.provider")}</th>
            <th>{t("dashboard.table.calls")}</th>
            <th>{t("dashboard.table.failures")}</th>
            <th>{t("dashboard.table.switches")}</th>
            <th>{t("dashboard.table.prompt")}</th>
            <th>{t("dashboard.table.completion")}</th>
            <th>{t("dashboard.table.reasoning")}</th>
            <th>{t("dashboard.table.cached")}</th>
            <th>{t("dashboard.table.cost")}</th>
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

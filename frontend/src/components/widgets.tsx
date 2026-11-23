/**
 * Reusable dashboard widgets.
 */

import type { ReactNode } from "react";

import type { ProviderHealth } from "../api/types";
import { percent } from "../utils/format";

/** KPI tile showing a label and a formatted value. */
export function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <div className="kpi-value">{value}</div>
      {hint ? (
        <div className="mono" style={{ color: "var(--muted)", fontSize: 12 }}>
          {hint}
        </div>
      ) : null}
    </div>
  );
}

/** Health badge for a provider circuit state. */
export function HealthBadge({ state }: { state: ProviderHealth["state"] }) {
  return <span className={`badge ${state}`}>{state.replace("_", " ")}</span>;
}

/** Concurrency gauge showing used slots against capacity. */
export function CapacityBar({ inflight, capacity }: { inflight: number; capacity: number }) {
  const ratio = capacity > 0 ? Math.min(inflight / capacity, 1) : 0;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--muted)" }}>
        <span>inflight</span>
        <span>
          {inflight} / {capacity}
        </span>
      </div>
      <div style={{ height: 6, background: "var(--panel-alt)", borderRadius: 3, marginTop: 4 }}>
        <div
          data-testid="capacity-fill"
          style={{
            width: `${ratio * 100}%`,
            height: "100%",
            background: ratio > 0.85 ? "var(--bad)" : "var(--accent)",
            borderRadius: 3,
          }}
        />
      </div>
    </div>
  );
}

/** Success-rate ring rendered with CSS conic gradient. */
export function SuccessRing({ rate }: { rate: number }) {
  const degrees = Math.round(Math.max(0, Math.min(rate, 1)) * 360);
  return (
    <div
      aria-label={`success ${percent(rate)}`}
      style={{
        width: 56,
        height: 56,
        borderRadius: "50%",
        background: `conic-gradient(var(--ok) ${degrees}deg, var(--panel-alt) ${degrees}deg)`,
        display: "grid",
        placeItems: "center",
        fontSize: 12,
      }}
    >
      <span style={{ background: "var(--panel)", borderRadius: "50%", padding: "10px 6px" }}>
        {percent(rate, 0)}
      </span>
    </div>
  );
}

/** Section container with a heading. */
export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

/** Renders a list of short text reasons. */
export function ReasonList({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return <span style={{ color: "var(--ok)" }}>eligible</span>;
  return <span>{reasons.join(", ")}</span>;
}

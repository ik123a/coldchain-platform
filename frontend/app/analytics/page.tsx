"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AnimatedNumber } from "@/components/AnimatedNumber";

type Bucket = { name: string; value: number };

const SEVERITY_TONE: Record<string, string> = {
  CRITICAL: "var(--critical)",
  HIGH: "var(--warning)",
  MEDIUM: "var(--ai)",
  LOW: "var(--nominal)",
};

const pct = (n: number, total: number) => (total > 0 ? (n / total) * 100 : 0);

export default function Analytics() {
  const [a, setA] = useState<any>(null);
  const [d, setD] = useState<any>(null);

  useEffect(() => {
    api("/api/analytics").then(setA).catch(() => {});
    api("/api/dashboard").then(setD).catch(() => {});
  }, []);

  const causes: Bucket[] = a
    ? Object.entries(a.top_failure_causes || {}).map(([name, value]) => ({
        name: name.replace(/_/g, " "),
        value: Number(value),
      }))
    : [];
  const sev: Bucket[] = a
    ? Object.entries(a.severity_breakdown || {}).map(([name, value]) => ({ name, value: Number(value) }))
    : [];

  const totalIncidents = a?.total_incidents ?? 0;
  const openIncidents = a?.open_incidents ?? 0;
  const resolvedIncidents = Math.max(0, totalIncidents - openIncidents);
  const causeMax = causes.reduce((m, c) => Math.max(m, c.value), 0);

  const kpis = [
    { l: "Total incidents", v: a?.total_incidents, suffix: "" },
    { l: "Critical", v: a?.critical_incidents, suffix: "" },
    { l: "Open", v: a?.open_incidents, suffix: "" },
    { l: "Avg recovery", v: a?.avg_recovery_ticks, suffix: " ticks" },
    { l: "Readings ingested", v: a?.readings_ingested, suffix: "" },
    { l: "Avg response score", v: a?.avg_response_score, suffix: " / 100" },
  ];

  return (
    <div className="fade-in space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {kpis.map((k) => (
          <div key={k.l} className="base-card p-3.5">
            <div className="t-micro uppercase text-[var(--text-muted)]">{k.l}</div>
            <div className="kpi-num mt-1 t-metric-lg font-bold text-[var(--text)]">
              {typeof k.v === "number" ? (
                <AnimatedNumber value={k.v} suffix={k.suffix} />
              ) : (
                <span className="text-[var(--text-dim)]">—</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <section className="base-card p-4 lg:col-span-3">
          <header className="mb-3 flex items-baseline justify-between gap-3">
            <h3 className="t-body font-semibold">Failure causes</h3>
            <span className="t-micro text-[var(--text-muted)]">share of {totalIncidents} incidents</span>
          </header>

          {causes.length ? (
            <ul className="space-y-2.5">
              {causes.map((c) => (
                <li key={c.name}>
                  <div className="mb-1 flex items-baseline justify-between gap-3">
                    <span className="truncate t-body-sm capitalize text-[var(--text)]">{c.name}</span>
                    <span className="kpi-num shrink-0 t-body-sm text-[var(--text-secondary)]">
                      {c.value.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-elevated)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)]"
                      style={{ width: `${causeMax > 0 ? (c.value / causeMax) * 100 : 0}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-10 text-center t-body-sm text-[var(--text-muted)]">
              No incidents recorded yet — analytics populate from persisted incidents.
            </p>
          )}
        </section>

        <section className="base-card p-4 lg:col-span-2">
          <header className="mb-3 flex items-baseline justify-between gap-3">
            <h3 className="t-body font-semibold">Severity mix</h3>
            <span className="t-micro text-[var(--text-muted)]">{totalIncidents} total</span>
          </header>

          {sev.length ? (
            <>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-[var(--surface-elevated)]">
                {sev.map((s) => (
                  <div
                    key={s.name}
                    title={`${s.name}: ${s.value}`}
                    style={{
                      width: `${pct(s.value, totalIncidents)}%`,
                      background: SEVERITY_TONE[s.name] ?? "var(--text-muted)",
                    }}
                  />
                ))}
              </div>
              <ul className="mt-3 space-y-1.5">
                {sev.map((s) => (
                  <li key={s.name} className="flex items-center gap-2 t-body-sm">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ background: SEVERITY_TONE[s.name] ?? "var(--text-muted)" }}
                    />
                    <span className="flex-1 text-[var(--text-secondary)]">{s.name}</span>
                    <span className="kpi-num text-[var(--text)]">{s.value}</span>
                    <span className="kpi-num w-14 text-right text-[var(--text-muted)]">
                      {pct(s.value, totalIncidents).toFixed(0)}%
                    </span>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="py-10 text-center t-body-sm text-[var(--text-muted)]">
              Severity mix appears once incidents exist.
            </p>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="base-card p-4">
          <div className="t-micro uppercase text-[var(--text-muted)]">Incident resolution</div>
          <div className="mt-2 flex items-baseline gap-4">
            <div>
              <div className="kpi-num t-metric font-bold text-[var(--warning-soft)]">{openIncidents}</div>
              <div className="t-label text-[var(--text-muted)]">open</div>
            </div>
            <div>
              <div className="kpi-num t-metric font-bold text-[var(--nominal-soft)]">{resolvedIncidents}</div>
              <div className="t-label text-[var(--text-muted)]">resolved</div>
            </div>
          </div>
        </div>

        <div className="base-card p-4">
          <div className="t-micro uppercase text-[var(--text-muted)]">Mean peak temperature</div>
          <div className="kpi-num mt-2 t-metric font-bold text-[var(--warning-soft)]">
            {typeof a?.peak_temp_avg === "number" ? `${a.peak_temp_avg.toFixed(2)}°C` : "—"}
          </div>
          <div className="mt-1 t-label text-[var(--text-muted)]">across all recorded incidents</div>
        </div>

        <div className="base-card p-4">
          <div className="t-micro uppercase text-[var(--text-muted)]">Cargo at risk</div>
          <div className="kpi-num mt-2 t-metric font-bold text-[var(--critical-soft)]">
            {typeof d?.cargo_at_risk_value === "number" ? d.cargo_at_risk_value.toLocaleString() : "—"}
          </div>
          <div className="mt-1 t-label text-[var(--text-muted)]">
            {typeof d?.active_shipments === "number"
              ? `across ${d.active_shipments} active shipments`
              : "no active shipments"}
          </div>
        </div>
      </div>
    </div>
  );
}

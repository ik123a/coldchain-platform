"use client";
import Link from "next/link";
import { useMemo } from "react";
import { useStore } from "@/lib/store";

/**
 * Home hero — "ops" redesign.
 *
 * Signature device: the thermal spine. Its three gradient stops are derived
 * from the SAME risk counts the KPI row renders, so the bar can never
 * contradict a number. Precedence is stated explicitly below.
 */
export default function OpsHero({ onLaunch, loading }: { onLaunch: (autopilot: boolean) => void; loading: boolean }) {
  const { st } = useStore();

  const vehicles: any[] = (st as any)?.fleetVehicles || (st as any)?.vehicles || [];
  const incidents: any[] = (st as any)?.incidents || [];

  const risk = useMemo(() => {
    const atRisk = vehicles.filter((v) => v?.status === "AT_RISK").length;
    const critical = vehicles.filter((v) => v?.status === "CRITICAL").length;
    const open = incidents.filter((i) => i?.status !== "RESOLVED").length;
    const nominal = Math.max(0, vehicles.length - atRisk - critical);
    return { atRisk, critical, open, nominal, total: vehicles.length };
  }, [vehicles, incidents]);

  // Precedence: critical wins over at-risk wins over nominal.
  const spineStops =
    risk.critical > 0
      ? ["var(--thermal-6)", "var(--thermal-6)", "var(--thermal-4)"]
      : risk.atRisk > 0
      ? ["var(--thermal-4)", "var(--thermal-3)", "var(--thermal-2)"]
      : ["var(--thermal-2)", "var(--thermal-1)", "var(--thermal-0)"];

  const severity = risk.critical > 0 ? "CRITICAL" : risk.atRisk > 0 ? "AT RISK" : "NOMINAL";

  return (
    <section className="ops-sheen border-b border-[var(--border)] px-[var(--gutter)] py-[var(--section-y)]">
      <div className="mx-auto max-w-[1400px]">
        <p className="ops-eyebrow">
          <span className="ops-eyebrow__num">01</span>
          <span>Operate</span>
        </p>

        <div className="mt-8 grid gap-12 lg:grid-cols-[1.35fr_1fr] lg:items-end">
          <div className="ops-reveal">
            <h1 className="ops-display max-w-[15ch] text-[var(--text)]">
              Every degree between here and{" "}
              <span className="text-[var(--accent)]">safe.</span>
            </h1>

            <p className="mt-6 max-w-[52ch] text-[1.0625rem] leading-[1.6] text-[var(--text-secondary)]">
              A deterministic decision layer for refrigerated freight. Physics-based shelf-life
              forecasting, contested rescue dispatch, and recovery verification — every decision
              reproducible without an LLM.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-3">
              <button
                onClick={() => onLaunch(true)}
                disabled={loading}
                className="ops-card ops-card--interactive group inline-flex items-center gap-2.5 px-6 py-3.5 text-[var(--t-body)] font-semibold text-[var(--text)] disabled:opacity-50"
                style={{ "--i": 0 } as React.CSSProperties}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--nominal)] ops-pulse" aria-hidden />
                {loading ? "Launching…" : "Run rescue demo"}
                <span aria-hidden className="text-[var(--accent)]">→</span>
              </button>

              <Link
                href="/live-map"
                className="ops-card ops-card--interactive inline-flex items-center gap-2.5 px-6 py-3.5 text-[var(--t-body)] font-semibold text-[var(--text-secondary)]"
                style={{ "--i": 1 } as React.CSSProperties}
              >
                Open live map
                <span aria-hidden className="text-[var(--accent)]">→</span>
              </Link>
            </div>
          </div>

          {/* Fleet status card — the spine is derived from these exact counts */}
          <div className="ops-card p-6" style={{ "--i": 2 } as React.CSSProperties}>
            <div className="flex items-baseline justify-between">
              <p className="ops-label">Fleet state</p>
              <p
                className="ops-num text-[var(--t-micro)] font-semibold tracking-[0.16em]"
                style={{
                  color:
                    risk.critical > 0
                      ? "var(--critical)"
                      : risk.atRisk > 0
                      ? "var(--warning)"
                      : "var(--nominal)",
                }}
              >
                {severity}
              </p>
            </div>

            <div
              className="ops-spine mt-4"
              style={
                {
                  "--spine-a": spineStops[0],
                  "--spine-b": spineStops[1],
                  "--spine-c": spineStops[2],
                } as React.CSSProperties
              }
              role="img"
              aria-label={`Fleet status: ${risk.nominal} nominal, ${risk.atRisk} at risk, ${risk.critical} critical, of ${risk.total} vehicles.`}
            >
              <div className="ops-spine__fill" />
            </div>

            <dl className="mt-6 grid grid-cols-3 gap-4">
              <Stat label="Nominal" value={risk.nominal} tone="var(--nominal)" />
              <Stat label="At risk" value={risk.atRisk} tone="var(--warning)" />
              <Stat label="Critical" value={risk.critical} tone="var(--critical)" />
            </dl>

            <p className="ops-label mt-6 border-t border-[var(--border)] pt-4">
              {risk.open} open incident{risk.open === 1 ? "" : "s"} · {risk.total} vehicles
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <dt className="ops-label">{label}</dt>
      <dd
        className="ops-num mt-1.5 text-[2rem] font-semibold leading-none"
        style={{ color: tone }}
      >
        {value}
      </dd>
    </div>
  );
}

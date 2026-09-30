"use client";
import { useMemo } from "react";
import { ArrowRight, Play } from "lucide-react";
import { useStore } from "@/lib/store";

type Tone = "nominal" | "warning" | "critical";

/** Map a vehicle risk level to a tone. The fleet payload carries risk_level
 *  and cargo_health, not a cargo temperature, so the manifest never invents one. */
function riskTone(risk: string | null | undefined): Tone {
  const r = (risk || "").toUpperCase();
  if (r === "CRITICAL" || r === "SEVERE") return "critical";
  if (r === "HIGH" || r === "WARNING" || r === "ELEVATED") return "warning";
  return "nominal";
}

const ETA = (min: number | null | undefined) =>
  min == null ? "—" : min < 60 ? `${Math.round(min)}m` : `${(min / 60).toFixed(1)}h`;

/**
 * Home hero — the live operating picture.
 *
 * A dispatch coordinator's first question is "what is moving and what is
 * wrong", so the hero IS the manifest: real vehicles, real destinations and
 * real cargo temperatures read from the same store every page uses. Every
 * number is derived from that data, never hard-coded, so the hero cannot
 * contradict the rows beneath it.
 */
export default function OpsHero({
  onLaunch,
  loading,
}: {
  onLaunch: (autopilot: boolean) => void;
  loading: boolean;
}) {
  const { st } = useStore();

  const vehicles: any[] = useMemo(
    () => ((st as any)?.fleetVehicles as any[]) ?? [],
    [st]
  );

  const rows = useMemo(() => {
    const seen = new Set<string>();
    const out: any[] = [];
    for (const v of vehicles) {
      const id: string | undefined = v?.id ?? v?.vehicle_id ?? v?.unit_id;
      if (!id || seen.has(id)) continue; // the twin and shipment views can
      seen.add(id);                     // both report the same unit
      const cargo: any = v?.cargo ?? {};
      out.push({
        id,
        dest: v?.trip?.destination_id ?? v?.destination_id ?? "—",
        origin: v?.trip?.origin_id ?? "",
        eta: v?.trip?.eta_min ?? null,
        progress: v?.trip?.route_progress_percent ?? null,
        remaining: v?.trip?.distance_remaining_km ?? null,
        load: cargo.load_percent ?? null,
        health: cargo.cargo_health ?? null,
        ttc: cargo.time_to_critical_min ?? null,
        risk: v?.risk_level ?? cargo.risk_level ?? null,
      });
    }
    return out.sort((a, b) => (a.id > b.id ? 1 : -1));
  }, [vehicles]);

  const counts = useMemo(() => {
    let critical = 0;
    let warning = 0;
    for (const r of rows) {
      const t = riskTone(r.risk);
      if (t === "critical") critical++;
      else if (t === "warning") warning++;
    }
    return {
      critical,
      warning,
      nominal: Math.max(0, rows.length - critical - warning),
      attention: critical + warning,
    };
  }, [rows]);

  // One distribution bar. Stop order matches the precedence used for the
  // headline tone: critical first, then at-risk, then nominal.
  const dist = useMemo(() => {
    const n = Math.max(1, rows.length);
    return [
      { k: "critical", pct: (counts.critical / n) * 100, c: "var(--critical)" },
      { k: "warning", pct: (counts.warning / n) * 100, c: "var(--warning)" },
      { k: "nominal", pct: (counts.nominal / n) * 100, c: "var(--nominal)" },
    ];
  }, [counts, rows.length]);

  const attentionTone: Tone =
    counts.critical > 0 ? "critical" : counts.warning > 0 ? "warning" : "nominal";
  const attentionColor = `var(--${attentionTone})`;

  return (
    <section
      className="border-b border-[var(--border)] px-[var(--gutter)] pb-[var(--section-y)] pt-12"
      aria-label="Live fleet status"
    >
      <div className="mx-auto max-w-[1600px]">
        <p className="ops-eyebrow">
          <span className="ops-eyebrow__num">01</span>
          <span>Cold-chain operations</span>
        </p>

        <div className="mt-6 flex flex-wrap items-end justify-between gap-x-10 gap-y-6">
          <div className="min-w-0">
            <h1 className="ops-display text-[3.25rem] leading-[1.02]">
              {rows.length} refrigerated
              <br />
              units in transit.
            </h1>

            <div className="mt-6 flex items-center gap-4 border-t border-[var(--border)] pt-5">
              <span
                className="ops-num text-[2.75rem] font-semibold leading-none"
                style={{ color: attentionColor }}
              >
                {counts.attention}
              </span>
              <span className="max-w-[16ch] text-[var(--t-body)] leading-[1.4] text-[var(--text-secondary)]">
                need attention out of {rows.length} tracked
              </span>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            <button
              onClick={() => onLaunch(false)}
              disabled={loading}
              className="ops-card ops-card--interactive inline-flex items-center gap-2.5 px-5 py-2.5 text-[var(--t-body)] font-semibold text-[var(--text)] disabled:opacity-60"
            >
              <Play size={14} className="text-[var(--accent)]" aria-hidden />
              {loading ? "Launching…" : "Run rescue demo"}
            </button>
            <button
              onClick={() => onLaunch(true)}
              disabled={loading}
              className="ops-arrow-link"
              style={{ background: "none", border: 0, cursor: "pointer", padding: 0 }}
            >
              Run autonomous
              <ArrowRight size={13} aria-hidden />
            </button>
          </div>
        </div>

        {/* Manifest */}
        <div className="ops-card mt-12 overflow-hidden">
          <div className="ops-eyebrow flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-2.5">
            <span className="flex items-center gap-3">
              <span>Live manifest</span>
              <span className="ops-num text-[var(--text-secondary)]">
                {counts.nominal} nominal · {counts.warning} at risk · {counts.critical} critical
              </span>
            </span>
            <span className="hidden normal-case tracking-normal sm:inline">
              derived from the deterministic twin — no real fleet
            </span>
          </div>

          <div
            className="flex h-0.5 w-full"
            role="img"
            aria-label={`${rows.length} units: ${counts.nominal} nominal, ${counts.warning} at risk, ${counts.critical} critical`}
          >
            {dist.map((d) => (
              <span
                key={d.k}
                style={{ width: `${d.pct}%`, background: d.c }}
                className={d.pct > 0 ? "h-full" : "h-0"}
              />
            ))}
          </div>

          <ul className="divide-y divide-[var(--border)]">
            {rows.length === 0 && (
              <li className="px-4 py-6 text-[var(--t-body)] text-[var(--text-muted)]">
                Waiting for fleet telemetry…
              </li>
            )}
            {rows.slice(0, 9).map((r) => {
              const tone = riskTone(r.risk);
              const color = `var(--${tone})`;
              return (
                <li
                  key={r.id}
                  className="group grid grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)_auto] items-center gap-x-5 px-4 py-2.5 transition-colors hover:bg-[var(--surface-raised)] sm:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)_minmax(0,1fr)_auto_auto]"
                >
                  <span className="flex min-w-0 items-center gap-2.5">
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-full"
                      style={{ background: color }}
                      aria-hidden
                    />
                    <span className="ops-num truncate text-[var(--t-body)] text-[var(--text)]">
                      {r.id}
                    </span>
                  </span>

                  <span className="ops-num truncate text-[var(--t-body)] text-[var(--text-muted)]">
                    {r.dest}
                  </span>

                  <span className="hidden items-center gap-2.5 sm:flex">
                    <span
                      className="h-[3px] min-w-[2.5rem] flex-1 overflow-hidden rounded-full bg-[var(--surface-inset)]"
                      aria-hidden
                    >
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.min(100, Math.max(0, r.progress ?? 0))}%`,
                          background: "var(--border-strong)",
                        }}
                      />
                    </span>
                    <span className="ops-num w-[3.2rem] shrink-0 text-[var(--t-micro)] tabular-nums text-[var(--text-dim)]">
                      {r.progress == null ? "—" : `${Math.round(r.progress)}%`}
                    </span>
                  </span>

                  <span
                    className="ops-num text-[var(--t-body)] uppercase"
                    style={{ color: tone === "nominal" ? "var(--text-muted)" : color }}
                  >
                    {r.risk ?? "—"}
                  </span>

                  <span className="ops-num w-[4.5rem] text-right text-[var(--t-body)] tabular-nums text-[var(--text-secondary)]">
                    {ETA(r.eta)}
                  </span>
                </li>
              );
            })}
          </ul>

          {rows.length > 9 && (
            <p className="border-t border-[var(--border)] px-4 py-2.5 text-[var(--t-micro)] text-[var(--text-dim)]">
              + {rows.length - 9} more units tracked
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

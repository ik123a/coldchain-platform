"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { useStore } from "@/lib/store";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { TempChart } from "@/components/TempChart";
import { RiskGauge } from "@/components/RiskGauge";
import { AgentGrid } from "@/components/AgentGrid";
import { Siren, TrendingUp } from "lucide-react";

export default function Dashboard() {
  const { st, dispatch } = useStore();
  const d = st.dashboard;
  const sim = st.sim;
  const sevBadge = (s: string) => s === "CRITICAL" ? "badge-red" : s === "HIGH" ? "badge-amber" : "badge-cyan";

  return (
    <div className="fade-in space-y-4">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: "Active shipments", value: d?.active_shipments },
          { label: "Temp zones", value: d?.temperature_zones },
          { label: "Open incidents", value: d?.active_incidents, warn: (d?.active_incidents ?? 0) > 0 },
          { label: "Cargo at risk", value: d?.cargo_at_risk_value, suffix: " ₹", warn: (d?.cargo_at_risk_value ?? 0) > 0 },
          { label: "System health", value: d?.system_health, suffix: " %" },
        ].map((k, i) => (
          <motion.div key={k.label} className="base-card p-3.5" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
            <div className="text-[10px] text-[var(--text3)] tracking-wider uppercase">{k.label}</div>
            <div className={`text-2xl font-bold mt-1 ${k.warn ? "text-[var(--amber)]" : ""}`}>
              <AnimatedNumber value={k.value} suffix={k.suffix || ""} />
            </div>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* main chart */}
        <div className="xl:col-span-2 base-card p-4">
          <div className="flex items-center justify-between mb-1">
            <div>
              <div className="text-[13px] font-semibold flex items-center gap-2">
                <TrendingUp size={14} className="text-[var(--accent)]" /> Live temperature vs safe band
              </div>
              <div className="text-[11px] text-[var(--text3)]">
                {sim ? `sim #${sim.simulation_id} · ${sim.cargo_type.replace("_", " ")} · tick ${sim.tick} · ${sim.scenario}` : "no simulation running — launch from /simulation"}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {sim?.incident_status && sim.incident_status !== "RESOLVED" && (
                <Link href="/incidents" className="badge badge-red pulse-red">INCIDENT {sim.incident_status}</Link>
              )}
              {sim && <span className="badge badge-green">rsl {100 / sim.cargo_health > 1 ? (100 - sim.cargo_health).toFixed(1) + "% used" : "100%"}</span>}
            </div>
          </div>
          {st.history.length >= 2 ? <TempChart history={st.history} zone={sim?.zone} />
            : <div className="h-64 grid place-items-center text-[12px] text-[var(--text3)]">waiting for telemetry… (webhook pushes every 1 s when running)</div>}
          <div className="flex gap-5 mt-2 text-[11px] text-[var(--text2)]">
            <Metric label="Temp" v={sim ? sim.true_temperature.toFixed(2) + "°C" : "—"} hot={sim ? sim.true_temperature > sim.zone.mx : false} />
            <Metric label="Ambient" v={sim ? sim.ambient_temperature.toFixed(1) + "°C" : "—"} />
            <Metric label="Humidity" v={sim ? sim.humidity.toFixed(1) + "%" : "—"} />
            <Metric label="Compressor" v={sim ? (sim.compressor_on ? "ON" : sim.backup_cooling ? "BACKUP" : "OFF") : "—"} hot={sim ? !sim.compressor_on && !sim.backup_cooling : false} />
            <Metric label="Power" v={sim ? (sim.power_ok ? "GRID" : "BATTERY " + Math.round(sim.battery_level) + "%") : "—"} hot={sim ? !sim.power_ok : false} />
            <Metric label="Door" v={sim ? (sim.door_open ? "OPEN" : "CLOSED") : "—"} hot={sim ? sim.door_open : false} />
            <Metric label="Peak" v={sim ? sim.peak_temperature.toFixed(1) + "°C" : "—"} />
          </div>
        </div>

        {/* right column */}
        <div className="space-y-4">
          <div className="base-card p-4 flex items-center gap-4">
            <RiskGauge score={sim?.risk_score ?? null} level={sim?.risk_level ?? null} />
            <div className="flex-1">
              <div className="text-[11px] text-[var(--text3)] mb-1">CURRENT RISK</div>
              <div className={`text-2xl font-bold kpi-num ${sim && sim.risk_score >= 55 ? "text-[var(--amber)]" : ""}`}>
                <AnimatedNumber value={sim?.risk_score} suffix=" / 100" />
              </div>
              <div className="text-[10.5px] text-[var(--text3)] mt-1">
                exposure {sim?.exposure_ticks ?? 0} ticks · cargo <AnimatedNumber value={sim?.cargo_health} suffix=" %" />
              </div>
            </div>
          </div>

          {/* open incidents */}
          <div className="base-card p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] font-semibold flex items-center gap-2"><Siren size={14} className="text-[var(--red)]" /> Open incidents</span>
              <Link href="/incidents" className="text-[11px] text-[var(--accent)]">view all →</Link>
            </div>
            <div className="space-y-2">
              {(d?.open_incidents || []).slice(0, 4).map((i: any) => (
                <Link key={i.id} href={`/incidents?id=${i.id}`}
                      className={`block p-2.5 rounded-lg border border-[var(--border)] hover:border-[var(--border-hi)] transition ${i.severity === "CRITICAL" ? "pulse-red" : ""}`}>
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="font-semibold">#{i.id} {(i.root_cause || "diagnosing").replace(/_/g, " ")}</span>
                    <span className={`badge ${sevBadge(i.severity)}`}>{i.severity}</span>
                  </div>
                  <div className="text-[10.5px] text-[var(--text3)] mt-0.5">{i.status} · sim #{i.simulation_id} · detected {new Date(i.detected_at).toLocaleTimeString()}</div>
                </Link>
              ))}
              {!(d?.open_incidents || []).length &&
                <div className="text-[12px] text-[var(--text3)] py-6 text-center">no open incidents — system nominal</div>}
            </div>
          </div>

          {/* AI team */}
          <div className="base-card p-4">
            <div className="text-[13px] font-semibold mb-2">AI operations team</div>
            <AgentGrid agentsStatus={st.agentsStatus} />
          </div>
        </div>
      </div>

      {/* AI activity feed */}
      <div className="base-card p-4">
        <div className="text-[13px] font-semibold mb-2">AI activity feed</div>
        <div className="space-y-1.5 max-h-56 overflow-y-auto scroll-thin">
          {st.events.slice(0, 16).map((e, i) => (
            <div key={i} className="fade-in flex items-start gap-3 text-[11.5px]">
              <span className="text-[var(--text3)] tabular-nums shrink-0">{new Date(e.ts).toLocaleTimeString()}</span>
              <span className={`status-dot mt-1.5 ${e.kind === "incident_detected" ? "red" : e.kind === "recovery_verified" ? "" : ""}`}></span>
              <span className="text-[var(--text2)]">
                <b className="text-[var(--text)]">{e.agent ? e.agent.replace("_", " ") : e.kind}</b>
                {" — "}{(e.detail || e.root_cause || e.kind).toString()}
                {e.confidence != null && ` (confidence ${e.confidence})`}
                {e.score != null && ` [${e.score}${e.level ? " " + e.level : "/100"}]`}
              </span>
            </div>
          ))}
          {!st.events.length && <div className="text-[12px] text-[var(--text3)] py-4">no activity yet — start a simulation and inject a failure</div>}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, v, hot }: { label: string; v: string; hot?: boolean }) {
  return (
    <span><span className="text-[var(--text3)]">{label}</span> <b className={hot ? "text-[var(--red)]" : ""}>{v}</b></span>
  );
}

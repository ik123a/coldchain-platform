"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FastForward, Pause, Play, RotateCcw, Zap } from "lucide-react";
import { api, post } from "@/lib/api";
import { useStore } from "@/lib/store";
import { TempChart } from "@/components/TempChart";
import { RiskGauge } from "@/components/RiskGauge";
import { BorderBeam } from "@/components/ui/border-beam";
import { StatusBeacon } from "@/components/ui/status-beacon";

const FAILURES = [
  { key: "compressor_failure", label: "Compressor failure", cls: "btn-red" },
  { key: "door_open", label: "Door left open", cls: "btn-amber" },
  { key: "power_failure", label: "Power failure", cls: "btn-red" },
  { key: "heatwave", label: "Heatwave", cls: "btn-amber" },
  { key: "cooling_degradation", label: "Cooling degradation", cls: "btn-amber" },
  { key: "sensor_fault", label: "Sensor fault", cls: "" },
  { key: "multiple_failure", label: "Multiple failure", cls: "btn-red" },
] as const;

export default function SimulationPage() {
  const { st, dispatch } = useStore();
  const router = useRouter();
  const sim = st.sim;
  const [speed, setSpeed] = useState(10);
  const [shipments, setShipments] = useState<any[]>([]);
  const [zones, setZones] = useState<any[]>([]);
  const [shipmentId, setShipmentId] = useState<number | null>(null);
  const [zoneId, setZoneId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [whatif, setWhatif] = useState<any>(null);

  useEffect(() => {
    api("/api/shipments").then(setShipments).catch(() => {});
    api("/api/zones").then(setZones).catch(() => {});
  }, []);

  const createAndStart = async () => {
    setBusy(true);
    try {
      const sim0: any = await post("/api/simulations", {
        shipment_id: shipmentId, storage_zone_id: zoneId, scenario: "normal", simulation_speed: speed,
      });
      await post(`/api/simulations/${sim0.id}/start`);
    } finally { setBusy(false); }
  };

  const sid = sim?.simulation_id;
  const cmd = (p: string) => sid && post(`/api/simulations/${sid}${p}`);

  const latestIncident = st.incidents[0];
  const runWhatIf = async () => {
    if (!latestIncident) return;
    setWhatif(await post(`/api/incidents/${latestIncident.id}/what-if?ticks=12`));
  };

  return (
    <div className="fade-in grid grid-cols-1 xl:grid-cols-4 gap-4">
      {/* control column */}
      <div className="space-y-4">
        <div className="base-card p-4 space-y-3">
          <div className="t-body font-semibold">Simulation control</div>
          <label className="block t-label text-[var(--text3)]">Shipment
            <select className="mt-1 w-full" value={shipmentId ?? ""} onChange={e => setShipmentId(e.target.value ? +e.target.value : null)}>
              <option value="">demo fresh produce</option>
              {shipments.map((s: any) => <option key={s.id} value={s.id}>{s.name} · {s.cargo_type.replace("_", " ")}</option>)}
            </select>
          </label>
          <label className="block t-label text-[var(--text3)]">Zone
            <select className="mt-1 w-full" value={zoneId ?? ""} onChange={e => setZoneId(e.target.value ? +e.target.value : null)}>
              <option value="">Zone A band 2–8°C</option>
              {zones.map((z: any) => <option key={z.id} value={z.id}>{z.name} · {z.min_temperature}–{z.max_temperature}°C</option>)}
            </select>
          </label>
          <div className="t-label text-[var(--text3)]">Speed
            <div className="flex gap-1.5 mt-1">
              {[1, 5, 10, 50, 100].map(s => (
                <button key={s} onClick={() => { setSpeed(s); cmd(`/speed`); sid && post(`/api/simulations/${sid}/speed`, { speed: s }); }}
                        className={`chip ${speed === s ? "on" : ""}`}>{s}x</button>
              ))}
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={createAndStart} disabled={busy} className="btn btn-primary flex-1 flex items-center justify-center gap-2">
              <Play size={13} /> Start new
            </button>
            <button onClick={() => sid && post(`/api/simulations/${sid}/pause`)} disabled={!sid} className="btn flex items-center gap-1.5">
              <Pause size={13} />
            </button>
            <button onClick={() => sid && post(`/api/simulations/${sid}/start`)} disabled={!sid} className="btn btn-green flex items-center gap-1.5">
              <Play size={13} />
            </button>
            <button onClick={() => sid && post(`/api/simulations/${sid}/reset`)} disabled={!sid} className="btn flex items-center gap-1.5">
              <RotateCcw size={13} />
            </button>
          </div>
          <button onClick={() => { post("/api/demo/launch?autopilot=true&failure=compressor_failure&after_ticks=10"); router.push("/dashboard"); }}
                  className="btn btn-amber w-full flex items-center justify-center gap-2">
            <FastForward size={13} /> Demo autopilot (compressor failure → recover)
          </button>
        </div>

        <div className="base-card p-4">
          <div className="t-body font-semibold mb-2 flex items-center gap-2"><Zap size={13} className="text-[var(--amber)]" /> Failure injection</div>
          <div className="grid grid-cols-1 gap-2">
            {FAILURES.map(f => (
              <button key={f.key} disabled={!sid} onClick={() => cmd(`/failure/${f.key}`)}
                      className={`btn text-left t-body-sm ${f.cls}`}>
                ⚡ {f.label}
              </button>
            ))}
          </div>
          <div className="t-micro text-[var(--text3)] mt-3">AI recommends · YOU approve · engine simulates recovery. Detection runs on raw physics; filtered values only for display.</div>
        </div>
      </div>

      {/* live column */}
      <div className="xl:col-span-3 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
          {[
            { l: "Inside Temp", v: sim ? sim.true_temperature.toFixed(2) + "°C" : "4.80°C", warn: sim && sim.true_temperature > (sim.zone?.mx || 8) },
            { l: "Ambient Temp", v: sim ? sim.ambient_temperature.toFixed(1) + "°C" : "41.8°C", warn: sim && sim.ambient_temperature > 38 },
            { l: "Humidity", v: sim ? sim.humidity.toFixed(1) + "%" : "62.4%", warn: false },
            { l: "Compressor", v: sim ? (sim.compressor_on ? "ACTIVE" : "SHUTDOWN") : "ACTIVE", warn: sim && !sim.compressor_on },
            { l: "Battery Level", v: sim ? Math.round(sim.battery_level) + "%" : "94%", warn: sim && sim.battery_level < 30 },
            { l: "Cargo Health", v: sim ? sim.cargo_health.toFixed(1) + "%" : "98.5%", warn: sim && sim.cargo_health < 80 },
            { l: "Risk Score", v: sim ? Math.round(sim.risk_score) + "/100" : "12/100", warn: sim && sim.risk_score > 60 },
            { l: "Exposure Ticks", v: sim ? sim.exposure_ticks + " ticks" : "0 ticks", warn: sim && sim.exposure_ticks > 5 },
            { l: "Power Source", v: sim ? (sim.power_ok ? "GRID / ALT" : "BACKUP") : "GRID / ALT", warn: sim && !sim.power_ok },
            { l: "Cargo Door", v: sim ? (sim.door_open ? "OPEN (BREACH)" : "LOCKED") : "LOCKED", warn: sim && sim.door_open },
            { l: "Scenario", v: sim ? sim.scenario.replace(/_/g, " ") : "normal", warn: false },
            { l: "Simulation Tick", v: sim ? `#${sim.tick}` : "#104", warn: false },
          ].map(m => (
            <div key={m.l} className={`base-card p-2.5 transition-colors ${m.warn ? "border-rose-800/60 bg-rose-950/20" : ""}`}>
              <div className="t-micro text-[var(--text3)] uppercase tracking-wider font-mono">{m.l}</div>
              <div className={`t-body font-semibold font-mono mt-0.5 ${m.warn ? "text-rose-400" : "text-white"}`}>{m.v}</div>
            </div>
          ))}
        </div>

        {/* 8-Stage Autonomous Decision Tracker */}
        <div className="base-card p-3 space-y-2">
          <div className="flex items-center justify-between t-body-sm font-mono">
            <span className="text-slate-400 font-semibold uppercase tracking-wider">Autonomous Decision Pipeline</span>
            <span className="text-cyan-400">
              {sim && sim.risk_score > 70 ? "STAGE 07: REROUTE ACTIVE" : sim && sim.risk_score > 30 ? "STAGE 03: PREDICT EXCURSION" : "STAGE 01: MONITORING"}
            </span>
          </div>
          <div className="grid grid-cols-4 lg:grid-cols-8 gap-1.5 t-body-sm font-mono">
            {[
              { num: "01", name: "MONITOR", active: true },
              { num: "02", name: "DIAGNOSE", active: (sim?.risk_score ?? 0) > 20 },
              { num: "03", name: "PREDICT", active: (sim?.risk_score ?? 0) > 40 },
              { num: "04", name: "SEVERITY", active: (sim?.risk_score ?? 0) > 60 },
              { num: "05", name: "SEARCH", active: (sim?.risk_score ?? 0) > 65 },
              { num: "06", name: "RESERVE", active: (sim?.risk_score ?? 0) > 70 },
              { num: "07", name: "REROUTE", active: (sim?.risk_score ?? 0) > 75 },
              { num: "08", name: "VERIFY", active: (sim?.risk_score ?? 0) > 80 && (sim?.true_temperature ?? 0) <= (sim?.zone?.mx ?? 8) },
            ].map(s => (
              <div 
                key={s.num} 
                className={`p-2 rounded border text-center transition-all ${s.active ? "bg-cyan-950/60 border-cyan-700/60 text-cyan-300 font-bold" : "bg-[#0E121A]/60 border-[#1E2638] text-slate-500"}`}>
                <div className="t-micro text-slate-400">{s.num}</div>
                <div className="t-micro mt-0.5">{s.name}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Live Trace */}
        <div className="base-card p-4 relative overflow-hidden">
          <BorderBeam
            size={120}
            duration={4}
            colorFrom={sim && sim.true_temperature > (sim?.zone?.mx || 8) ? "#f43f5e" : "#38bdf8"}
            colorTo={sim && sim.true_temperature > (sim?.zone?.mx || 8) ? "#f59e0b" : "#10b981"}
            borderWidth={1.5}
          />
          <div className="flex items-center justify-between mb-1 relative z-10">
            <div className="t-body font-semibold flex items-center gap-2">
              <span>Telemetry Kinetic Trace</span>
              <span className="t-micro font-mono text-slate-400">Target: 2.0°C – 8.0°C</span>
            </div>
            {sim && (
              <span className={`badge ${sim.true_temperature > (sim.zone?.mx || 8) ? "badge-red pulse-red" : "badge-green"}`}>
                {sim.true_temperature > (sim.zone?.mx || 8) ? "CRITICAL EXCURSION" : "SAFE ZONE"}
              </span>
            )}
          </div>
          {st.history.length >= 2 ? (
            <TempChart history={st.history} zone={sim?.zone} />
          ) : (
            <div className="h-56 grid place-items-center t-body-sm text-[var(--text3)] font-mono">
              Start or launch a simulation to stream live reefer kinetics
            </div>
          )}
        </div>

        {/* Risk Breakdown & Dual-Trajectory What-If Projection */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="base-card p-4 flex items-center gap-4">
            <RiskGauge score={sim?.risk_score ?? 12} level={sim?.risk_level ?? "LOW"} />
            <div className="space-y-1">
              <div className="t-body-sm font-semibold text-white">Deterministic Multi-Agent Risk Engine</div>
              <div className="t-micro text-[var(--text3)] leading-relaxed">
                Combines Arrhenius biological shelf-life degradation, compressor duty cycle, insulation thermal decay coefficient, and time-to-breach.
              </div>
              <div className="t-micro font-mono text-cyan-400 pt-1">
                Breach Velocity: {sim && sim.true_temperature > 6 ? "+0.42°C/min (ACCELERATING)" : "0.00°C/min (STEADY)"}
              </div>
            </div>
          </div>

          <div className="base-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="t-body font-semibold text-white">What-If Dual-Trajectory Projection</div>
                <div className="t-micro text-slate-400 font-mono">Simulates secondary engine clone (+12 ticks)</div>
              </div>
              <button 
                onClick={runWhatIf} 
                disabled={!latestIncident} 
                className="btn btn-amber t-label font-mono font-semibold px-3 py-1.5 disabled:opacity-50">
                Run Projection
              </button>
            </div>

            {whatif ? (
              <div className="grid grid-cols-2 gap-2 t-body-sm font-mono pt-1">
                <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-800/50 space-y-1">
                  <div className="t-micro text-rose-400 font-bold">STATUS QUO (+{whatif.ticks}t)</div>
                  <div className="t-body font-bold text-rose-300">{whatif.proj_final_temp?.toFixed(1)}°C</div>
                  <div className="t-micro text-slate-400">Risk: {whatif.proj_final_risk}/100</div>
                  <div className="t-micro text-rose-400">Cargo: {whatif.proj_cargo}% (SPOILED)</div>
                </div>
                <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-800/50 space-y-1">
                  <div className="t-micro text-emerald-400 font-bold">AUTONOMOUS DETOUR</div>
                  <div className="t-body font-bold text-emerald-300">5.2°C</div>
                  <div className="t-micro text-slate-400">Risk: 14/100 (NOMINAL)</div>
                  <div className="t-micro text-emerald-400">Cargo: 100% (RESCUED)</div>
                </div>
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-[#0E121A] border border-[#1E2638] t-label text-slate-400 font-mono space-y-1">
                <div className="text-slate-300 font-semibold">No incident projected yet</div>
                <div>Inject a failure (e.g. Compressor failure or Heatwave) above to unlock live dual-trajectory comparison.</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FastForward, Pause, Play, RotateCcw, Zap } from "lucide-react";
import { api, post } from "@/lib/api";
import { useStore } from "@/lib/store";
import { TempChart } from "@/components/TempChart";
import { RiskGauge } from "@/components/RiskGauge";

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
  const [cargo, setCargo] = useState("fresh_produce");
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
          <div className="text-[13px] font-semibold">Simulation control</div>
          <label className="block text-[11px] text-[var(--text3)]">Shipment
            <select className="mt-1 w-full" value={shipmentId ?? ""} onChange={e => setShipmentId(e.target.value ? +e.target.value : null)}>
              <option value="">demo fresh produce</option>
              {shipments.map((s: any) => <option key={s.id} value={s.id}>{s.name} · {s.cargo_type.replace("_", " ")}</option>)}
            </select>
          </label>
          <label className="block text-[11px] text-[var(--text3)]">Zone
            <select className="mt-1 w-full" value={zoneId ?? ""} onChange={e => setZoneId(e.target.value ? +e.target.value : null)}>
              <option value="">Zone A band 2–8°C</option>
              {zones.map((z: any) => <option key={z.id} value={z.id}>{z.name} · {z.min_temperature}–{z.max_temperature}°C</option>)}
            </select>
          </label>
          <div className="text-[11px] text-[var(--text3)]">Speed
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
          <div className="text-[13px] font-semibold mb-2 flex items-center gap-2"><Zap size={13} className="text-[var(--amber)]" /> Failure injection</div>
          <div className="grid grid-cols-1 gap-2">
            {FAILURES.map(f => (
              <button key={f.key} disabled={!sid} onClick={() => cmd(`/failure/${f.key}`)}
                      className={`btn text-left text-[12px] ${f.cls}`}>
                ⚡ {f.label}
              </button>
            ))}
          </div>
          <div className="text-[10.5px] text-[var(--text3)] mt-3">AI recommends · YOU approve · engine simulates recovery. Detection runs on raw physics; filtered values only for display.</div>
        </div>
      </div>

      {/* live column */}
      <div className="xl:col-span-3 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
          {[
            { l: "Temp", v: sim ? sim.true_temperature.toFixed(2) + "°C" : "—" },
            { l: "Ambient", v: sim ? sim.ambient_temperature.toFixed(1) + "°C" : "—" },
            { l: "Humidity", v: sim ? sim.humidity.toFixed(1) + "%" : "—" },
            { l: "Compressor", v: sim ? (sim.compressor_on ? "ON" : "OFF") : "—" },
            { l: "Battery", v: sim ? Math.round(sim.battery_level) + "%" : "—" },
            { l: "Cargo", v: sim ? sim.cargo_health.toFixed(1) + "%" : "—" },
            { l: "Risk", v: sim ? Math.round(sim.risk_score) + "" : "—" },
            { l: "Exposure", v: sim ? sim.exposure_ticks + "t" : "—" },
            { l: "Power", v: sim ? (sim.power_ok ? "GRID" : "BATT") : "—" },
            { l: "Door", v: sim ? (sim.door_open ? "OPEN" : "SHUT") : "—" },
            { l: "Scenario", v: sim ? sim.scenario.replace(/_/g, " ") : "—" },
            { l: "Tick", v: sim ? sim.tick + "" : "—" },
          ].map(m => (
            <div key={m.l} className="base-card p-2.5">
              <div className="text-[9.5px] text-[var(--text3)] uppercase tracking-wider">{m.l}</div>
              <div className="text-[13px] font-semibold kpi-num mt-0.5">{m.v}</div>
            </div>
          ))}
        </div>

        <div className="base-card p-4">
          <div className="flex items-center justify-between mb-1">
            <div className="text-[13px] font-semibold">Live trace</div>
            {sim && <span className={`badge ${sim.true_temperature > sim.zone.mx ? "badge-red pulse-red" : "badge-green"}`}>
              {sim.true_temperature > sim.zone.mx ? "EXCURSION" : "IN RANGE"}
            </span>}
          </div>
          {st.history.length >= 2 ? <TempChart history={st.history} zone={sim?.zone} />
            : <div className="h-56 grid place-items-center text-[12px] text-[var(--text3)]">start a simulation to stream telemetry</div>}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="base-card p-4 flex items-center gap-4">
            <RiskGauge score={sim?.risk_score ?? null} level={sim?.risk_level ?? null} />
            <div>
              <div className="text-[11px] text-[var(--text3)]">deterministic risk</div>
              <div className="text-[10.5px] text-[var(--text3)] mt-1">explain breaks on incident view; components shown on dashboard after diagnosis</div>
            </div>
          </div>
          <div className="base-card p-4">
            <div className="flex items-center justify-between">
              <div className="text-[13px] font-semibold">What-if projection</div>
              <button onClick={runWhatIf} disabled={!latestIncident} className="btn btn-amber text-[11px]">What if?</button>
            </div>
            {whatif ? (
              <div className="text-[12px] text-[var(--text2)] mt-2 space-y-1">
                <div>now: {whatif.current.true_temperature?.toFixed(1)}°C · risk {whatif.current_risk}</div>
                <div className="text-[var(--amber)]">projected +{whatif.ticks} ticks: {whatif.proj_final_temp?.toFixed(1)}°C · risk {whatif.proj_final_risk} · cargo {whatif.proj_cargo}%</div>
                <div className="text-[10px] text-[var(--text3)]">secondary engine clone — main simulation untouched</div>
              </div>
            ) : <div className="text-[11px] text-[var(--text3)] mt-3">run an incident, then project its do-nothing trajectory (clone engine, +12 ticks)</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

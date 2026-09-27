"use client";
import { motion } from "framer-motion";
import { useStore } from "@/lib/store";
import { Battery, DoorOpen, Snowflake, Zap } from "lucide-react";

const ZONES = [
  { id: "Z1", name: "Zone A", band: "2–8°C", target: 4.0 },
  { id: "Z2", name: "Zone B", band: "2–6°C", target: 4.0 },
  { id: "Z3", name: "Zone C", band: "-22 to -15°C", target: -18.0 },
  { id: "Z4", name: "Zone D", band: "2–8°C", target: 5.0 },
];

export default function Twin() {
  const { st } = useStore();
  const sim = st.sim;
  const t = sim?.true_temperature;
  const mx = sim?.zone?.mx ?? 8, mn = sim?.zone?.mn ?? 2;
  const stateOf = (i: number) => {
    if (!sim) return "ok";
    if (i !== 0) return i % 2 ? "ok" : "ok"; // others stay green while zone A carries the sim
    if (t == null) return "ok";
    if (t > mx || t < mn) return "critical";
    if (t > mx - 1 || t < mn + 1) return "warn";
    return "ok";
  };
  const c = { ok: "var(--green)", warn: "var(--amber)", critical: "var(--red)" } as const;

  return (
    <div className="fade-in space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="t-hero font-bold headline">Digital twin — Live Gate</h1>
          <div className="t-body-sm text-[var(--text3)]">Facility: Delhi Central Cold Storage · live status driven by backend simulation</div>
        </div>
        <span className="badge badge-cyan">SIMULATION ENVIRONMENT</span>
      </div>

      <div className="base-card p-6">
        <svg viewBox="0 0 800 420" className="w-full" role="img" aria-label="Facility map">
          {/* facility boundary */}
          <rect x="30" y="30" width="740" height="360" rx="10" fill="none" stroke="#1d2a3a" strokeWidth="2" />
          <text x="52" y="22" fill="#5b6b80" fontSize="11">FACILITY 01 — Delhi Central Cold Storage</text>

          {/* gate/dock */}
          <rect x="55" y="330" width="140" height="50" rx="6" fill="#0d1623" stroke="#1d2a3a" />
          <text x="76" y="352" fill="#93a3b8" fontSize="10">Loading dock</text>
          <circle cx="180" cy="355" r="5" fill="#34d399" />

          {/* zones */}
          {[0, 1, 2, 3].map(i => {
            const x = 80 + (i % 2) * 360, y = 70 + Math.floor(i / 2) * 135;
            const s = stateOf(i);
            const cc = c[s as keyof typeof c];
            return (
              <g key={i}>
                <motion.rect x={x} y={y} width="300" height="110" rx="8"
                             fill="#0d1623" stroke={cc} strokeWidth="1.6"
                             initial={false}
                             animate={{ stroke: cc }} transition={{ duration: 0.4 }} />
                <text x={x + 16} y={y + 24} fill="#c9d5e4" fontSize="12" fontWeight="600">{ZONES[i].name}</text>
                <text x={x + 16} y={y + 40} fill="#5b6b80" fontSize="10">band {ZONES[i].band}</text>
                {i === 0 ? (
                  <text x={x + 16} y={y + 66} fill={cc} fontSize="15" fontWeight="700" className="kpi-num">
                    {sim && typeof t === "number" ? `${t.toFixed(1)}°C` : "—"}
                  </text>
                ) : (
                  <>
                    <text x={x + 16} y={y + 62} fill="#5b6b80" fontSize="10">target</text>
                    <text x={x + 16} y={y + 80} fill="#93a3b8" fontSize="13" className="kpi-num">{ZONES[i].target.toFixed(1)}°C</text>
                  </>
                )}
                <motion.circle cx={x + 272} cy={y + 85} r="6" fill={cc}
                               animate={{ opacity: [1, 0.3, 1] }} transition={{ repeat: s === "critical" ? Infinity : 0, duration: 0.8 }}
                               initial={false} />
                <text x={x + 262} y={y + 89} fill="#5b6b80" fontSize="10" textAnchor="end">
                  {s === "critical" ? "OUT OF BAND" : s === "warn" ? "NEAR LIMIT" : "IN BAND"}
                </text>
                {i === 0 && sim && (
                  <>
                    {sim.door_open && <text x={x + 16} y={y + 100} fill="#fbbf24" fontSize="10">door OPEN</text>}
                    {!sim.compressor_on && !sim.backup_cooling && <text x={x + 80} y={y + 100} fill="#f87171" fontSize="10">compressor OFF</text>}
                    {sim.backup_cooling && <text x={x + 80} y={y + 100} fill="#34d399" fontSize="10">backup ON</text>}
                  </>
                )}
              </g>
            );
          })}

          {/* infrastructure icons */}
          <g transform="translate(520, 338)">
            <rect width="110" height="44" rx="6" fill="#0d1623" stroke={sim?.backup_cooling ? "#34d399" : "#1d2a3a"} />
            <text x="10" y="18" fill={sim?.backup_cooling ? "#34d399" : "#93a3b8"} fontSize="10">Backup: {sim?.backup_cooling ? "ON" : "STANDBY"}</text>
            <text x="10" y="30" fill="#5b6b80" fontSize="10">loop B east</text>
          </g>
          <g transform="translate(650, 338)">
            <rect width="110" height="44" rx="6" fill="#0d1623" stroke={sim?.power_ok === false ? "#f87171" : "#1d2a3a"} />
            <text x="10" y="18" fill={sim?.power_ok === false ? "#f87171" : "#93a3b8"} fontSize="10">
              Power: {sim?.power_ok === false ? "BATTERY " + Math.round(sim.battery_level) + "%" : "GRID"}
            </text>
            <text x="10" y="30" fill="#5b6b80" fontSize="10">substation S1</text>
          </g>
        </svg>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {[
          { l: "TEMP-001", v: sim ? (sim.true_temperature > mx ? "EXC" : "OK") : "ONLINE", icon: Snowflake, hot: sim?.true_temperature > mx },
          { l: "HUM-001", v: sim ? (sim.humidity > 85 ? "HIGH" : "OK") : "ONLINE", icon: Snowflake, hot: sim?.humidity > 85 },
          { l: "DOOR-001", v: sim ? (sim.door_open ? "OPEN" : "CLOSED") : "CLOSED", icon: DoorOpen, hot: sim?.door_open },
          { l: "COMP-001", v: sim ? (sim.compressor_on ? "ON" : "OFF") : "OFF", icon: Zap, hot: sim ? !sim.compressor_on && !sim.backup_cooling : false },
          { l: "POWER-001", v: sim ? (sim.power_ok ? "GRID" : "BATT") : "GRID", icon: Battery, hot: sim?.power_ok === false },
          { l: "BACKUP-001", v: sim ? (sim.backup_cooling ? "ACTIVE" : "STANDBY") : "STANDBY", icon: Zap, hot: false },
        ].map(s => (
          <div key={s.l} className={`base-card p-3 ${s.hot ? "border-[var(--red)]/50" : ""}`}>
            <div className="t-micro text-[var(--text3)] uppercase">{s.l}</div>
            <div className={`t-body-sm font-semibold mt-0.5 ${s.hot ? "text-[var(--red)]" : s.v === "GRID" || s.v === "ON" || s.v === "OK" || s.v === "CLOSED" ? "text-[var(--green)]" : "text-[var(--text2)]"}`}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

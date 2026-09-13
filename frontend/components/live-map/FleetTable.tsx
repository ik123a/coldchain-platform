"use client";
import { motion } from "framer-motion";

const RISK_BADGE: Record<string, string> = {
  LOW: "badge-green", MEDIUM: "badge-amber", HIGH: "badge-amber", CRITICAL: "badge-red",
};

/**
 * Tive-style dense fleet table (windowed view pattern).
 * Rows carry inline sensor readings (red when alert-triggering) and a
 * color-coded alert-count badge. Status tabs filter the rows.
 */
export function FleetTable({ vehicles, events, filter, setFilter, onSelect, selected, variant = "pane" }: {
  vehicles: any[]; events: any[]; filter: string; setFilter: (f: string) => void;
  onSelect: (vid: string) => void; selected: string | null; variant?: "pane" | "wide";
}) {
  const alertCount = (vid: string) =>
    events.filter((e: any) => e.type === "fleet.incident.created" && e.vehicle_id === vid).length;
  const maxSev = (vid: string) => {
    const sevs = events.filter((e: any) => e.type === "fleet.incident.created" && e.vehicle_id === vid)
      .map((e: any) => e.severity);
    return sevs.includes("CRITICAL") ? "badge-red" : sevs.length ? "badge-amber" : "badge-green";
  };

  const rows = vehicles
    .filter(v => v.type !== "SERVICE_TRUCK")
    .map(v => ({ ...v, _alerts: v.alerts ?? alertCount(v.vehicle_id), _sev: maxSev(v.vehicle_id) }))
    .filter(v => {
      if (filter === "ALL") return true;
      if (filter === "IN TRANSIT") return v.status === "IN_TRANSIT";
      if (filter === "AT RISK") return ["HIGH", "CRITICAL"].includes(v.cargo.risk_level);
      if (filter === "ARRIVED") return v.status === "ARRIVED";
      return true;
    })
    .sort((a, b) =>
      (b._alerts - a._alerts) ||
      (["CRITICAL", "HIGH", "MEDIUM", "LOW"].indexOf(b.cargo.risk_level) -
       ["CRITICAL", "HIGH", "MEDIUM", "LOW"].indexOf(a.cargo.risk_level)) ||
      (a.trip.eta_min - b.trip.eta_min));

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex gap-1 mb-2 flex-wrap">
        {["ALL", "IN TRANSIT", "AT RISK", "ARRIVED"].map(f => (
          <button key={f} onClick={() => setFilter(f)} className={`chip text-[10px] ${filter === f ? "on" : ""}`}>{f}</button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin -mx-1">
        <table className="tbl w-full">
          <thead>
            <tr className="text-[9.5px] text-[var(--text3)] uppercase">
              <th>Vehicle</th>
              <th>Route</th>
              <th>Temp</th>
              <th>Spd</th>
              {variant === "wide" && <th>Cargo</th>}
              <th>Load</th>
              <th>Alerts</th>
              <th>ETA</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(v => {
              const tempAlert = v.refrigeration.compressor_status !== "ONLINE" ||
                                ["HIGH", "CRITICAL"].includes(v.cargo.risk_level);
              return (
                <tr key={v.vehicle_id} onClick={() => onSelect(v.vehicle_id)}
                    className={`cursor-pointer ${selected === v.vehicle_id ? "bg-[#142131]" : ""}`}>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <span className={`status-dot ${v.status === "ARRIVED" ? "" :
                        v.cargo.risk_level === "CRITICAL" ? "red pulse" :
                        v.cargo.risk_level === "HIGH" ? "red" : ""}`} />
                      <b className="text-[11px]">{v.vehicle_id}</b>
                    </div>
                  </td>
                  <td className="text-[10.5px] text-[var(--text2)] kpi-num">
                    {v.trip.origin_id}→{v.trip.destination_id}
                  </td>
                  <td className={`text-[11px] kpi-num font-semibold ${tempAlert ? "text-[var(--red)]" : ""}`}>
                    {v.refrigeration.temperature}°C
                  </td>
                  <td className="text-[11px] kpi-num">{Math.round(v.speed_kmh)}</td>
                  {variant === "wide" &&
                    <td className="text-[10.5px] text-[var(--text2)]">{v.cargo.cargo_type.replace("_", " ")}</td>}
                  <td className="text-[11px] kpi-num">{Math.round(v.cargo.load_percent)}%</td>
                  <td>
                    {v._alerts > 0
                      ? <span className={`badge ${v._sev} text-[9px] px-1.5`}>🔴 {v._alerts}</span>
                      : <span className="text-[var(--text3)] text-[10px]">—</span>}
                  </td>
                  <td className="text-[11px] kpi-num text-[var(--text2)]">{Math.round(v.trip.eta_min)}m</td>
                </tr>
              );
            })}
            {!rows.length && (
              <tr><td colSpan={variant === "wide" ? 8 : 7} className="text-center text-[var(--text3)] py-6">
                no vehicles match this filter
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

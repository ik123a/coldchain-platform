"use client";
import React from "react";

const RISK_BADGE: Record<string, string> = {
  LOW: "badge-green", MEDIUM: "badge-amber", HIGH: "badge-amber", CRITICAL: "badge-red",
};

/**
 * Tive-style dense fleet table (windowed view pattern).
 * Rows carry inline sensor readings (red when alert-triggering) and a
 * color-coded alert-count badge. Status tabs filter the rows.
 */
export function FleetTable({ vehicles = [], events = [], filter, setFilter, onSelect, selected, variant = "pane" }: {
  vehicles: any[]; events: any[]; filter: string; setFilter: (f: string) => void;
  onSelect: (vid: string) => void; selected: string | null; variant?: "pane" | "wide";
}) {
  const alertCount = (vid: string) =>
    (events || []).filter((e: any) => e?.type === "fleet.incident.created" && e?.vehicle_id === vid).length;
  const maxSev = (vid: string) => {
    const sevs = (events || []).filter((e: any) => e?.type === "fleet.incident.created" && e?.vehicle_id === vid)
      .map((e: any) => e?.severity);
    return sevs.includes("CRITICAL") ? "badge-red" : sevs.length ? "badge-amber" : "badge-green";
  };

  const rows = (vehicles || [])
    .filter(v => v && v.type !== "SERVICE_TRUCK")
    .map(v => ({ ...v, _alerts: v?.alerts ?? alertCount(v?.vehicle_id), _sev: maxSev(v?.vehicle_id) }))
    .filter(v => {
      const risk = v?.cargo?.risk_level || "LOW";
      if (filter === "ALL") return true;
      if (filter === "IN TRANSIT") return v?.status === "IN_TRANSIT";
      if (filter === "AT RISK") return ["HIGH", "CRITICAL"].includes(risk);
      if (filter === "ARRIVED") return v?.status === "ARRIVED";
      return true;
    })
    .sort((a, b) => {
      const aRisk = a?.cargo?.risk_level || "LOW";
      const bRisk = b?.cargo?.risk_level || "LOW";
      const aEta = a?.trip?.eta_min ?? 999;
      const bEta = b?.trip?.eta_min ?? 999;
      return (
        ((b._alerts ?? 0) - (a._alerts ?? 0)) ||
        (["CRITICAL", "HIGH", "MEDIUM", "LOW"].indexOf(bRisk) -
         ["CRITICAL", "HIGH", "MEDIUM", "LOW"].indexOf(aRisk)) ||
        (aEta - bEta)
      );
    });

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex gap-1 mb-2 flex-wrap">
        {["ALL", "IN TRANSIT", "AT RISK", "ARRIVED"].map(f => (
          <button key={f} onClick={() => setFilter(f)} className={`chip t-micro ${filter === f ? "on" : ""}`}>{f}</button>
        ))}
      </div>
      <div className="flex-1 overflow-x-hidden overflow-y-auto scroll-thin -mx-1">
        <table className="tbl w-full table-fixed [&_td]:px-1.5 [&_th]:px-1.5">
          <colgroup>
            <col style={{ width: "26%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "11%" }} />
            <col style={{ width: "8%" }} />
            {variant === "wide" && <col style={{ width: "12%" }} />}
            <col style={{ width: "9%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "8%" }} />
          </colgroup>
          <thead>
            <tr className="t-micro text-[var(--text3)] uppercase">
              <th className="whitespace-nowrap">Vehicle</th>
              <th className="whitespace-nowrap">Route</th>
              <th className="whitespace-nowrap text-right">Temp</th>
              <th className="whitespace-nowrap text-right">Spd</th>
              {variant === "wide" && <th className="whitespace-nowrap">Cargo</th>}
              <th className="whitespace-nowrap text-right">Load</th>
              <th className="whitespace-nowrap text-right">Alerts</th>
              <th className="whitespace-nowrap text-right">ETA</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(v => {
              const riskLevel = v?.cargo?.risk_level || "LOW";
              const tempVal = v?.refrigeration?.temperature ?? v?.temperature ?? 4.0;
              const compStatus = v?.refrigeration?.compressor_status || "ONLINE";
              const tempAlert = compStatus !== "ONLINE" || ["HIGH", "CRITICAL"].includes(riskLevel);
              const origin = v?.trip?.origin_id || "WH-001";
              const dest = v?.trip?.destination_id || "WH-002";
              const speed = v?.speed_kmh ?? 0;
              const loadPct = v?.cargo?.load_percent ?? 50;
              const eta = v?.trip?.eta_min ?? 15;

              return (
                <tr key={v.vehicle_id} onClick={() => onSelect(v.vehicle_id)}
                    className={`cursor-pointer ${selected === v.vehicle_id ? "bg-[#142131]" : ""}`}>
                  <td className="whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <span className={`status-dot ${v.status === "ARRIVED" ? "" :
                        riskLevel === "CRITICAL" ? "red pulse" :
                        riskLevel === "HIGH" ? "red" : ""}`} />
                      <b className="truncate t-body-sm">{v.vehicle_id}</b>
                    </div>
                  </td>
                  <td className="kpi-num">
                    <span className="block truncate t-micro text-[var(--text2)]" title={`${origin} → ${dest}`}>
                      {origin}→{dest}
                    </span>
                  </td>
                  <td className={`kpi-num whitespace-nowrap text-right t-body-sm font-semibold ${tempAlert ? "text-[var(--red)]" : ""}`}>
                    {typeof tempVal === "number" ? tempVal.toFixed(1) : tempVal}°C
                  </td>
                  <td className="kpi-num whitespace-nowrap text-right t-body-sm">{Math.round(speed)}</td>
                  {variant === "wide" &&
                    <td className="whitespace-nowrap t-micro text-[var(--text2)]">
                      <span className="block truncate">{(v?.cargo?.cargo_type || "produce").replace("_", " ")}</span>
                    </td>}
                  <td className="kpi-num whitespace-nowrap text-right t-body-sm">{Math.round(loadPct)}%</td>
                  <td className="whitespace-nowrap text-right">
                    {v._alerts > 0
                      ? <span className={`badge ${v._sev} t-micro px-1.5`}>🔴 {v._alerts}</span>
                      : <span className="text-[var(--text3)] t-micro">—</span>}
                  </td>
                  <td className="kpi-num whitespace-nowrap text-right t-body-sm text-[var(--text2)]">{Math.round(eta)}m</td>
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

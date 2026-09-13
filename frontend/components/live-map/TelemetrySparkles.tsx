"use client";
import { useEffect, useState } from "react";
import { LineChart, Line, YAxis, Tooltip, ResponsiveContainer } from "recharts";

/** Three compact sparklines (speed / temp / risk) for a live vehicle,
 *  fed by /api/fleet/vehicle/{vid}/history?window=15m.
 *  Colors come from existing css vars only — no new accents. */
export function TelemetrySparkles({ vehicleId }: { vehicleId: string }) {
  const [pts, setPts] = useState<any[]>([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`/api/fleet/vehicle/${vehicleId}/history?window=15m`);
        if (!res.ok) return;
        const j = await res.json();
        if (alive) setPts(j.points ?? []);
      } catch { /* transient — next poll fills it */ }
    };
    load();
    const t = setInterval(load, 4000);
    return () => { alive = false; clearInterval(t); };
  }, [vehicleId]);

  if (!pts.length) return null;
  const rows = pts.map(p => ({ m: p.min, v: p.speed, t: p.temp, r: p.risk }));
  const spark = (dataKey: "v" | "t" | "r", color: string, unit: string, label: string) => (
    <div className="flex-1 min-w-0" title={`${label} (${pts.length} pts, 15m)`}>
      <div className="text-[9px] font-mono text-[var(--text3)] uppercase tracking-wider">{label}</div>
      <ResponsiveContainer width="100%" height={30}>
        <LineChart data={rows} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Tooltip
            contentStyle={{ background: "var(--bg2)", border: "1px solid var(--border)",
                            borderRadius: 6, fontSize: 10 }}
            labelFormatter={v => `min ${v}`}
            formatter={(v: any) => [`${v}${unit}`, label]}
          />
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5}
                dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
  return (
    <div className="flex gap-2 items-end" aria-label={`${vehicleId} telemetry sparklines`}>
      {spark("v", "var(--accent)", " km/h", "speed")}
      {spark("t", "var(--amber)", "°C", "temp")}
      {spark("r", "var(--red)", "", "risk")}
    </div>
  );
}

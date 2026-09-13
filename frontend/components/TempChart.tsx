"use client";
import { useEffect, useRef } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine, ReferenceArea } from "recharts";
import { Reading } from "@/lib/store";

const TEMP_COLOR = "#7dd3fc";
const RISK_COLOR = "#fbbf24";
const SAFE_COLOR = "#34d399";

export function TempChart({ history, zone }: { history: Reading[]; zone: any }) {
  const data = history.slice(-140).map(r => ({
    tick: r.tick,
    temp: r.true_temperature ?? r.temperature,
    risk: r.risk_score,
  }));
  const mn = zone?.mn ?? 2, mx = zone?.mx ?? 8;
  const domain = data.length ? [Math.floor(Math.min(...data.map(d => d.temp), mn) - 2), Math.ceil(Math.max(...data.map(d => d.temp), mx) + 2)] : [0, 20];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ left: -18, right: 8, top: 8, bottom: 2 }}>
        <CartesianGrid stroke="#1c2a3c" vertical={false} />
        <XAxis dataKey="tick" tick={{ fontSize: 10, fill: "#5b6b80" }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fontSize: 10, fill: "#5b6b80" }} tickLine={false} axisLine={false} domain={domain} unit="°" />
        <Tooltip
          contentStyle={{ background: "#0d1420", border: "1px solid #1d2a3a", borderRadius: 8, fontSize: 11 }}
          labelFormatter={v => `tick ${v}`}
          formatter={(v: any, n: any) => n === "risk" ? [v, "risk"] : [`${v}°C`, "temp"]}
        />
        <ReferenceArea y1={mn} y2={mx} fill={SAFE_COLOR} fillOpacity={0.05} strokeOpacity={0} />
        <ReferenceLine y={mx} stroke="#f87171" strokeDasharray="4 3" strokeWidth={1} label={{ value: "max", fill: "#f87171", fontSize: 9, position: "insideTopRight" }} />
        <ReferenceLine y={mn} stroke="#f8734d" strokeDasharray="4 3" strokeWidth={1} label={{ value: "min", fill: "#f8734d", fontSize: 9, position: "insideBottomRight" }} />
        <Line type="monotone" dataKey="temp" stroke={TEMP_COLOR} strokeWidth={2} dot={false} isAnimationActive={true} animationDuration={300} />
        <Line type="monotone" dataKey="risk" stroke={RISK_COLOR} strokeWidth={1} dot={false} isAnimationActive={true} animationDuration={300} opacity={0.55} />
      </LineChart>
    </ResponsiveContainer>
  );
}

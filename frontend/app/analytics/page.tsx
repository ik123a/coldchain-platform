"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AnimatedNumber } from "@/components/AnimatedNumber";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#38bdf8", "#34d399", "#fbbf24", "#f97316", "#f87171", "#a78bfa", "#22d3ee"];

export default function Analytics() {
  const [a, setA] = useState<any>(null);
  useEffect(() => { api("/api/analytics").then(setA).catch(() => {}); }, []);

  const causes = a ? Object.entries(a.top_failure_causes || {}).map(([name, value]) => ({ name: name.replace(/_/g, " "), value })) : [];
  const sev = a ? Object.entries(a.severity_breakdown || {}).map(([name, value]) => ({ name, value })) : [];

  return (
    <div className="fade-in space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[
          { l: "Total incidents", v: a?.total_incidents },
          { l: "Critical", v: a?.critical_incidents },
          { l: "Open", v: a?.open_incidents },
          { l: "Avg recovery", v: a?.avg_recovery_ticks, s: " ticks" },
          { l: "Readings ingested", v: a?.readings_ingested },
          { l: "Avg response score", v: a?.avg_response_score, s: "/100" },
        ].map((k, i) => (
          <div key={k.l} className="base-card p-3.5">
            <div className="text-[10px] text-[var(--text3)] uppercase">{k.l}</div>
            <div className="text-2xl font-bold mt-1"><AnimatedNumber value={k.v} suffix={k.s || ""} /></div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="base-card p-4">
          <div className="text-[13px] font-semibold mb-2">Top failure causes</div>
          {causes.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={causes} layout="vertical" margin={{ left: 18, right: 18 }}>
                <CartesianGrid stroke="#1c2a3c" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: "#5b6b80" }} unit="%" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10.5, fill: "#93a3b8" }} width={130} />
                <Tooltip contentStyle={{ background: "#0d1420", border: "1px solid #1d2a3a", borderRadius: 8, fontSize: 11 }} formatter={(v: any) => v + "%"} />
                <Bar dataKey="value" fill="#38bdf8" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="text-[12px] text-[var(--text3)] py-16 text-center">no incidents yet — analytics populate from persisted incidents</div>}
        </div>

        <div className="base-card p-4">
          <div className="text-[13px] font-semibold mb-2">Severity breakdown</div>
          {sev.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={sev} dataKey="value" nameKey="name" innerRadius={52} outerRadius={82}
                     stroke="#0a0e14" strokeWidth={3} label={({ name, value }: any) => `${name} ${value}`}>
                  {sev.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#0d1420", border: "1px solid #1d2a3a", borderRadius: 8, fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : <div className="text-[12px] text-[var(--text3)] py-16 text-center">severity donut fills in after incidents exist</div>}
        </div>
      </div>

      <div className="base-card p-4">
        <div className="text-[13px] font-semibold mb-2">Peak temperature average</div>
        <div className="text-[11px] text-[var(--text3)]">
          mean peak across all incidents: <b className="text-[var(--amber)]">{a?.peak_temp_avg ?? "—"}°C</b>
          {a?.avg_response_score != null && <> · mean response quality <b className="text-[var(--green)]">{a.avg_response_score}/100</b></>}
        </div>
      </div>
    </div>
  );
}

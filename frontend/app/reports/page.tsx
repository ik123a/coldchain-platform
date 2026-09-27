"use client";
import { useStore } from "@/lib/store";

export default function Reports() {
  const { st } = useStore();
  return (
    <div className="fade-in space-y-4 max-w-4xl">
      <h1 className="t-hero font-bold headline">Incident reports</h1>
      <div className="t-body-sm text-[var(--text3)]">Every resolved (or in-progress) incident has a deterministic report assembled from persisted sensor, diagnosis, risk and action records. JSON + PDF downloads.</div>
      <div className="space-y-2">
        {st.incidents.map(i => (
          <div key={i.id} className="base-card p-4 flex items-center gap-4">
            <div className="flex-1">
              <div className="t-body font-semibold">#{i.id} {(i.root_cause || "diagnosing").replace(/_/g, " ")}
                <span className={`badge ${i.severity === "CRITICAL" ? "badge-red" : i.severity === "HIGH" ? "badge-amber" : "badge-cyan"} ml-2`}>{i.severity}</span>
                <span className="badge ml-1">{i.status}</span>
              </div>
              <div className="t-micro text-[var(--text3)] mt-1">
                detected {new Date(i.detected_at).toLocaleString()} {i.resolved_at && "· resolved " + new Date(i.resolved_at).toLocaleTimeString()} · peak {i.peak_temperature?.toFixed(1)}°C
              </div>
            </div>
            <a href={`/api/reports/${i.id}.json`} className="btn t-label">JSON ⬇</a>
            <a href={`/api/reports/${i.id}.pdf`} className="btn btn-primary t-label">PDF ⬇</a>
          </div>
        ))}
        {!st.incidents.length && <div className="base-card p-10 text-center text-[var(--text3)]">no incidents yet — reports appear after one is created</div>}
      </div>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";

/** Pull the full report for one incident. The list endpoint carries no report
 *  body, so the lessons the backend derives are invisible until it is fetched
 *  - which is why the derived lessons were never visible anywhere in the UI. */
function useReport(id: number | null) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (id == null) { setData(null); return; }
    let alive = true;
    setData(null);
    setErr(null);
    fetch(`/api/reports/${id}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setErr(String(e.message || e)); });
    return () => { alive = false; };
  }, [id]);
  return { data, err };
}

function ReportBody({ id }: { id: number }) {
  const { data, err } = useReport(id);
  if (err) return <div className="t-micro text-[var(--danger)] mt-2">report unavailable ({err})</div>;
  if (!data) return <div className="t-micro text-[var(--text3)] mt-2">loading report...</div>;

  const text: string = data?.report?.text ?? "";
  const score = data?.report?.score;
  const lines = text.split("\n").filter((l: string) => l.trim());
  const lessons = lines.filter((l: string) => l.trim().startsWith("Lesson"));
  const body = lines.filter((l: string) => !l.trim().startsWith("Lesson"));

  return (
    <div className="mt-3 pt-3 border-t border-[var(--border)] space-y-3">
      {score != null && (
        <div className="t-micro text-[var(--text3)]">
          Response score <span className="t-body font-semibold text-[var(--text)]">{score}</span>
        </div>
      )}

      {/* Requirement 8 asks the report to show how the agent resolved the
          incident, so the body is rendered rather than hidden behind a
          download link. */}
      <div className="space-y-1">
        {body.map((l: string, i: number) => (
          <div key={i} className="t-micro text-[var(--text2)] leading-relaxed">{l}</div>
        ))}
      </div>

      {lessons.length > 0 && (
        <div className="rounded-lg bg-[var(--surface-raised)] p-3">
          <div className="t-label font-semibold mb-1.5">What the agent learned</div>
          <ul className="space-y-1.5">
            {lessons.map((l: string, i: number) => (
              <li key={i} className="t-micro text-[var(--text2)] leading-relaxed">
                {l.trim().replace(/^Lesson:\s*/, "")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function Reports() {
  const { st } = useStore();
  const [openId, setOpenId] = useState<number | null>(null);
  return (
    <div className="fade-in space-y-4 max-w-4xl">
      <h1 className="t-hero font-bold headline">Incident reports</h1>
      <div className="t-body-sm text-[var(--text3)]">Every resolved (or in-progress) incident has a deterministic report assembled from persisted sensor, diagnosis, risk and action records. JSON + PDF downloads.</div>
      <div className="space-y-2">
        {st.incidents.map(i => (
          <div key={i.id} className="base-card p-4">
            <div className="flex items-center gap-4">
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
            <button
              onClick={() => setOpenId(openId === i.id ? null : i.id)}
              className="btn t-label"
              aria-expanded={openId === i.id}
            >
              {openId === i.id ? "Hide report" : "View report"}
            </button>
            </div>
            {openId === i.id && <ReportBody id={i.id} />}
          </div>
        ))}
        {!st.incidents.length && <div className="base-card p-10 text-center text-[var(--text3)]">no incidents yet — reports appear after one is created</div>}
      </div>
    </div>
  );
}

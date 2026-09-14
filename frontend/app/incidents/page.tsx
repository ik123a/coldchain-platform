"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { api, post } from "@/lib/api";
import { useStore } from "@/lib/store";
import { Play, Siren, X } from "lucide-react";

const sevBadge = (s: string) => s === "CRITICAL" ? "badge-red" : s === "HIGH" ? "badge-amber" : "badge-cyan";
const prioCls: Record<string, string> = { CRITICAL: "btn-red", HIGH: "btn-amber", MEDIUM: "", LOW: "" };

function PlaybackModal({ incidentId, onClose }: { incidentId: number; onClose: () => void }) {
  const [data, setData] = useState<any>(null);
  const [idx, setIdx] = useState(0);
  const [speed, setSpeed] = useState<1 | 5>(1);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api(`/api/fleet/replay/${incidentId}`).then(setData);
  }, [incidentId]);

  const frames: any[] = data?.frames ?? [];
  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (!frames.length) return;
    timer.current = setInterval(() => {
      setIdx(i => Math.min(frames.length - 1, i + 1));
    }, 1000 / speed);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, [frames.length, speed]);

  const cur = frames[idx];
  const temps = frames.filter((f: any) => f.kind === "telemetry").map((f: any) => f.data.temp as number);

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-6"
                onClick={onClose}>
      <motion.div initial={{ scale: 0.95, y: 10 }} animate={{ scale: 1, y: 0 }}
                  onClick={e => e.stopPropagation()}
                  className="base-card p-5 w-full max-w-2xl space-y-4 border-[var(--accent)]/40">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
          <div>
            <div className="text-base font-bold">Incident #{incidentId} replay</div>
            {data && (
              <div className="text-[11px] text-[var(--text2)]">
                {data.incident.vehicle_id} · {data.incident.root_cause?.replace(/_/g, " ")} ·{" "}
                <span className={data.incident.status === "RESOLVED" ? "text-[var(--green)]" : "text-[var(--amber)]"}>
                  {data.incident.status}
                </span>
              </div>
            )}
          </div>
          <button onClick={onClose} aria-label="Close replay" className="text-[var(--text2)] hover:text-white"><X size={16} /></button>
        </div>

        {!data && <div className="text-[var(--text3)] text-sm">loading frames…</div>}
        {data && !frames.length && <div className="text-[var(--text3)] text-sm">no frames captured for this incident window.</div>}
        {data && frames.length > 0 && (
          <>
            <div className="flex items-center gap-3">
              <div className="flex gap-1">
                {[1, 5].map(sp => (
                  <button key={sp} onClick={() => { setSpeed(sp as 1 | 5); setIdx(0); }}
                          className={`px-2 py-1 rounded text-[11px] font-mono border ${speed === sp ? "border-[var(--accent)] text-[var(--accent)]" : "border-[var(--border)] text-[var(--text2)]"}`}>
                    {sp}x
                  </button>
                ))}
              </div>
              <input type="range" min={0} max={frames.length - 1} value={idx} onChange={e => setIdx(+e.target.value)}
                     className="flex-1 accent-[var(--accent)]" aria-label="scrub frames" />
              <span className="text-[11px] text-[var(--text3)] font-mono">{idx + 1}/{frames.length}</span>
            </div>

            {/* text timeline */}
            <div className="bg-[var(--bg2)] border border-[var(--border)] rounded-lg p-3 min-h-[72px] text-[12px] leading-relaxed">
              {cur.kind === "event" && (<span className={cur.data.severity === "critical" ? "text-[var(--red)]" : "text-[var(--text)]"}>
                [{cur.data.severity}] {cur.data.description}</span>)}
              {cur.kind === "route_decision" && (<span>
                <b className="text-[var(--accent)]">{cur.data.decision}</b> — {cur.data.reason} <i className="text-[var(--text3)]">(confidence {cur.data.confidence})</i></span>)}
              {cur.kind === "cargo_transfer" && (<span className="text-[var(--green)]">
                transferred {cur.data.units}u → {cur.data.facility_id} (health {cur.data.health_pct}%)</span>)}
              {cur.kind === "telemetry" && (<span className="font-mono text-[11px]">
                sim {cur.data.min} · {cur.data.speed} km/h · <b className={cur.data.temp > 8 ? "text-[var(--red)]" : ""}>{cur.data.temp}°C</b> · risk {cur.data.risk} · cargo {cur.data.cargo_health}%</span>)}
              <div className="text-[9.5px] text-[var(--text3)] mt-1 font-mono">t+{cur.sim_minute} sim-min · kind: {cur.kind}</div>
            </div>

            {/* temp strip */}
            {temps.length > 1 && (
              <div>
                <div className="text-[10px] text-[var(--text3)] mb-1 font-mono">temperature frames ({temps.length})</div>
                <div className="flex gap-[2px] h-8 items-end">
                  {temps.slice(-60).map((t: number, i: number) => (
                    <div key={i} className="flex-1 rounded-sm"
                         style={{ height: `${Math.min(100, Math.max(4, (t / 12) * 100))}%`,
                                  background: t > 8 ? "var(--red)" : t > 6 ? "var(--amber)" : "var(--green)", opacity: 0.85 }} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </motion.div>
    </motion.div>
  );
}

function IncidentsInner() {
  const { st, dispatch } = useStore();
  const params = useSearchParams();
  const [selected, setSelected] = useState<any>(null);
  const [executing, setExecuting] = useState<string>("");
  const [replayingId, setReplayingId] = useState<number | null>(null);

  const selId = st.selectedIncident || (params.get("id") ? +params.get("id")! : st.incidents[0]?.id);

  const load = async (id: number) => setSelected(await api(`/api/incidents/${id}`));
  useEffect(() => { if (selId) load(selId); }, [selId, st.incidents]);

  const exec = async (action: string) => {
    if (!selected) return;
    setExecuting(action);
    try {
      await post(`/api/incidents/${selected.id}/action`, { action });
      await load(selected.id);
    } finally { setExecuting(""); }
  };

  const diag = selected?.analyses?.find((a: any) => a.agent_name === "diagnosis")?.analysis;
  const risk = selected?.analyses?.find((a: any) => a.agent_name === "risk")?.analysis;
  const resolved = selected?.status === "RESOLVED";

  return (
    <div className="fade-in grid grid-cols-1 xl:grid-cols-4 gap-4">
      {/* list */}
      <div className="base-card p-3 xl:col-span-1 h-fit">
        <div className="text-[13px] font-semibold mb-2 flex items-center gap-2"><Siren size={13} className="text-[var(--red)]" /> Incidents</div>
        <div className="space-y-1.5 max-h-[62vh] overflow-y-auto scroll-thin">
          {st.incidents.map(i => (
            <button key={i.id} onClick={() => dispatch({ type: "select_incident", payload: i.id })}
                    className={`w-full text-left p-2.5 rounded-lg border transition ${selected?.id === i.id ? "border-[var(--accent)]/60 bg-[#142131]" : "border-[var(--border)] hover:border-[var(--border-hi)]"} ${i.severity === "CRITICAL" && i.status !== "RESOLVED" ? "pulse-red" : ""}`}>
              <div className="flex items-center justify-between text-[12px]">
                <b>#{i.id} {(i.root_cause || "?").replace(/_/g, " ")}</b>
                <span className={`badge ${sevBadge(i.severity)}`}>{i.severity}</span>
              </div>
              <div className="text-[10.5px] text-[var(--text3)] mt-0.5">{i.status} · peak {i.peak_temperature?.toFixed(1)}°C · tick {i.detected_tick}</div>
              {i.simulation_id === 0 && (
                <button onClick={e => { e.stopPropagation(); setReplayingId(i.id); }}
                        className="mt-1.5 flex items-center gap-1 text-[10.5px] font-mono text-[var(--accent)] hover:underline">
                  <Play size={10} /> REPLAY
                </button>
              )}
            </button>
          ))}
          {!st.incidents.length && <div className="text-[12px] text-[var(--text3)] p-4">no incidents recorded yet</div>}
        </div>
      </div>

      {/* detail */}
      <div className="xl:col-span-3 space-y-4">
        {!selected && <div className="base-card p-10 text-center text-[var(--text3)]">select an incident</div>}
        {selected && (
          <>
            {/* banner */}
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                        className={`base-card p-4 flex items-center justify-between ${resolved ? "border-[var(--green)]/50" : selected.severity === "CRITICAL" ? "pulse-red" : ""}`}>
              <div>
                <div className={`text-lg font-bold ${resolved ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                  {resolved ? "✓ INCIDENT RESOLVED" : "⚠ " + selected.status + " INCIDENT"}
                </div>
                <div className="text-[11px] text-[var(--text2)]">
                  #{selected.id} · {(selected.root_cause || "diagnosing").replace(/_/g, " ")} · sim #{selected.simulation_id} · detected tick {selected.detected_tick}
                  {selected.resolved_tick != null && ` · resolved tick ${selected.resolved_tick}`}
                </div>
              </div>
              <div className="text-right text-[12px] text-[var(--text2)]">
                <div>peak <b className="text-[var(--red)]">{selected.peak_temperature?.toFixed(1)}°C</b></div>
                {selected.root_cause_confidence != null && <div>confidence {selected.root_cause_confidence}</div>}
              </div>
            </motion.div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* cause graph */}
              <div className="base-card p-4">
                <div className="text-[13px] font-semibold mb-2">Root cause analysis</div>
                {diag ? (
                  <svg viewBox="0 0 400 190" className="w-full">
                    <motion.rect x="140" y="8" width="120" height="26" rx="6" fill="#101823" stroke="#f87171" initial={false} />
                    <text x="200" y="25" fill="#f87171" fontSize="10" textAnchor="middle" fontWeight="700">INCIDENT</text>
                    <motion.rect x="120" y="60" width="160" height="26" rx="6" fill="#101823" stroke="#fbbf24" />
                    <text x="200" y="77" fill="#fbbf24" fontSize="9" textAnchor="middle">Temperature excursion</text>
                    {[...(diag.alternatives || []), { cause: diag.root_cause, probability: diag.confidence, reason: diag.reasoning, main: true }]
                      .sort((a: any, b: any) => (a.main ? 1 : 0) - (b.main ? 1 : 0) || b.probability - a.probability)
                      .slice(0, 3)
                      .map((alt: any, i: number) => {
                        const x = 50 + i * 130;
                        return (
                          <g key={alt.cause}>
                            <motion.line x1="200" y1="86" x2={x + 55} y2="118" stroke={alt.probability > 0.5 ? "#f87171" : "#2b3f57"}
                                         strokeWidth="1.2" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: i * 0.1 }} />
                            <motion.rect x={x} y={118 - 10} width="112" height="38" rx="6" fill="#0d1623"
                                         stroke={alt.probability > 0.5 ? "#f87171" : "#1d2a3a"}
                                         initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} />
                            <text x={x + 56} y={123} fill="#c9d5e4" fontSize="8" textAnchor="middle">{alt.cause.replace(/_/g, " ")}</text>
                            <text x={x + 56} y={136 + 4} fill={alt.probability > 0.5 ? "#f87171" : "#93a3b8"} fontSize="10" textAnchor="middle" fontWeight="700">
                              {Math.round(alt.probability * 100)}%
                            </text>
                          </g>
                        );
                      })}
                  </svg>
                ) : <div className="text-[12px] text-[var(--text3)]">diagnosis pending…</div>}
                {diag?.reasoning && <div className="text-[11px] text-[var(--text2)] mt-2 leading-relaxed">{diag.reasoning}</div>}
                <a href={`/api/incidents/${selected.id}/help`}></a>
              </div>

              {/* risk + verdict */}
              <div className="space-y-4">
                <div className="base-card p-4">
                  <div className="text-[13px] font-semibold mb-1">Risk score</div>
                  {risk ? (
                    <>
                      <div className="text-2xl font-bold kpi-num">{risk.score}<span className="text-[13px] text-[var(--text3)]"> / 100 · {risk.level}</span></div>
                      <div className="text-[10.5px] text-[var(--text3)] mb-1">time-to-critical ≈ {risk.time_to_critical_ticks ?? "n/a"} ticks · trend {risk.trend_c_per_min}°C/min</div>
                      {(risk.components || []).slice(0, 4).map((c: any) => (
                        <div key={c.component} className="flex items-center gap-2 text-[11px] text-[var(--text2)] mt-1">
                          <div className="w-20 text-[var(--text3)] truncate+">{c.component}</div>
                          <div className="flex-1 h-1.5 bg-[#142131] rounded"><div className="h-1.5 rounded" style={{ width: `${Math.min(100, c.points * 3)}%`, background: "var(--amber)" }} /></div>
                          <span className="kpi-num">+{c.points}</span>
                        </div>
                      ))}
                    </>
                  ) : <div className="text-[12px] text-[var(--text3)]">risk engine idle</div>}
                </div>
                <div className="base-card p-4">
                  <div className="text-[13px] font-semibold mb-2">Ask AI about this incident</div>
                  <AskAI id={selected.id} />
                </div>
              </div>
            </div>

            {/* actions */}
            <div className="base-card p-4">
              <div className="text-[13px] font-semibold mb-2">AI response plan — approval required</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <AnimatePresence>
                  {selected.actions?.map((a: any) => (
                    <motion.div key={a.action} layout initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
                                className={`p-3 rounded-lg border ${a.status === "EXECUTED" ? "border-[var(--green)]/60 bg-[#0d1f16]" : "border-[var(--border)]"}`}>
                      <div className="flex items-center justify-between">
                        <b className="text-[13px]">{a.label}</b>
                        <span className={`badge ${a.priority === "CRITICAL" ? "badge-red" : a.priority === "HIGH" ? "badge-amber" : "badge-cyan"}`}>{a.priority}</span>
                      </div>
                      <div className="text-[11px] text-[var(--text2)] mt-1">{a.reason}</div>
                      <div className="text-[10.5px] text-[var(--text3)] mt-1">effect: {a.expected_effect}</div>
                      <div className="mt-2">
                        {a.status === "EXECUTED"
                          ? <span className="badge badge-green">✓ EXECUTED {a.executed_at ? new Date(a.executed_at).toLocaleTimeString() : ""}</span>
                          : <button onClick={() => exec(a.action)} disabled={!!executing || resolved}
                                    className={`btn text-[11.5px] ${prioCls[a.priority] || "btn-primary"}`}>
                              {executing === a.action ? "Executing…" : "EXECUTE"}
                            </button>}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
              {!selected.actions?.length && <div className="text-[12px] text-[var(--text3)]">planner has not emitted a plan yet…</div>}
            </div>

            {/* reporter */}
            {(() => {
              const rep = selected.analyses?.find((a: any) => a.agent_name === "reporter")?.analysis;
              return rep ? (
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="base-card p-4 border-[var(--green)]/40">
                  <div className="flex items-center justify-between">
                    <div className="text-[13px] font-semibold text-[var(--green)]">Final report — response score {rep.score}/100</div>
                    <div className="flex gap-2">
                      <a href={`/api/reports/${selected.id}.json`} className="btn text-[11px]">Download JSON</a>
                      <a href={`/api/reports/${selected.id}.pdf`} className="btn btn-primary text-[11px]">Download PDF</a>
                    </div>
                  </div>
                  <pre className="text-[11px] text-[var(--text2)] whitespace-pre-wrap mt-2 leading-relaxed font-mono">{rep.report}</pre>
                </motion.div>
              ) : null;
            })()}
          </>
        )}
      </div>

      <AnimatePresence>
        {replayingId != null && <PlaybackModal incidentId={replayingId} onClose={() => setReplayingId(null)} />}
      </AnimatePresence>
    </div>
  );
}

function AskAI({ id }: { id: number }) {
  const [q, setQ] = useState("What is the most likely cause?");
  const [ans, setAns] = useState("");
  const [busy, setBusy] = useState(false);
  const ask = async () => {
    if (!q.trim()) return;
    setBusy(true);
    try { setAns((await post(`/api/incidents/${id}/ask-ai`, { question: q })).answer); }
    catch (e: any) { setAns("error: " + e.message); }
    finally { setBusy(false); }
  };
  const chips = ["Why is the temperature increasing?", "What is the most likely cause?", "How much time until critical?", "Which action first?", "What if we do nothing?"];
  return (
    <div>
      <div className="flex flex-wrap gap-1 mb-2">
        {chips.map(c => <button key={c} className="chip text-[10px]" onClick={() => setQ(c)}>{c}</button>)}
      </div>
      <div className="flex gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()} className="flex-1" placeholder="ask about this incident…" />
        <button onClick={ask} disabled={busy} className="btn btn-primary text-[12px]">{busy ? "…" : "Ask"}</button>
      </div>
      {ans && <div className="mt-2 text-[11.5px] text-[var(--text2)] bg-[#0d1623] rounded-lg p-3 leading-relaxed fade-in">{ans}</div>}
    </div>
  );
}

export default function IncidentsPage() {
  return (
    <Suspense fallback={<div className="base-card p-10 text-center text-[var(--text3)]">loading incidents…</div>}>
      <IncidentsInner />
    </Suspense>
  );
}

"use client";
import { useState } from "react";
import { useStore } from "@/lib/store";
import { post } from "@/lib/api";
import { Bot, Send } from "lucide-react";

export default function Copilot() {
  const { st, dispatch } = useStore();
  const [msgs, setMsgs] = useState<{ role: "u" | "ai"; text: string }[]>([
    { role: "ai", text: "ColdChain copilot online. I answer from live simulation state — no generic replies. Pick an incident or ask about current readings." },
  ]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (text?: string) => {
    const question = (text ?? q).trim();
    if (!question) return;
    setQ("");
    setMsgs(m => [...m, { role: "u", text: question }]);
    setBusy(true);
    try {
      const incidentId = st.selectedIncident ?? st.incidents.find(i => i.status !== "RESOLVED")?.id ?? st.incidents[0]?.id;
      if (!incidentId) {
        setMsgs(m => [...m, { role: "ai", text: "No incident recorded yet. Current state: " +
          (st.sim ? `temp ${st.sim.true_temperature}°C, risk ${st.sim.risk_score}/100, scenario ${st.sim.scenario}, cargo ${st.sim.cargo_health}%, compressor ${st.sim.compressor_on ? "ON" : "OFF"}.` : "no simulation running — start one from Live Simulation.") }]);
      } else {
        const r = await post(`/api/incidents/${incidentId}/ask-ai`, { question });
        setMsgs(m => [...m, { role: "ai", text: r.answer }]);
      }
    } catch (e: any) {
      setMsgs(m => [...m, { role: "ai", text: "error: " + e.message }]);
    } finally { setBusy(false); }
  };

  const chips = [
    "Why is the temperature increasing?",
    "What is the most likely cause?",
    "How much time until critical?",
    "Which action should we take first?",
    "What happens if we do nothing?",
    "Why backup cooling?",
  ];

  return (
    <div className="fade-in max-w-3xl mx-auto">
      <div className="base-card overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border)] flex items-center gap-2">
          <Bot size={15} className="text-[var(--cyan)]" />
          <b className="text-[14px]">AI Copilot</b>
          <span className="badge badge-cyan">context-aware · deterministic</span>
          <span className="text-[10.5px] text-[var(--text3)] ml-auto">
            incident context: #{st.selectedIncident ?? st.incidents[0]?.id ?? "—"}
          </span>
        </div>
        <div className="p-4 space-y-3 h-[52vh] overflow-y-auto scroll-thin">
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === "u" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[78%] rounded-xl px-3.5 py-2.5 text-[12.5px] leading-relaxed ${m.role === "u" ? "bg-[#1e3a5f] text-[#cfe8ff]" : "base-card text-[var(--text2)]"}`}>
                {m.text}
              </div>
            </div>
          ))}
          {busy && <div className="text-[11px] text-[var(--text3)]">thinking…</div>}
        </div>
        <div className="p-3 border-t border-[var(--border)]">
          <div className="flex flex-wrap gap-1 mb-2">
            {chips.map(c => <button key={c} className="chip text-[10px]" onClick={() => ask(c)}>{c}</button>)}
          </div>
          <div className="flex gap-2 items-center">
            <label htmlFor="inc" className="text-[10.5px] text-[var(--text3)]">incident</label>
            <select id="inc" value={st.selectedIncident ?? ""} onChange={e => dispatch({ type: "select_incident", payload: e.target.value ? +e.target.value : null })}>
              <option value="">latest</option>
              {st.incidents.slice(0, 8).map(i => <option key={i.id} value={i.id}>#{i.id} {(i.root_cause || "").replace(/_/g, " ")}</option>)}
            </select>
            <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()}
                   className="flex-1" placeholder="ask about current state, causes, risks, actions…" />
            <button onClick={() => ask()} className="btn btn-primary flex items-center gap-1.5" disabled={busy}>
              <Send size={13} /> Ask
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";
import { useStore } from "@/lib/store";

export default function Settings() {
  const { st, dispatch } = useStore();
  return (
    <div className="fade-in max-w-2xl space-y-4">
      <h2 className="text-xl font-bold headline">Settings</h2>

      <div className="base-card p-4 space-y-3">
        <div className="text-[13px] font-semibold">Appearance</div>
        <div className="flex gap-2">
          {(["dark", "light", "system"] as const).map(t => (
            <button key={t} onClick={() => dispatch({ type: "theme", payload: t })} className={`chip ${st.theme === t ? "on" : ""}`}>{t}</button>
          ))}
        </div>
        <div className="text-[10.5px] text-[var(--text3)]">“system” follows OS preference (dark default for ops use).</div>
      </div>

      <div className="base-card p-4 space-y-3">
        <div className="text-[13px] font-semibold">AI mode</div>
        <div className="text-[12px] text-[var(--text2)]">
          Current: <b className="text-[var(--cyan)]">{st.status?.ai_mode || "…"}</b>
          {st.status?.ai_mode === "DETERMINISTIC" && " — set OPENAI_API_KEY + MODEL_NAME to switch to LLM-backed agents. App is fully functional without a key."}
        </div>
      </div>

      <div className="base-card p-4 space-y-3">
        <div className="text-[13px] font-semibold">Cargo profiles (thresholds)</div>
        {[
          ["Fresh produce", "2–8°C", "high sensitivity"], ["Dairy", "2–6°C", "high"],
          ["Frozen goods", "-22…-15°C", "medium"], ["Pharmaceutical", "2–8°C", "very high (simulated)"],
        ].map(([n, r, s]) => (
          <div key={n} className="flex items-center justify-between text-[12px] border-b border-[var(--border)] py-1.5 last:border-0">
            <b>{n}</b><span className="text-[var(--text2)]">{r}</span><span className="badge badge-cyan">{s}</span>
          </div>
        ))}
        <div className="text-[10.5px] text-[var(--text3)]">Profiles applied at simulation creation; zone thresholds override cargo defaults.</div>
      </div>

      <div className="base-card p-4 space-y-2">
        <div className="text-[13px] font-semibold">Data & persistence</div>
        <div className="text-[11px] text-[var(--text2)] leading-relaxed">
          SQLite by default (zero-setup demo), Postgres via DATABASE_URL switch — simulations, readings, incidents, AI analyses, actions and reports persist across restarts.
          Backend is authoritative: sanitization loop every 1 s of wall time per simulation tick.
        </div>
      </div>
    </div>
  );
}

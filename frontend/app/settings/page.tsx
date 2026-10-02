"use client";
import { useStore } from "@/lib/store";
import { Monitor, Moon, Sun } from "lucide-react";
import type { Theme } from "@/lib/theme";

/**
 * Appearance picker.
 *
 * Each option carries a miniature preview of the real token set rather than a
 * bare label: the two themes differ in surface ORDER (dark = near-black
 * canvas; light = grey canvas with white cards), which a single swatch cannot
 * convey. The preview resolves its own scoped variables in globals.css, so it
 * always depicts the theme it represents no matter which one is active.
 */
const OPTIONS: { id: Theme; label: string; hint: string; icon: typeof Moon }[] = [
  { id: "light", label: "Light", hint: "Grey canvas, white cards — for projectors and daylight", icon: Sun },
  { id: "dark", label: "Dark", hint: "Near-black instrument panel — the ops default", icon: Moon },
  { id: "system", label: "System", hint: "Follow the OS setting, live", icon: Monitor },
];

export default function Settings() {
  const { st, dispatch } = useStore();
  return (
    <div className="fade-in max-w-3xl space-y-4">
      <h1 className="t-hero font-bold headline">Settings</h1>

      <section className="base-card p-4 space-y-3" aria-labelledby="appearance-h">
        <div className="flex items-baseline justify-between gap-3">
          <h2 id="appearance-h" className="t-body font-semibold">Appearance</h2>
          <span className="t-micro text-[var(--text3)]">Saved to this browser</span>
        </div>

        <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Theme">
          {OPTIONS.map(({ id, label, hint, icon: Icon }) => {
            const active = st.theme === id;
            return (
              <button
                key={id}
                role="radio"
                aria-checked={active}
                onClick={() => dispatch({ type: "theme", payload: id })}
                className={`group flex flex-col items-start gap-2 rounded-[var(--r-md)] border p-2.5 text-left transition-colors ${
                  active
                    ? "border-[var(--accent)] bg-[var(--surface-inset)]"
                    : "border-[var(--border)] bg-[var(--surface-raised)] hover:border-[var(--border-strong)]"
                }`}
              >
                <span data-preview={id === "system" ? "dark" : id} aria-hidden className="theme-preview">
                  <span className="theme-preview__nav" />
                  <span className="theme-preview__body">
                    <span className="theme-preview__title" />
                    <span className="theme-preview__cards"><span /><span /></span>
                  </span>
                </span>
                <span className="flex items-center gap-1.5 t-body-sm font-semibold">
                  <Icon size={13} className={active ? "text-[var(--accent)]" : "text-[var(--text-muted)]"} aria-hidden />
                  {label}
                </span>
                <span className="t-body-sm leading-snug text-[var(--text2)]">{hint}</span>
              </button>
            );
          })}
        </div>

        <p className="t-body-sm text-[var(--text3)]">
          Applies instantly on every screen — including the live-map basemap — and survives reload.
          With <b>System</b>, the page follows your OS light/dark setting as it changes.
        </p>
      </section>

      <section className="base-card p-4 space-y-3">
        <h2 className="t-body font-semibold">AI mode</h2>
        <div className="t-body-sm text-[var(--text2)]">
          Current: <b className="text-[var(--cyan)]">{st.status?.ai_mode || "…"}</b>
          {st.status?.ai_mode === "DETERMINISTIC" && " — set OPENAI_API_KEY + MODEL_NAME to switch to LLM-backed agents. App is fully functional without a key."}
        </div>
        <p className="t-body-sm text-[var(--text3)]">
          <b>DETERMINISTIC-AGENTS</b> — the shipped mode — runs every decision through rule-based
          agents with no language model in the path, so identical input always yields an identical
          rescue plan. That reproducibility is what the demo and the viva rely on.
        </p>
      </section>

      <section className="base-card p-4 space-y-3">
        <h2 className="t-body font-semibold">Cargo profiles (thresholds)</h2>
        {[
          ["Fresh produce", "2–8°C", "high sensitivity"], ["Dairy", "2–6°C", "high"],
          ["Frozen goods", "-22…-15°C", "medium"], ["Pharmaceutical", "2–8°C", "very high (simulated)"],
        ].map(([n, r, s]) => (
          <div key={n} className="flex items-center justify-between t-body-sm border-b border-[var(--border)] py-1.5 last:border-0">
            <b>{n}</b><span className="text-[var(--text2)]">{r}</span><span className="badge badge-cyan">{s}</span>
          </div>
        ))}
        <p className="t-body-sm text-[var(--text3)]">Profiles applied at simulation creation; zone thresholds override cargo defaults.</p>
      </section>

      <section className="base-card p-4 space-y-2">
        <h2 className="t-body font-semibold">Data &amp; persistence</h2>
        <p className="t-label text-[var(--text2)] leading-relaxed">
          SQLite by default (zero-setup demo), Postgres via DATABASE_URL switch — simulations, readings, incidents, AI analyses, actions and reports persist across restarts.
          Backend is authoritative: sanitization loop every 1 s of wall time per simulation tick.
        </p>
      </section>
    </div>
  );
}

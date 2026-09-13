"use client";
import { useStore } from "@/lib/store";

export default function Toasts() {
  const { st, dispatch } = useStore();
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 w-80" role="status" aria-live="polite">
      {st.toasts.map(t => (
        <div key={t.id}
             className={`base-card p-3 text-[12px] fade-in-up flex items-start gap-2 border-l-2 ${t.sev === "CRITICAL" ? "border-l-[var(--red)]" : t.sev === "OK" ? "border-l-[var(--green)]" : "border-l-[var(--cyan)]"}`}>
          <span className={`status-dot mt-1.5 ${t.sev === "CRITICAL" ? "red pulse" : t.sev === "OK" ? "" : ""}`}></span>
          <div className="flex-1 text-[var(--text2)]">{t.text}</div>
          <button onClick={() => dispatch({ type: "dismiss_toast", payload: t.id })}
                  className="text-[var(--text3)] hover:text-[var(--text)] aria-label='dismiss'"
                  aria-label="Dismiss">✕</button>
        </div>
      ))}
    </div>
  );
}

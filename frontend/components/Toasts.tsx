"use client";
import { useEffect } from "react";
import { useStore } from "@/lib/store";

const TOAST_TTL_MS = 5200;
const VISIBLE_MAX = 3;

export default function Toasts() {
  const { st, dispatch } = useStore();
  const toasts = st.toasts.slice(-VISIBLE_MAX);
  const key = toasts.map((t) => t.id).join(",");

  useEffect(() => {
    if (!toasts.length) return;
    const timers = toasts.map((t) =>
      setTimeout(() => dispatch({ type: "dismiss_toast", payload: t.id }), TOAST_TTL_MS)
    );
    return () => timers.forEach(clearTimeout);
  }, [key, dispatch]);

  if (!toasts.length) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-64 flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`base-card fade-in-up pointer-events-auto flex items-start gap-2 border-l-2 px-3 py-2.5 t-body-sm ${
            t.sev === "CRITICAL"
              ? "border-l-[var(--critical)]"
              : t.sev === "OK"
              ? "border-l-[var(--nominal)]"
              : "border-l-[var(--ai)]"
          }`}
        >
          <span
            className={`status-dot mt-1.5 ${t.sev === "CRITICAL" ? "red pulse" : t.sev === "OK" ? "" : "amber"}`}
          />
          <div className="flex-1 leading-snug text-[var(--text-secondary)]">{t.text}</div>
          <button
            onClick={() => dispatch({ type: "dismiss_toast", payload: t.id })}
            aria-label="Dismiss notification"
            className="-mr-1 shrink-0 rounded px-1 text-[var(--text-muted)] transition-colors hover:text-[var(--text)]"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

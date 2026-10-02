"use client";
import { useState } from "react";
import { Bell, Check, ChevronDown } from "lucide-react";
import { useStore } from "@/lib/store";

/**
 * Notification centre — the replacement for the old toast stack.
 *
 * Why this is not a popup: the old implementation pushed a card into the
 * bottom-right corner for every telemetry event and dismissed it after 5.2s.
 * Three problems for an operator: cargo transfers fire constantly and buried
 * anything important, the message was gone before it could be read, and it
 * covered the map. Nothing here expires.
 *
 * What changed, concretely:
 *   - persistent      — the full history is retained and scrollable
 *   - non-intrusive   — collapsed to a single counter button; expands on click
 *   - dismissible     — read/clear controls, nothing auto-vanishes
 *   - prioritised     — CRITICAL entries sort above INFO/OK and are marked
 *
 * Severity is not decoration: `ai.approval.requested` and
 * `fleet.incident.created` are the two events that require a human decision,
 * and they are the two that must not be missed.
 */
export default function NotificationCentre() {
  const { st, dispatch } = useStore();
  const [open, setOpen] = useState(false);

  const all = st.notices ?? [];
  const unread = all.filter((n) => !n.read).length;
  const critical = all.filter((n) => !n.read && n.sev === "CRITICAL").length;
  // Severity first, then unread, then newest. Sorting only on `read` was not
  // enough: an incident raised a minute ago could sit below three routine
  // cargo transfers that arrived after it, which is exactly the burying the
  // old toast stack caused.
  const rank = (n: (typeof all)[number]) =>
    (n.sev === "CRITICAL" ? 0 : n.sev === "INFO" ? 1 : 2) * 2 + (n.read ? 1 : 0);
  const ordered = [...all].sort((a, b) => rank(a) - rank(b) || b.id - a.id);

  const dot = critical > 0 ? "bg-[var(--critical)]" : unread > 0 ? "bg-[var(--warning)]" : "bg-[var(--nominal)]";

  return (
    <div className="fixed bottom-4 right-4 z-50 w-[min(22rem,calc(100vw-2rem))]">
      <div className="flex flex-col items-end gap-2">
        {open && (
          <div
            className="base-card fade-in flex max-h-[26rem] w-full flex-col overflow-hidden"
            role="log"
            aria-label="Activity centre"
          >
            <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
              <span className="t-body font-semibold flex items-center gap-2">
                <Bell size={13} aria-hidden />
                Activity
                {unread > 0 && <span className="badge badge-amber">{unread} new</span>}
              </span>
              <div className="flex items-center gap-1">
                {unread > 0 && (
                  <button
                    onClick={() => dispatch({ type: "ack_notice", payload: "all" })}
                    className="chip"
                    title="Mark all as read"
                  >
                    <Check size={11} aria-hidden /> Read all
                  </button>
                )}
                <button
                  onClick={() => dispatch({ type: "clear_notices" })}
                  className="chip"
                  title="Dismiss read items"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="scroll-thin flex-1 overflow-y-auto">
              {ordered.length === 0 ? (
                <p className="t-body-sm text-[var(--text3)] px-3 py-4">
                  Nothing yet. Incidents, AI decisions, approvals and transfers appear here
                  and stay until you clear them.
                </p>
              ) : (
                <ul>
                  {ordered.map((n) => (
                    <li key={n.id}>
                      <button
                        onClick={() => dispatch({ type: "ack_notice", payload: n.id })}
                        className={`flex w-full items-start gap-2 border-l-2 px-3 py-2 text-left transition-colors hover:bg-[var(--surface-raised)] ${
                          n.sev === "CRITICAL"
                            ? "border-l-[var(--critical)]"
                            : n.sev === "OK"
                            ? "border-l-[var(--nominal)]"
                            : "border-l-[var(--ai)]"
                        } ${n.read ? "opacity-60" : ""}`}
                      >
                        <span
                          className={`status-dot mt-1.5 shrink-0 ${
                            n.sev === "CRITICAL" ? "red pulse" : n.sev === "OK" ? "" : "amber"
                          }`}
                          aria-hidden
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block t-body-sm leading-snug text-[var(--text-secondary)]">
                            {n.text}
                          </span>
                          <span className="mt-0.5 block font-mono text-[10px] text-[var(--text-dim)]">
                            {n.source} · {new Date(n.at).toLocaleTimeString()}
                          </span>
                        </span>
                        {!n.read && <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent)]" aria-label="unread" />}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={`Activity centre${unread ? `, ${unread} unread` : ""}`}
          className="base-card pointer-events-auto flex items-center gap-2 px-3 py-2"
          title="Activity centre — incidents, AI decisions, approvals"
        >
          <span className={`status-dot ${dot} ${unread > 0 ? "pulse" : ""}`} aria-hidden />
          <span className="t-body-sm font-semibold">Activity</span>
          {unread > 0 && (
            <span className="rounded-full bg-[var(--surface-inset)] px-1.5 t-micro font-bold leading-none text-[var(--text)]">
              {unread}
            </span>
          )}
          <ChevronDown size={12} className={open ? "rotate-180 transition-transform" : "transition-transform"} aria-hidden />
        </button>
      </div>
    </div>
  );
}

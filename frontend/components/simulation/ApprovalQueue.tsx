"use client";
import { useCallback, useEffect, useState } from "react";
import { Check, ShieldQuestion, X } from "lucide-react";
import { api, post } from "@/lib/api";

/**
 * Human-in-the-loop approval queue.
 *
 * The AI recommends; a person decides. Nothing in this panel executes a rescue
 * on its own — the buttons post a decision and the backend applies it (or
 * records the rejection).
 *
 * Rendered as a persistent card rather than a popup: a decision that requires
 * judgement should stay on screen until it is made, not disappear on a timer.
 */

type Proposal = {
  key: string;
  vehicle_id: string;
  vehicle_name: string;
  incident_id: number | null;
  decision: string;
  target: string;
  current_destination: string;
  reason: string;
  confidence: number;
  score: number | null;
  scored: Record<string, any>;
  candidates: any[];
  cargo_type: string;
  load_units: number;
  temperature: number;
  cargo_health: number;
  raised_at_sim_minute: number;
  status: string;
};

type Payload = {
  require_approval: boolean;
  auto_approve_timeout_sim_min: number;
  pending: Proposal[];
  pending_count: number;
  resolved: Proposal[];
};

export default function ApprovalQueue({ compact = false }: { compact?: boolean }) {
  const [data, setData] = useState<Payload | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Payload>("/api/fleet/approvals").then(setData).catch(() => {});
  }, []);

  useEffect(() => {
    load();
    // The queue changes on the server when an incident fires, which is driven by
    // the WebSocket rather than by anything on this page. Polling at 3s is the
    // simplest thing that cannot miss a decision; the store already polls
    // /api/fleet/state on the same cadence.
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  const decide = async (key: string, approve: boolean) => {
    setBusy(key);
    setErr(null);
    try {
      await post(`/api/fleet/approvals/${encodeURIComponent(key)}`, {
        approve,
        note: approve ? "approved by operator" : "rejected by operator",
      });
      load();
    } catch (e: any) {
      setErr(String(e?.message ?? e).slice(0, 160));
    } finally {
      setBusy(null);
    }
  };

  const setMode = async (on: boolean) => {
    await post("/api/fleet/approvals/mode", { require_approval: on }).catch(() => {});
    load();
  };

  if (!data) return null;
  const pending = data.pending ?? [];

  return (
    <section className="base-card p-4 space-y-3" aria-labelledby="approvals-h">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id="approvals-h" className="t-body font-semibold flex items-center gap-2">
            <ShieldQuestion size={14} className="text-[var(--accent)]" aria-hidden />
            AI recommendations awaiting your decision
          </h2>
          <p className="t-body-sm text-[var(--text3)] mt-0.5">
            The agent proposes. Nothing changes until you approve.
          </p>
        </div>
        <label className="flex items-center gap-1.5 t-micro text-[var(--text3)] whitespace-nowrap">
          <input
            type="checkbox"
            checked={data.require_approval}
            onChange={(e) => setMode(e.target.checked)}
            aria-label="Require human approval"
          />
          gate on
        </label>
      </div>

      {err && <p role="alert" className="t-body-sm text-[var(--critical)]">{err}</p>}

      {!data.require_approval && (
        <p className="t-body-sm text-[var(--warning)]">
          Gate is off — diverts apply automatically, as in the original autonomous demo.
        </p>
      )}

      {pending.length === 0 ? (
        <p className="t-body-sm text-[var(--text3)]">
          {data.require_approval
            ? "Nothing waiting. A recommendation appears here when a truck needs a rescue decision."
            : "Gate disabled."}
        </p>
      ) : (
        <ul className="space-y-2">
          {pending.map((p) => (
            <li
              key={p.key}
              className={
                p.escalated
                  ? "rounded-[var(--r-md)] border-2 border-[var(--critical)] bg-[var(--surface-inset)] p-3 space-y-2"
                  : "rounded-[var(--r-md)] border border-[var(--warning)] bg-[var(--surface-inset)] p-3 space-y-2"
              }
            >
              {p.escalated && (
                <div className="flex items-center gap-2 text-[var(--critical)] t-body-sm font-semibold">
                  <span aria-hidden>▲</span>
                  ESCALATED BY AGENT — no operator response within the grace period
                  at sim-min {p.escalated_at_sim_minute}. Still awaiting your decision.
                </div>
              )}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="t-body-sm font-semibold">
                    Divert {p.vehicle_name} → {p.target}
                  </p>
                  <p className="t-body-sm text-[var(--text3)]">
                    currently heading to {p.current_destination} · {p.cargo_type} · {p.load_units}u ·{" "}
                    {p.temperature}°C · cargo {p.cargo_health}%
                  </p>
                </div>
                {p.score != null && (
                  <span className="badge badge-cyan shrink-0">score {Math.round(p.score)}</span>
                )}
              </div>

              <p className="t-body-sm text-[var(--text2)]">{p.reason}</p>

              {p.candidates?.length > 0 && (
                <details className="t-body-sm" open>
                  <summary className="cursor-pointer text-[var(--text3)]">
                    {p.candidates.length} alternative destination(s) considered, ranked by score
                  </summary>
                  <ul className="mt-1 space-y-0.5">
                    {p.candidates.map((c: any, i: number) => (
                      <li key={i} className="text-[var(--text3)]">
                        {c.id ?? c.facility_id ?? "?"} —{" "}
                        {c.reason ?? c.eta_total_min != null ? `${c.eta_total_min} min` : ""}
                        {c.score != null ? ` · score ${Math.round(c.score)}` : ""}
                        {/* Requirement 16 asks the agent to weigh cost as well as
                            time and proximity. Cost was computed server-side but
                            never shown, so the trade-off was invisible. */}
                        {c.cost_inr != null ? ` · Rs ${Number(c.cost_inr).toLocaleString("en-IN")}` : ""}
                      </li>
                    ))}
                  </ul>
                </details>
              )}

              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => decide(p.key, true)}
                  disabled={busy === p.key}
                  className="btn btn-green flex items-center gap-1.5"
                >
                  <Check size={13} aria-hidden /> Approve
                </button>
                <button
                  onClick={() => decide(p.key, false)}
                  disabled={busy === p.key}
                  className="btn flex items-center gap-1.5"
                >
                  <X size={13} aria-hidden /> Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {!compact && (data.resolved ?? []).length > 0 && (
        <details className="t-body-sm">
          <summary className="cursor-pointer text-[var(--text3)]">
            Recent decisions ({(data.resolved ?? []).length})
          </summary>
          <ul className="mt-1 space-y-0.5">
            {(data.resolved ?? []).slice().reverse().map((r) => (
              <li key={r.key} className="text-[var(--text3)]">
                <span className={r.status === "APPROVED" ? "text-[var(--nominal)]" : "text-[var(--warning)]"}>
                  {r.status}
                </span>{" "}
                · {r.vehicle_name} → {r.target}
                {r.note ? ` · ${r.note}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { post, api } from "@/lib/api";

const CMDS: { key: string; label: string; hint: string; run: (args: { router: any; dispatch: any; st: any }) => Promise<void> }[] = [
  { key: "sim-start", label: "Start simulation", hint: "demo launch", run: async ({ router }) => { await post("/api/demo/launch?autopilot=true&failure=compressor_failure&after_ticks=10"); router.push("/dashboard"); } },
  { key: "demo", label: "Launch demo mode", hint: "seed + autopilot", run: async ({ router }) => { await post("/api/demo/launch?autopilot=true&failure=compressor_failure&after_ticks=8"); router.push("/dashboard"); } },
  { key: "compressor", label: "Trigger compressor failure", hint: "inject into latest sim", run: async ({ st }) => { const sid = st.sim?.simulation_id; if (sid) await post(`/api/simulations/${sid}/failure/compressor_failure`); } },
  { key: "power", label: "Trigger power failure", hint: "inject into latest sim", run: async ({ st }) => { const sid = st.sim?.simulation_id; if (sid) await post(`/api/simulations/${sid}/failure/power_failure`); } },
  { key: "resolve", label: "Execute first recovery action", hint: "on latest incident", run: async () => { const incs = await api("/api/incidents"); const i = incs?.[0]?.id; const d = i ? await api(`/api/incidents/${i}`) : null; const a = d?.actions?.find((x: any) => x.action !== "monitor" && x.status === "PENDING"); if (i && a) await post(`/api/incidents/${i}/action`, { action: a.action }); } },
  { key: "incidents", label: "Open incident center", hint: "/incidents", run: async ({ router }) => router.push("/incidents") },
  { key: "copilot", label: "Open AI Copilot", hint: "/copilot", run: async ({ router }) => router.push("/copilot") },
  { key: "reports", label: "Open reports", hint: "/reports", run: async ({ router }) => router.push("/reports") },
  { key: "analytics", label: "Open analytics", hint: "/analytics", run: async ({ router }) => router.push("/analytics") },
  { key: "sim-ctrl", label: "Open simulation controls", hint: "/simulation", run: async ({ router }) => router.push("/simulation") },
  { key: "theme", label: "Toggle dark mode", hint: "dark/light", run: async ({ dispatch, st }) => dispatch({ type: "theme", payload: st.theme === "dark" ? "light" : "dark" }) },
];

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const { st, dispatch } = useStore();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [cursor, setCursor] = useState(0);
  const items = CMDS.filter(c => c.label.toLowerCase().includes(q.toLowerCase()));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") setCursor(c => Math.min(items.length - 1, c + 1));
      if (e.key === "ArrowUp") setCursor(c => Math.max(0, c - 1));
      if (e.key === "Enter" && items[cursor]) { items[cursor].run({ router, dispatch, st }); onClose(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, cursor]);

  return (
    <div className="fixed inset-0 z-50 bg-black/55 grid place-items-start pt-28 px-4" role="dialog" aria-modal="true"
         onClick={onClose}>
      <div className="base-card w-full max-w-xl p-2 fade-in" onClick={e => e.stopPropagation()}>
        <input autoFocus value={q} onChange={e => { setQ(e.target.value); setCursor(0); }}
               placeholder="Type a command — start, inject, resolve, copilot, reports…"
               aria-label="Command search"
               className="w-full mb-2 text-[13px]" />
        <div className="max-h-72 overflow-y-auto">
          {items.map((c, i) => (
            <button key={c.key}
                    className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-3 text-[12.5px] ${i === cursor ? "bg-[#142131]" : ""}`}
                    onMouseEnter={() => setCursor(i)}
                    onClick={() => { c.run({ router, dispatch, st }); onClose(); }}>
              <span className="chip text-[9px]">{c.hint}</span>
              {c.label}
            </button>
          ))}
          {!items.length && <div className="text-[12px] text-[var(--text3)] p-4">no match</div>}
        </div>
      </div>
    </div>
  );
}

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, Boxes, Bot, ClipboardList, Container, Cpu, Droplets, FlaskConical, Home, Layers, Map, Settings, Siren } from "lucide-react";
import { useStore } from "@/lib/store";
import Toasts from "./Toasts";
import { CommandPalette } from "./CommandPalette";
import { useEffect, useState } from "react";

const NAV = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: Activity },
  { href: "/live-map", label: "Live Map", icon: Map },
  { href: "/simulation", label: "Live Simulation", icon: FlaskConical },
  { href: "/twin", label: "Digital Twin", icon: Map },
  { href: "/shipments", label: "Shipments", icon: Container },
  { href: "/incidents", label: "Incidents", icon: Siren },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/copilot", label: "AI Copilot", icon: Bot },
  { href: "/reports", label: "Reports", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { st } = useStore();
  const [openCmd, setOpenCmd] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpenCmd(v => !v); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const acks = st.dashboard;
  const running = st.sim && st.status?.simulations_running > 0;

  return (
    <div className="min-h-screen flex">
      {/* SIDEBAR */}
      <aside className="w-56 shrink-0 border-r border-[var(--border)] p-4 hidden md:flex flex-col gap-1 bg-[#0b1018]"
             aria-label="Main navigation">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1e3a5f] to-[#0d1623] border border-[#2b5b8b] grid place-items-center">
            <Droplets size={15} className="text-[#7ec8ff]" />
          </div>
          <div>
            <div className="text-[13.5px] font-bold headline leading-tight">COLDCHAIN</div>
            <div className="text-[9.5px] text-[var(--text3)] tracking-widest">RESCUE · OPS CENTER</div>
          </div>
        </div>
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href}
                className={`route flex items-center gap-2.5 px-3 py-2 rounded-lg transition-colors hover:bg-[#10192a] ${path === href ? "active bg-[#10192a]" : ""}`}
                aria-current={path === href ? "page" : undefined}>
            <Icon size={14} /> {label}
          </Link>
        ))}
        <div className="mt-auto pt-4 border-t border-[var(--border)]">
          <button onClick={() => setOpenCmd(true)} className="chip w-full justify-center flex items-center gap-1.5 text-[11px]">
            ⌘K Command palette
          </button>
          <div className="text-[10px] text-[var(--text3)] mt-3 leading-relaxed">
            SIMULATION ENVIRONMENT<br/>backend is authoritative
          </div>
        </div>
      </aside>

      {/* MAIN */}
      <div className="flex-1 min-w-0 flex flex-col">
        <header className="border-b border-[var(--border)] px-5 py-2.5 flex items-center gap-4 bg-[#0b1018cc] backdrop-blur">
          <div className="text-[13px] font-semibold headline flex items-center gap-2">
            <Activity size={14} className="text-[var(--accent)]" />
            ColdChain Rescue
            <span className="badge badge-cyan">SIMULATION ENVIRONMENT</span>
          </div>
          <div className="flex-1" aria-hidden />
          <StatusItem label="AI" ok={st.status?.ai_mode != null} note={st.status?.ai_mode || "..."} />
          <StatusItem label="DB" ok={st.status?.database === "CONNECTED"} note={st.status?.database || "..."} />
          <StatusItem label="WS" ok={st.connected} note={st.connected ? "LIVE" : "RECONNECTING"} />
          <StatusItem label="SIM" ok={st.status?.simulations_running > 0 || st.sim != null}
                    note={running ? `${st.sim!.simulation_id} @tick ${st.sim!.tick}` : "idle"} />
          <span className={`badge ${st.status?.system === "OPERATIONAL" ? "badge-green" : "badge-amber"}`}>
            {st.status?.system || "BOOTING"}
          </span>
        </header>

        <main className="flex-1 p-5 md:p-6 fade-in">
          {children}
        </main>
      </div>
      <Toasts />
      {openCmd && <CommandPalette onClose={() => setOpenCmd(false)} />}
    </div>
  );
}

function StatusItem({ label, ok, note }: { label: string; ok: boolean; note: string }) {
  return (
    <span className="hidden sm:flex items-center gap-1.5 text-[10.5px] text-[var(--text2)]">
      <span className={`status-dot ${ok ? "" : "red"} ${ok ? "pulse" : ""}`}></span>
      {label} <span className={ok ? "text-[var(--green)]" : "text-[var(--red)]"}>{note}</span>
    </span>
  );
}

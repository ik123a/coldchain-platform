"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Activity, BarChart3, Boxes, Bot, ChevronLeft, ChevronRight, 
  ClipboardList, Container, Cpu, Droplets, FastForward, FlaskConical, 
  Home, Layers, List, Map, Settings, Siren, Warehouse, Search, Sparkles
} from "lucide-react";
import { useStore } from "@/lib/store";
import Toasts from "./Toasts";
import { CommandPalette } from "./CommandPalette";

// Strict Section 8 Navigation Structure
const PRIMARY_NAV = [
  { href: "/dashboard", label: "Dashboard", icon: Activity },
  { href: "/live-map", label: "Live Map", icon: Map },
  { href: "/shipments-live", label: "Fleet", icon: List },
  { href: "/shipments", label: "Shipments", icon: Container },
  { href: "/live-map?filter=WAREHOUSES", label: "Warehouses", icon: Warehouse },
  { href: "/incidents", label: "Incidents", icon: Siren, badgeKey: "incidents" },
  { href: "/copilot", label: "AI Command", icon: Bot },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/simulation", label: "Simulation", icon: FlaskConical },
  { href: "/simulation?tab=replay", label: "Replay", icon: FastForward },
  { href: "/reports", label: "Reports", icon: ClipboardList },
  { href: "/settings", label: "Settings", icon: Settings },
];

const SECONDARY_NAV = [
  { href: "/design-references", label: "Media Library", icon: Layers },
  { href: "/design-reference-board", label: "Design Board", icon: Boxes },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { st } = useStore();
  const [openCmd, setOpenCmd] = useState(false);
  const [collapsed, setCollapsed] = useState(true);

  // Keyboard shortcut for Cmd+K command palette
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpenCmd((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openIncidentsCount = st.incidents?.filter(i => i.status !== "RESOLVED")?.length || 0;
  const isMapRoute = path === "/live-map" || path === "/dashboard";

  return (
    <div className="min-h-screen flex bg-[#080A0F] text-slate-100 selection:bg-cyan-500/20 font-sans">
      {/* 1. SLIM COLLAPSIBLE ICON RAIL (SECTION 8) */}
      <aside 
        className={`shrink-0 border-r border-[#1E2638] bg-[#0A0D14] flex flex-col transition-all duration-200 z-40 select-none ${
          collapsed ? "w-14" : "w-56"
        }`}
        aria-label="Application Navigation">
        
        {/* Brand Anchor */}
        <div className="h-12 border-b border-[#1E2638] flex items-center justify-between px-3">
          <Link href="/" className="flex items-center gap-2.5 overflow-hidden group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1E3A5F] to-[#0D1623] border border-[#2B5B8B] grid place-items-center shrink-0 group-hover:border-cyan-400 transition-colors">
              <Droplets size={15} className="text-cyan-400" />
            </div>
            {!collapsed && (
              <div className="min-w-0 transition-opacity duration-200">
                <div className="text-[12px] font-bold tracking-tight text-white leading-tight">COLDCHAIN</div>
                <div className="text-[9px] text-slate-400 tracking-wider">RESCUE OPS</div>
              </div>
            )}
          </Link>
          <button
            onClick={() => setCollapsed(v => !v)}
            title={collapsed ? "Expand navigation" : "Collapse navigation"}
            className="hidden md:grid place-items-center w-6 h-6 rounded text-slate-400 hover:text-white hover:bg-[#141B26] transition-colors">
            {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        </div>

        {/* Primary Navigation Items */}
        <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto scroll-thin">
          {PRIMARY_NAV.map(({ href, label, icon: Icon, badgeKey }) => {
            const isActive = path === href || (href.includes("?") && path === href.split("?")[0]);
            const badgeCount = badgeKey === "incidents" ? openIncidentsCount : 0;
            return (
              <Link
                key={href}
                href={href}
                title={collapsed ? label : undefined}
                className={`relative flex items-center gap-3 px-2.5 py-2 rounded-lg text-xs font-medium transition-all group ${
                  isActive 
                    ? "bg-[#141B26] text-cyan-400 border border-[#2B3A52]/60 shadow-sm" 
                    : "text-slate-400 hover:text-slate-200 hover:bg-[#101622]"
                }`}>
                <Icon size={16} className={`shrink-0 ${isActive ? "text-cyan-400" : "text-slate-400 group-hover:text-slate-200"}`} />
                {!collapsed && <span className="truncate">{label}</span>}
                {badgeCount > 0 && (
                  <span className={`ml-auto rounded-full text-[9px] font-mono font-bold grid place-items-center shrink-0 bg-rose-950 text-rose-400 border border-rose-800 ${
                    collapsed ? "absolute top-1 right-1 w-3.5 h-3.5" : "px-1.5 py-0.2"
                  }`}>
                    {badgeCount}
                  </span>
                )}
              </Link>
            );
          })}

          <div className="pt-2 my-2 border-t border-[#1E2638]/70" />

          {/* Secondary Visual Reference Links */}
          {SECONDARY_NAV.map(({ href, label, icon: Icon }) => {
            const isActive = path === href;
            return (
              <Link
                key={href}
                href={href}
                title={collapsed ? label : undefined}
                className={`flex items-center gap-3 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
                  isActive 
                    ? "bg-[#141B26] text-white" 
                    : "text-slate-400 hover:text-slate-300 hover:bg-[#101622]"
                }`}>
                <Icon size={14} className="shrink-0 text-slate-400" />
                {!collapsed && <span className="truncate">{label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Command Palette Trigger & Footer */}
        <div className="p-2 border-t border-[#1E2638] bg-[#0A0D14]">
          <button
            onClick={() => setOpenCmd(true)}
            title="Command Palette (⌘K)"
            className={`w-full flex items-center justify-center gap-2 py-1.5 px-2 rounded-lg bg-[#141B26] hover:bg-[#1C2638] text-slate-400 hover:text-white border border-[#1E2638] transition-colors text-xs`}>
            <Search size={13} className="shrink-0" />
            {!collapsed && <span className="font-mono text-[10px]">⌘K Search</span>}
          </button>
        </div>
      </aside>

      {/* 2. MAIN WORKSPACE CANVAS */}
      <div className="flex-1 min-w-0 flex flex-col h-screen overflow-hidden">
        {/* Sleek Top Operations Bar */}
        <header className="h-11 shrink-0 border-b border-[#1E2638] px-4 flex items-center justify-between bg-[#0A0D14]/90 backdrop-blur z-30 select-none">
          <div className="flex items-center gap-3">
            <Link href="/" className="text-xs font-semibold tracking-tight text-white flex items-center gap-2">
              <span>ColdChain Rescue</span>
              <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/50 px-2 py-0.5 rounded-full">
                LIVE AUTONOMOUS TWIN
              </span>
            </Link>
          </div>

          <div className="flex items-center gap-4 font-mono text-[11px]">
            <StatusIndicator label="AI ENGINE" value={st.status?.ai_mode || "LLM"} ok={st.status?.ai_mode != null} />
            <StatusIndicator label="DB" value={st.status?.database || "ONLINE"} ok={st.status?.database === "CONNECTED"} />
            <StatusIndicator label="WS" value={st.connected ? "STREAMING" : "CONNECTING"} ok={st.connected} />
            
            <div className="hidden lg:flex items-center gap-1.5 pl-2 border-l border-[#1E2638]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-400">FLEET:</span>
              <span className="text-white font-bold">{st.fleetVehicles?.length || 14} TWINS</span>
            </div>

            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
              st.status?.system === "OPERATIONAL" 
                ? "bg-emerald-950 text-emerald-400 border border-emerald-800" 
                : "bg-amber-950 text-amber-400 border border-amber-800"
            }`}>
              {st.status?.system || "OPERATIONAL"}
            </span>
          </div>
        </header>

        {/* Viewport: Full-bleed for map routes, padded for standard views */}
        <main className={`flex-1 min-w-0 overflow-y-auto ${isMapRoute ? "p-0 overflow-hidden" : "p-4 md:p-6"}`}>
          {children}
        </main>
      </div>

      <Toasts />
      {openCmd && <CommandPalette onClose={() => setOpenCmd(false)} />}
    </div>
  );
}

function StatusIndicator({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="hidden sm:flex items-center gap-1.5 text-slate-400">
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-rose-500"}`}></span>
      <span className="text-slate-400 text-[10px]">{label}:</span>
      <span className={ok ? "text-slate-200" : "text-rose-400"}>{value}</span>
    </div>
  );
}

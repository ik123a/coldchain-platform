"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity, BarChart3, Bot, ChevronLeft, ChevronRight,
  ClipboardList, Container, Droplets, FastForward, FlaskConical,
  List, Map, Settings, Siren, Warehouse, Search
} from "lucide-react";
import { StatusBeacon } from "./ui/status-beacon";
import { useStore } from "@/lib/store";
import Toasts from "./Toasts";
import { CommandPalette } from "./CommandPalette";

const NAV_GROUPS = [
  {
    label: "Operate",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: Activity },
      { href: "/live-map", label: "Live Map", icon: Map },
      { href: "/shipments-live", label: "Fleet", icon: List },
      { href: "/simulation", label: "Simulation", icon: FlaskConical },
    ],
  },
  {
    label: "Monitor",
    items: [
      { href: "/shipments", label: "Shipments", icon: Container },
      { href: "/live-map?filter=WAREHOUSES", label: "Warehouses", icon: Warehouse },
      { href: "/incidents", label: "Incidents", icon: Siren, badgeKey: "incidents" },
      { href: "/twin", label: "Digital Twin", icon: Droplets },
    ],
  },
  {
    label: "Analyze",
    items: [
      { href: "/copilot", label: "AI Command", icon: Bot },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/simulation?tab=replay", label: "Replay", icon: FastForward },
      { href: "/reports", label: "Reports", icon: ClipboardList },
    ],
  },
  {
    label: "Configure",
    items: [{ href: "/settings", label: "Settings", icon: Settings }],
  },
];

const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

export default function Layout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { st } = useStore();
  const [openCmd, setOpenCmd] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

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

  const openIncidentsCount = st.incidents?.filter((i) => i.status !== "RESOLVED").length || 0;
  const isMapRoute = path === "/live-map" || path === "/dashboard";
  const fleetCount = st.fleetVehicles?.length ?? 0;

  return (
    <div className="flex min-h-screen bg-[var(--canvas)] text-[var(--text)]">
      <aside
        className={`z-40 flex shrink-0 select-none flex-col border-r border-[var(--border)] bg-[var(--surface-subtle)] transition-[width] duration-200 ${
          collapsed ? "w-[60px]" : "w-[232px]"
        }`}
        aria-label="Application Navigation"
      >
        <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-3">
          <Link href="/" className="group flex min-w-0 items-center gap-2.5 overflow-hidden">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[10px] border border-[var(--border-accent)] bg-gradient-to-br from-[#1E3A5F] to-[#0D1623] transition-colors group-hover:border-cyan-400">
              <Droplets size={15} className="text-cyan-400" />
            </span>
            {!collapsed && (
              <span className="min-w-0 leading-tight">
                <span className="block truncate t-body-sm font-bold tracking-tight text-white">COLDCHAIN</span>
                <span className="block truncate t-micro tracking-wider text-[var(--text-muted)]">RESCUE OPS</span>
              </span>
            )}
          </Link>
          <button
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            className="hidden h-6 w-6 shrink-0 place-items-center rounded text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-card)] hover:text-white md:grid"
          >
            {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        </div>

        <nav className="scroll-thin flex-1 overflow-y-auto px-2 py-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-4 last:mb-0">
              {!collapsed ? (
                <p className="mb-1.5 px-2.5 t-micro font-semibold uppercase tracking-[0.12em] text-[var(--text-dim)]">
                  {group.label}
                </p>
              ) : (
                <div className="mx-2.5 mb-2 h-px bg-[var(--border)]" />
              )}
              <ul className="space-y-0.5">
                {group.items.map(({ href, label, icon: Icon, badgeKey }) => {
                  const [base, query] = href.split("?");
                  const isActive = path === base && !query;
                  const badgeCount = badgeKey === "incidents" ? openIncidentsCount : 0;
                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        title={collapsed ? label : undefined}
                        aria-current={isActive ? "page" : undefined}
                        className={`group relative flex items-center gap-3 rounded-lg border px-2.5 py-2 t-body-sm font-medium transition-colors ${
                          isActive
                            ? "border-[var(--border-strong)] bg-[var(--surface-card)] text-cyan-400"
                            : "border-transparent text-[var(--text-secondary)] hover:bg-[var(--surface-raised)] hover:text-[var(--text)]"
                        }`}
                      >
                        <Icon
                          size={16}
                          className={`shrink-0 ${isActive ? "text-cyan-400" : "text-[var(--text-muted)] group-hover:text-[var(--text)]"}`}
                        />
                        {!collapsed && <span className="truncate">{label}</span>}
                        {badgeCount > 0 &&
                          (collapsed ? (
                            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--critical)]" />
                          ) : (
                            <span className="ml-auto shrink-0 rounded-full border border-rose-800 bg-rose-950 px-1.5 py-0.5 font-mono t-micro font-bold leading-none text-rose-400">
                              {badgeCount}
                            </span>
                          ))}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-[var(--border)] p-2">
          <button
            onClick={() => setOpenCmd(true)}
            title="Command Palette"
            className="press-effect flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-card)] px-2 py-1.5 t-body-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--surface-elevated)] hover:text-white"
          >
            <Search size={13} className="shrink-0" />
            {!collapsed && <span className="font-mono t-micro">⌘K Search</span>}
          </button>
        </div>
      </aside>

      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-30 flex h-11 shrink-0 select-none items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface-subtle)]/90 px-4 backdrop-blur">
          <Link href="/" className="flex min-w-0 items-center gap-2 t-body-sm font-semibold tracking-tight text-white">
            <span className="truncate">ColdChain Rescue</span>
            <span className="shrink-0 rounded-full border border-cyan-800/50 bg-cyan-950/60 px-2 py-0.5 font-mono t-micro text-cyan-400">
              LIVE AUTONOMOUS TWIN
            </span>
          </Link>

          <div className="flex shrink-0 items-center gap-4 font-mono t-label">
            <StatusIndicator label="AI ENGINE" value={st.status?.ai_mode || "LLM"} ok={st.status?.ai_mode != null} />
            <StatusIndicator label="DB" value={st.status?.database || "ONLINE"} ok={st.status?.database === "CONNECTED"} />
            <StatusIndicator label="WS" value={st.connected ? "STREAMING" : "CONNECTING"} ok={st.connected} />

            <div className="hidden items-center gap-1.5 border-l border-[var(--border)] pl-2 lg:flex">
              <StatusBeacon status="online" size="sm" />
              <span className="text-[var(--text-muted)]">FLEET:</span>
              <span className="font-bold text-white">{fleetCount} TWINS</span>
            </div>

            <span
              className={`rounded border px-2 py-0.5 t-micro font-bold ${
                st.status?.system === "OPERATIONAL"
                  ? "border-emerald-800 bg-emerald-950 text-emerald-400"
                  : "border-amber-800 bg-amber-950 text-amber-400"
              }`}
            >
              {st.status?.system || "OPERATIONAL"}
            </span>
          </div>
        </header>

        <main
          className={`min-w-0 flex-1 ${isMapRoute ? "flex h-full flex-col overflow-hidden p-0" : "overflow-y-auto p-4 md:p-6"}`}
        >
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
    <div className="hidden items-center gap-1.5 sm:flex">
      <span
        className={`h-1.5 w-1.5 rounded-full ${ok ? "breathe bg-emerald-400" : "animate-pulse bg-rose-500"}`}
        style={ok ? ({ "--glow-color": "rgba(16,185,129,0.4)" } as React.CSSProperties) : undefined}
      />
      <span className="t-micro text-[var(--text-muted)]">{label}:</span>
      <span className={ok ? "text-slate-200" : "text-rose-400"}>{value}</span>
    </div>
  );
}

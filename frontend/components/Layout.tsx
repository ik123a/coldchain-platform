"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity, BarChart3, Bot, ChevronLeft, ChevronRight,
  ClipboardList, Container, Droplets, FastForward, FlaskConical,
  List, Map, Moon, Settings, Siren, Sun, Warehouse, Search
} from "lucide-react";
import { StatusBeacon } from "./ui/status-beacon";
import { useStore } from "@/lib/store";
import { resolveTheme } from "@/lib/theme";
import Toasts from "./Toasts";
import { CommandPalette } from "./CommandPalette";

const NAV_GROUPS = [
  {
    n: "01",
    label: "Operate",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: Activity },
      { href: "/live-map", label: "Live Map", icon: Map },
      { href: "/shipments-live", label: "Fleet", icon: List },
      { href: "/simulation", label: "Simulation", icon: FlaskConical },
    ],
  },
  {
    n: "02",
    label: "Monitor",
    items: [
      { href: "/shipments", label: "Shipments", icon: Container },
      { href: "/live-map?filter=WAREHOUSES", label: "Warehouses", icon: Warehouse },
      { href: "/incidents", label: "Incidents", icon: Siren, badgeKey: "incidents" },
      { href: "/twin", label: "Digital Twin", icon: Droplets },
    ],
  },
  {
    n: "03",
    label: "Analyze",
    items: [
      { href: "/copilot", label: "AI Command", icon: Bot },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/simulation?tab=replay", label: "Replay", icon: FastForward },
      { href: "/reports", label: "Reports", icon: ClipboardList },
    ],
  },
  {
    n: "04",
    label: "Configure",
    items: [{ href: "/settings", label: "Settings", icon: Settings }],
  },
];

const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

export default function Layout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { st, dispatch } = useStore();
  const [openCmd, setOpenCmd] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // One-click flip for demos and projectors. Under "system" the toggle
  // pins the OPPOSITE of what is currently showing, which is the least
  // surprising behaviour: the button always means "show me the other one".
  const isLight = resolveTheme(st.theme) === "light";
  const toggleTheme = () =>
    dispatch({ type: "theme", payload: isLight ? "dark" : "light" });

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
  const systemOk = st.status?.system === "OPERATIONAL";
  const dbOk = st.status?.database === "CONNECTED";
  const wsOk = !!st.connected;

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
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[10px] border border-[var(--border-accent)] bg-gradient-to-br from-[#1E3A5F] to-[#0D1623] transition-colors group-hover:border-[var(--accent)]">
              <Droplets size={15} className="text-[var(--accent)]" />
            </span>
            {!collapsed && (
              <span className="min-w-0 leading-tight">
                <span className="block truncate t-body-sm font-bold tracking-tight text-[var(--text)]">COLDCHAIN</span>
                <span className="block truncate t-micro tracking-wider text-[var(--text-muted)]">RESCUE OPS</span>
              </span>
            )}
          </Link>
          <button
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            className="hidden h-6 w-6 min-h-6 min-w-6 shrink-0 place-items-center rounded text-[var(--text-muted)] transition-colors hover:bg-[var(--surface-card)] hover:text-[var(--text)] md:grid"
          >
            {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
          </button>
        </div>

        <nav className="scroll-thin flex-1 overflow-y-auto px-2 py-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-4 last:mb-0">
              {!collapsed ? (
                <p className="ops-eyebrow mb-2 px-2">
                  <span className="ops-eyebrow__num">{group.n}</span>
                  <span>{group.label}</span>
                </p>
              ) : (
                <div className="mx-2 mb-2.5 h-px bg-[var(--border)]" />
              )}
              <ul className="space-y-px">
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
                        className={`group relative flex items-center gap-3 rounded-[var(--r-md)] px-2.5 py-[7px] text-[var(--t-body)] transition-colors ${
                          isActive
                            ? "bg-[var(--surface-card)] text-[var(--text)]"
                            : "text-[var(--text-secondary)] hover:bg-[var(--surface-raised)] hover:text-[var(--text)]"
                        }`}
                      >
                        {isActive && (
                          <span
                            aria-hidden
                            className="absolute inset-y-1 left-0 w-px bg-[var(--accent)]"
                          />
                        )}
                        <Icon
                          size={15}
                          className={`shrink-0 ${
                            isActive
                              ? "text-[var(--accent)]"
                              : "text-[var(--text-dim)] group-hover:text-[var(--text-muted)]"
                          }`}
                          aria-hidden
                        />
                        {!collapsed && <span className="truncate">{label}</span>}
                        {badgeCount > 0 &&
                          (collapsed ? (
                            <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--critical)]" />
                          ) : (
                            <span className="ml-auto shrink-0 rounded-full border border-[var(--border)] bg-[var(--surface-inset)] px-1.5 py-0.5 font-mono t-micro font-bold leading-none text-[var(--critical)]">
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

        {!collapsed && (
          <div className="border-t border-[var(--border)] p-3">
            <p className="ops-label mb-2">System</p>
            <ul className="space-y-1.5">
              <StateRow label="Core" value={systemOk ? "Operational" : "Degraded"} ok={systemOk} />
              <StateRow label="Database" value={dbOk ? "Connected" : "Offline"} ok={dbOk} />
              <StateRow label="Stream" value={wsOk ? "Live" : "Polling"} ok={wsOk} />
              <StateRow label="Fleet" value={`${fleetCount} units`} ok={fleetCount > 0} />
            </ul>
          </div>
        )}

        <div className="border-t border-[var(--border)] p-2">
          <button
            onClick={() => setOpenCmd(true)}
            title="Command Palette"
            className="flex w-full items-center justify-center gap-2 rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-card)] px-2 py-1.5 text-[var(--t-body)] text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text)]"
          >
            <Search size={13} className="shrink-0" aria-hidden />
            {!collapsed && <span className="ops-label">⌘K Search</span>}
          </button>
        </div>
      </aside>

      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-30 flex h-11 shrink-0 select-none items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface-subtle)] px-4 backdrop-blur">
          <Link href="/" className="flex min-h-6 min-w-0 items-center gap-2 t-body-sm font-semibold tracking-tight text-[var(--text)]">
            <span className="truncate">ColdChain Rescue</span>
            <span className="ops-label hidden shrink-0 border border-[var(--border)] px-2 py-0.5 sm:inline">
              Simulation
            </span>
          </Link>

          <div className="ops-label flex shrink-0 items-center gap-5">
                      <button
                        onClick={toggleTheme}
                        title={isLight ? "Switch to dark theme" : "Switch to light theme"}
                        aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
                        className="flex h-6 min-h-6 min-w-6 items-center justify-center rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-inset)] text-[var(--text-muted)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text)]"
                      >
                        {isLight ? <Moon size={12} aria-hidden /> : <Sun size={12} aria-hidden />}
                      </button>

                      <StatusIndicator label="AI" value={st.status?.ai_mode === "DETERMINISTIC-AGENTS" ? "Deterministic agents" : (st.status?.ai_mode || "Agents")} ok={st.status?.ai_mode === "DETERMINISTIC-AGENTS"} />
            <StatusIndicator label="DB" value={dbOk ? "Connected" : "Offline"} ok={dbOk} />
            <StatusIndicator label="WS" value={wsOk ? "Streaming" : "Polling"} ok={wsOk} />

            <div className="hidden items-center gap-1.5 border-l border-[var(--border)] pl-4 lg:flex">
              <span className="text-[var(--text-dim)]">Fleet</span>
              <span className="ops-num text-[var(--t-micro)] font-bold text-[var(--text)]">
                {fleetCount} twins
              </span>
            </div>

            <span
              className="rounded-[var(--r-pill)] px-2 py-0.5 text-[var(--t-micro)] font-bold"
              style={{
                color: systemOk ? "var(--nominal)" : "var(--warning)",
                background: "var(--surface-inset)",
              }}
            >
              {systemOk ? "Operational" : "Degraded"}
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
    <span className="hidden items-center gap-1.5 sm:flex">
      <span
        className={`h-1.5 w-1.5 rounded-full ${ok ? "ops-pulse" : "animate-pulse"}`}
        style={{ background: ok ? "var(--nominal)" : "var(--critical)" }}
        aria-hidden
      />
      <span className="text-[var(--text-dim)]">{label}</span>
      <span
        className="ops-num text-[var(--t-micro)]"
        style={{ color: ok ? "var(--text-secondary)" : "var(--critical)" }}
      >
        {value}
      </span>
    </span>
  );
}

function StateRow({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <li className="flex items-center justify-between gap-2">
      <span className="ops-label">{label}</span>
      <span
        className="ops-num text-[var(--t-micro)]"
        style={{ color: ok ? "var(--text-secondary)" : "var(--warning)" }}
      >
        {value}
      </span>
    </li>
  );
}

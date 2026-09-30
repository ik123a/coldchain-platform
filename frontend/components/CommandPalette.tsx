"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { post, api } from "@/lib/api";
import { AlertTriangle, Bot, Compass, Flame, MapPin, Navigation, Search, ShieldCheck, Thermometer, Truck, Zap } from "lucide-react";

interface CmdItem {
  key: string;
  category: "VEHICLES" | "ACTIONS" | "WAREHOUSES" | "NAVIGATION";
  label: string;
  hint: string;
  icon?: any;
  run: (args: { router: any; dispatch: any; st: any }) => Promise<void>;
}

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const { st, dispatch } = useStore();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<string>("ALL");
  const [cursor, setCursor] = useState(0);

  // Dynamic commands list
  const baseCommands: CmdItem[] = [
    { 
      key: "demo-launch", 
      category: "ACTIONS",
      label: "Launch Autonomous Rescue Demo", 
      hint: "AUTOPILOT", 
      icon: Zap,
      run: async ({ router }) => { 
        await post("/api/demo/launch?autopilot=true&failure=compressor_failure&after_ticks=8"); 
        router.push("/live-map"); 
      } 
    },
    { 
      key: "compressor-fail", 
      category: "ACTIONS",
      label: "Inject Compressor Failure", 
      hint: "CRITICAL REEFER", 
      icon: Flame,
      run: async ({ st }) => { 
        const sid = st.sim?.simulation_id; 
        if (sid) await post(`/api/simulations/${sid}/failure/compressor_failure`); 
      } 
    },
    { 
      key: "heatwave-inject", 
      category: "ACTIONS",
      label: "Inject 42°C Ambient Heatwave", 
      hint: "THERMAL LOAD", 
      icon: Thermometer,
      run: async ({ st }) => { 
        const sid = st.sim?.simulation_id; 
        if (sid) await post(`/api/simulations/${sid}/failure/heatwave`); 
      } 
    },
    { 
      key: "reroute-execute", 
      category: "ACTIONS",
      label: "Approve Emergency Cold-Hub Detour", 
      hint: "REROUTE NOW", 
      icon: Navigation,
      run: async ({ router }) => { 
        const incs = await api("/api/incidents"); 
        const i = incs?.[0]?.id; 
        if (i) {
          await post(`/api/incidents/${i}/action`, { action: "divert_warehouse" }); 
          router.push("/live-map");
        }
      } 
    },
    { 
      key: "nav-live-map", 
      category: "NAVIGATION",
      label: "Open Live Fleet Tracking Map", 
      hint: "/live-map", 
      icon: Navigation,
      run: async ({ router }) => router.push("/live-map") 
    },
    { 
      key: "nav-copilot", 
      category: "NAVIGATION",
      label: "Open AI Copilot & Incident Commander", 
      hint: "/copilot", 
      icon: Bot,
      run: async ({ router }) => router.push("/copilot") 
    },
    { 
      key: "nav-simulation", 
      category: "NAVIGATION",
      label: "Open Digital Twin Simulation Cockpit", 
      hint: "/simulation", 
      icon: Zap,
      run: async ({ router }) => router.push("/simulation") 
    },
    { 
      key: "nav-incidents", 
      category: "NAVIGATION",
      label: "Open Incident Escalation Center", 
      hint: "/incidents", 
      icon: AlertTriangle,
      run: async ({ router }) => router.push("/incidents") 
    },
  ];

  // Dynamic vehicle quick jumps from store
  const storeVehicles = (st as any)?.fleetVehicles || (st as any)?.vehicles || [];
  const vehicleCommands: CmdItem[] = (storeVehicles.length > 0 ? storeVehicles : [
    { vehicle_id: "TRUCK-101", status: "NOMINAL", temperature: 4.2 },
    { vehicle_id: "TRUCK-104", status: "CRITICAL", temperature: 8.9 },
    { vehicle_id: "TRUCK-108", status: "AT_RISK", temperature: 6.4 },
    { vehicle_id: "TRUCK-112", status: "NOMINAL", temperature: 3.8 },
  ]).map((v: any) => ({
    key: `vehicle-${v.vehicle_id}`,
    category: "VEHICLES" as const,
    label: `Jump to ${v.vehicle_id} (${v.temperature ? v.temperature.toFixed(1) : "4.0"}°C · ${v.status})`,
    hint: v.status,
    icon: Truck,
    run: async ({ router, dispatch }) => {
      dispatch({ type: "select_truck", payload: v.vehicle_id });
      router.push(`/live-map?truck=${v.vehicle_id}`);
    }
  }));

  // Dynamic warehouse quick jumps
  const warehouseCommands: CmdItem[] = [
    { id: "wh-01", name: "ColdHub South", bays: "3 free", temp: "-20°C to +4°C" },
    { id: "wh-02", name: "Phoenix Central Depot", bays: "1 free", temp: "+2°C to +8°C" },
    { id: "wh-03", name: "Apex Distribution Hub", bays: "4 free", temp: "-18°C to +2°C" },
  ].map(w => ({
    key: `warehouse-${w.id}`,
    category: "WAREHOUSES" as const,
    label: `Inspect ${w.name} (${w.bays} · ${w.temp})`,
    hint: "COLD HUB",
    icon: MapPin,
    run: async ({ router }) => {
      router.push(`/live-map?hub=${w.id}`);
    }
  }));

  const allCommands = [...baseCommands, ...vehicleCommands, ...warehouseCommands];

  const filtered = allCommands.filter(c => {
    const matchesCat = category === "ALL" || c.category === category;
    const matchesQuery = c.label.toLowerCase().includes(q.toLowerCase()) || c.hint.toLowerCase().includes(q.toLowerCase());
    return matchesCat && matchesQuery;
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") setCursor(c => Math.min(filtered.length - 1, c + 1));
      if (e.key === "ArrowUp") setCursor(c => Math.max(0, c - 1));
      if (e.key === "Enter" && filtered[cursor]) { 
        filtered[cursor].run({ router, dispatch, st }); 
        onClose(); 
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, cursor]);

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm grid place-items-start pt-24 px-4" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl bg-[var(--surface-raised)] border border-[var(--border)] shadow-2xl overflow-hidden p-3 fade-in" onClick={e => e.stopPropagation()}>
        {/* Search input bar */}
        <div className="relative flex items-center border-b border-[var(--border)] pb-3 pt-1 px-2">
          <Search size={18} className="text-[var(--text-dim)] mr-2.5 shrink-0" />
          <input 
            autoFocus 
            value={q} 
            onChange={e => { setQ(e.target.value); setCursor(0); }}
            placeholder="Type a command or search vehicles, hubs, emergency actions..."
            aria-label="Command search"
            className="w-full bg-transparent t-body text-[var(--text)] focus:outline-none placeholder-[var(--text-dim)] font-mono" 
          />
          <kbd className="hidden sm:inline-block t-micro font-mono px-2 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border)] text-[var(--text-dim)]">
            ESC to close
          </kbd>
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 px-2 pt-2.5 pb-2 t-label font-mono">
          {["ALL", "ACTIONS", "VEHICLES", "WAREHOUSES", "NAVIGATION"].map(cat => (
            <button
              key={cat}
              onClick={() => { setCategory(cat); setCursor(0); }}
              className={`px-2.5 py-1 rounded-md transition-colors ${category === cat ? "bg-[var(--surface-inset)] text-[var(--accent)] border border-[var(--border)]" : "text-[var(--text-dim)] hover:text-[var(--text)] hover:bg-[var(--surface-card)]"}`}>
              {cat}
            </button>
          ))}
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto scroll-thin py-1 space-y-1">
          {filtered.map((c, i) => {
            const Icon = c.icon || Zap;
            const isSelected = i === cursor;
            return (
              <button 
                key={c.key}
                className={`w-full text-left px-3 py-2.5 rounded-xl flex items-center justify-between transition-all t-body-sm font-mono ${isSelected ? "bg-[var(--surface-card)] border border-[var(--accent)] text-[var(--text)]" : "text-[var(--border-strong)] hover:bg-[var(--surface-card)] border border-transparent"}`}
                onMouseEnter={() => setCursor(i)}
                onClick={() => { c.run({ router, dispatch, st }); onClose(); }}>
                <div className="flex items-center gap-2.5 truncate">
                  <div className={`p-1.5 rounded-lg ${isSelected ? "bg-[var(--surface-inset)] text-[var(--accent)]" : "bg-[var(--surface-card)] text-[var(--text-dim)]"}`}>
                    <Icon size={14} />
                  </div>
                  <span className="truncate">{c.label}</span>
                </div>
                <span className={`t-micro px-2 py-0.5 rounded shrink-0 font-semibold border ${c.hint === "CRITICAL" || c.hint === "CRITICAL REEFER" ? "bg-[var(--surface-inset)] text-[var(--critical)] border-[var(--border)]" : c.hint === "AUTOPILOT" ? "bg-[var(--surface-inset)] text-[var(--accent)] border-[var(--border)]" : "bg-[var(--surface-card)] text-[var(--text-dim)] border-[var(--border)]"}`}>
                  {c.hint}
                </span>
              </button>
            );
          })}
          {!filtered.length && (
            <div className="t-body-sm font-mono text-[var(--text-dim)] p-6 text-center">
              No matching commands or resources found for "{q}"
            </div>
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="border-t border-[var(--border)] pt-2 px-2 flex items-center justify-between t-micro font-mono text-[var(--text-dim)]">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border)] text-[var(--border-strong)]">↑</kbd> <kbd className="px-1 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border)] text-[var(--border-strong)]">↓</kbd> navigate</span>
            <span><kbd className="px-1 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border)] text-[var(--border-strong)]">↵</kbd> select</span>
          </div>
          <span>ColdChain Autonomous Command</span>
        </div>
      </div>
    </div>
  );
}


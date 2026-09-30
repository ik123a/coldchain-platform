"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X, Thermometer, ShieldAlert, ShieldCheck, Activity, Cpu, AlertTriangle, 
  ArrowRight, CheckCircle2, Bot, Navigation, Warehouse, Clock, Zap, Split, 
  Truck, Compass, Gauge, Battery, Wrench, UserCheck, Check, CornerDownRight, ArrowLeftRight
} from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceArea, BarChart, Bar } from "recharts";
import { BorderBeam } from "@/components/ui/border-beam";
import { NumberTicker } from "@/components/ui/number-ticker";

interface DeepTelemetryProps {
  vehicle: any;
  onClose: () => void;
  onApproveDiversion: (vehicleId: string, facilityId: string) => void;
  onInjectFailure: (vehicleId: string) => void;
}

type DrawerTab = "overview" | "movement" | "refrigeration" | "cargo" | "vehicle" | "driver" | "route" | "ai_ops";

export function DeepTelemetryDrawer({ vehicle, onClose, onApproveDiversion, onInjectFailure }: DeepTelemetryProps) {
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");
  const [diverting, setDiverting] = useState(false);
  const [transferring, setTransferring] = useState(false);
  const [transferProgress, setTransferProgress] = useState(0);

  if (!vehicle) return null;

  const temp = vehicle.refrigeration?.temperature ?? 4.8;
  const outside = vehicle.outside_temperature ?? 41.8;
  const isBreached = temp > 8.0;
  const riskLevel = vehicle.cargo?.risk_level || (isBreached ? "CRITICAL" : "LOW");
  const speed = Math.round(vehicle.speed_kmh ?? 42);
  const maxSpeed = Math.round(vehicle.max_speed_kmh ?? 58);
  const avgSpeed = Math.round(vehicle.avg_speed_kmh ?? 44);
  const heading = Math.round(vehicle.heading ?? 74);
  const distRemaining = (vehicle.trip?.distance_remaining_km ?? 12.7).toFixed(1);
  const etaMin = vehicle.trip?.eta_min ?? 14;
  const progressPct = Math.round(vehicle.trip?.route_progress_percent ?? 45);
  const cargoHealth = Math.round(vehicle.cargo?.cargo_health ?? 96);
  const loadUnits = vehicle.load_units ?? 540;
  const capUnits = vehicle.capacity_units ?? 1000;
  const loadPct = Math.round((loadUnits / capUnits) * 100);

  // Generate dynamic 20-minute temperature series
  const chartData = [];
  const baseT = Math.max(3.5, temp - 1.5);
  for (let i = 0; i <= 20; i += 2) {
    const projectedInside = i < 10 
      ? +(baseT + (temp - baseT) * (i / 10)).toFixed(1)
      : +(temp + (isBreached ? (i - 10) * 0.4 : (Math.sin(i) * 0.2))).toFixed(1);
    const ambientOut = +(outside - 2 + (i * 0.2)).toFixed(1);
    chartData.push({
      time: `T-${20 - i}m`,
      inside: projectedInside,
      outside: ambientOut,
      safeMin: 2.0,
      safeMax: 8.0
    });
  }

  // What-if Divergence Data (Future A Continue vs Future B Divert)
  const whatIfData = [
    { step: "Now", continueTemp: temp, divertTemp: temp, continueRisk: 42, divertRisk: 42 },
    { step: "+5m", continueTemp: +(temp + 1.2).toFixed(1), divertTemp: +(temp + 0.4).toFixed(1), continueRisk: 65, divertRisk: 48 },
    { step: "+10m", continueTemp: +(temp + 2.8).toFixed(1), divertTemp: +(temp - 0.2).toFixed(1), continueRisk: 88, divertRisk: 35 },
    { step: "+15m", continueTemp: +(temp + 4.6).toFixed(1), divertTemp: 5.2, continueRisk: 99, divertRisk: 18 },
  ];

  const handleDiversion = (facilityId: string = "WH-002") => {
    setDiverting(true);
    setTimeout(() => {
      onApproveDiversion(vehicle.vehicle_id, facilityId);
      setDiverting(false);
    }, 600);
  };

  const handleTransfer = () => {
    setTransferring(true);
    let p = 0;
    const interval = setInterval(() => {
      p += 25;
      setTransferProgress(p);
      if (p >= 100) {
        clearInterval(interval);
        setTimeout(() => setTransferring(false), 500);
      }
    }, 300);
  };

  return (
    <motion.div
      initial={{ y: "100%", opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: "100%", opacity: 0 }}
      transition={{ type: "spring", damping: 28, stiffness: 240 }}
      className="fixed bottom-0 left-0 right-0 z-50 max-h-[85vh] bg-[var(--surface-subtle)] border-t border-[var(--border)] rounded-t-2xl shadow-2xl flex flex-col text-slate-100 overflow-hidden font-sans select-none">
      
      {/* 1. Header & Navigation Tabs */}
      <div className="p-3.5 border-b border-[var(--border)] flex flex-wrap items-center justify-between gap-3 bg-[var(--canvas)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[var(--surface-card)] border border-[var(--border)] grid place-items-center">
            <Truck size={16} className="text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="t-body font-bold text-white font-mono">{vehicle.vehicle_id}</span>
              <span className={`px-2 py-0.5 rounded t-micro font-mono font-bold ${
                riskLevel === "CRITICAL" ? "bg-rose-950 text-rose-400 border border-rose-800" :
                riskLevel === "HIGH" ? "bg-amber-950 text-amber-400 border border-amber-800" :
                "bg-emerald-950 text-emerald-400 border border-emerald-800"
              }`}>
                {riskLevel} RISK
              </span>
              <span className="t-body-sm text-slate-500 font-mono">· {vehicle.type || "EV_REEFER"}</span>
            </div>
            <div className="t-label text-slate-400 font-mono">
              Driver: {vehicle.driver?.name || "R. Sharma"} · Safety: {vehicle.driver?.driving_score || 94}%
            </div>
          </div>
        </div>

        {/* 8 Progressive Disclosure Tabs (Section 16) */}
        <div className="flex items-center gap-1 bg-[#101622] p-1 rounded-lg border border-[var(--border)] t-body-sm font-medium overflow-x-auto scroll-thin">
          {[
            { id: "overview", label: "Overview" },
            { id: "movement", label: "Movement" },
            { id: "refrigeration", label: "Refrigeration" },
            { id: "cargo", label: "Cargo" },
            { id: "vehicle", label: "Vehicle Health" },
            { id: "driver", label: "Driver" },
            { id: "route", label: "Route & Traffic" },
            { id: "ai_ops", label: "AI Operations" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as DrawerTab)}
              className={`px-2.5 py-1 rounded transition-colors whitespace-nowrap ${
                activeTab === tab.id 
                  ? "bg-[#1A2333] text-cyan-300 shadow-sm border border-cyan-500/30" 
                  : "text-slate-400 hover:text-slate-200"
              }`}>
              {tab.label}
            </button>
          ))}
        </div>

        <button
          onClick={onClose}
          aria-label="Close drawer"
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[var(--surface-card)] transition-colors">
          <X size={17} />
        </button>
      </div>

      {/* 2. Main Content Viewport */}
      <div className="p-5 overflow-y-auto max-h-[70vh] space-y-6">
        
        {/* TAB 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-[var(--surface-card)] p-3.5 rounded-xl border border-[var(--border)] relative overflow-hidden">
                <div className="t-micro font-mono text-slate-400">INSIDE CORE TEMP</div>
                <div className="t-metric-lg font-bold font-mono mt-1">
                  <NumberTicker 
                    value={temp} 
                    decimalPlaces={1} 
                    suffix="°C" 
                    className={isBreached ? "text-rose-400 font-bold t-metric-lg" : "text-white font-bold t-metric-lg"} 
                  />
                </div>
                <div className="t-body-sm font-mono text-emerald-400 mt-0.5">Safe Zone: 2.0–8.0°C</div>
              </div>

              <div className="bg-[var(--surface-card)] p-3.5 rounded-xl border border-[var(--border)] relative overflow-hidden">
                <div className="t-micro font-mono text-slate-400">OUTSIDE AMBIENT</div>
                <div className="t-metric-lg font-bold font-mono text-amber-400 mt-1">
                  <NumberTicker 
                    value={outside} 
                    decimalPlaces={1} 
                    suffix="°C" 
                    className="text-amber-400 font-bold t-metric-lg" 
                  />
                </div>
                <div className="t-micro font-mono text-amber-400/80 mt-0.5">Heatwave Active</div>
              </div>

              <div className="bg-[var(--surface-card)] p-3.5 rounded-xl border border-[var(--border)] relative overflow-hidden">
                <div className="t-micro font-mono text-slate-400">CARGO HEALTH</div>
                <div className="t-metric-lg font-bold font-mono mt-1">
                  <NumberTicker 
                    value={cargoHealth} 
                    suffix="%" 
                    className={cargoHealth < 85 ? "text-amber-400 font-bold t-metric-lg" : "text-emerald-400 font-bold t-metric-lg"} 
                  />
                </div>
                <div className="t-micro font-mono text-slate-400 mt-0.5">{vehicle.cargo?.cargo_type || "pharma"} (High Value)</div>
              </div>

              <div className="bg-[var(--surface-card)] p-3.5 rounded-xl border border-[var(--border)] relative overflow-hidden">
                <div className="t-micro font-mono text-slate-400">ETA / REMAINING</div>
                <div className="t-metric-lg font-bold font-mono text-cyan-400 mt-1 flex items-baseline gap-1">
                  <NumberTicker 
                    value={etaMin} 
                    suffix=" min" 
                    className="text-cyan-400 font-bold t-metric-lg" 
                  />
                </div>
                <div className="t-micro font-mono text-slate-400 mt-0.5">{distRemaining} km to destination</div>
              </div>
            </div>

            {/* Quick Actions & AI Recommendation Banner with BorderBeam */}
            <div className="bg-[#101622] p-4 rounded-xl border border-[var(--border)] flex flex-col md:flex-row items-start md:items-center justify-between gap-3 relative overflow-hidden">
              {isBreached && (
                <BorderBeam 
                  size={120} 
                  duration={4} 
                  colorFrom="var(--critical)" 
                  colorTo="var(--warning-soft)" 
                  borderWidth={1.5} 
                />
              )}
              <div className="flex items-center gap-3 relative z-10">
                <div className={`w-8 h-8 rounded-lg grid place-items-center shrink-0 border ${
                  isBreached ? "bg-rose-950/80 border-rose-800 text-rose-400" : "bg-cyan-950/80 border-cyan-800 text-cyan-400"
                }`}>
                  <Bot size={16} />
                </div>
                <div>
                  <div className="t-body-sm font-semibold text-white font-mono flex items-center gap-2">
                    AI AGENT EVALUATION: {isBreached ? "EMERGENCY DIVERSION RECOMMENDED" : "NORMAL REEFER OPERATION"}
                  </div>
                  <div className="t-label text-slate-400 mt-0.5">
                    {isBreached 
                      ? "Arrhenius kinetic threshold will be crossed in 8m. Reroute to Hub Beta (WH-002) to prevent $120k spoilage."
                      : "Refrigeration system stable. Kinetic degradation rate within nominal bounds."}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 w-full md:w-auto relative z-10">
                <button
                  onClick={() => onInjectFailure(vehicle.vehicle_id)}
                  className="py-1.5 px-3 rounded-lg t-body-sm font-medium bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition-colors cursor-pointer">
                  ⚡ Inject Anomaly
                </button>
                <button
                  onClick={() => handleDiversion("WH-002")}
                  disabled={diverting}
                  className="py-1.5 px-4 rounded-lg t-body-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors flex items-center gap-1.5 shadow-sm cursor-pointer disabled:opacity-50">
                  <Navigation size={13} /> {diverting ? "Executing..." : "Approve Diversion (WH-002)"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MOVEMENT (SECTION 17) */}
        {activeTab === "movement" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">CURRENT SPEED</div>
                <div className="t-metric-lg font-bold font-mono text-white mt-0.5">{speed} km/h</div>
                <div className="t-micro font-mono text-slate-400">Speed Limit: 60 km/h</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">AVERAGE SPEED</div>
                <div className="t-metric-lg font-bold font-mono text-slate-200 mt-0.5">{avgSpeed} km/h</div>
                <div className="t-micro font-mono text-slate-400">Max Peak: {maxSpeed} km/h</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">HEADING & BEARING</div>
                <div className="t-metric-lg font-bold font-mono text-cyan-400 mt-0.5">{heading}°</div>
                <div className="t-micro font-mono text-slate-400">{vehicle.direction || "EAST"} Corridor</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">ROUTE PROGRESS</div>
                <div className="t-metric-lg font-bold font-mono text-emerald-400 mt-0.5">{progressPct}%</div>
                <div className="t-micro font-mono text-slate-400">Adherence: 99.4%</div>
              </div>
            </div>

            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-3">
              <div className="t-body-sm font-mono font-semibold text-slate-300">KINEMATIC & ROUTE METRICS</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 t-body-sm font-mono">
                <div className="bg-[var(--surface-subtle)] p-2.5 rounded border border-[var(--border)]">
                  <span className="text-slate-400">Acceleration:</span>
                  <div className="text-white font-bold mt-0.5">+0.42 m/s²</div>
                </div>
                <div className="bg-[var(--surface-subtle)] p-2.5 rounded border border-[var(--border)]">
                  <span className="text-slate-400">Idle Time:</span>
                  <div className="text-white font-bold mt-0.5">2.4 min</div>
                </div>
                <div className="bg-[var(--surface-subtle)] p-2.5 rounded border border-[var(--border)]">
                  <span className="text-slate-400">Stop Count:</span>
                  <div className="text-white font-bold mt-0.5">1 Signal Stop</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: REFRIGERATION (SECTIONS 18-20) */}
        {activeTab === "refrigeration" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">OUTSIDE AMBIENT</div>
                <div className="t-metric-lg font-bold font-mono text-amber-400 mt-0.5">{outside.toFixed(1)}°C</div>
                <div className="t-micro font-mono text-slate-400">Thermal Load: High</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">INSIDE TEMPERATURE</div>
                <div className={`t-metric-lg font-bold font-mono mt-0.5 ${isBreached ? "text-rose-400" : "text-white"}`}>
                  {temp.toFixed(1)}°C
                </div>
                <div className="t-body-sm font-mono text-emerald-400">Safe: 2.0°C – 8.0°C</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">COMPRESSOR STATUS</div>
                <div className="t-section font-bold font-mono text-white mt-1">
                  {vehicle.refrigeration?.compressor_status || "ONLINE"}
                </div>
                <div className="t-micro font-mono text-slate-400">Efficiency: {isBreached ? "34%" : "96%"}</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">TIME TO CRITICAL</div>
                <div className={`t-metric-lg font-bold font-mono mt-0.5 ${isBreached ? "text-rose-400" : "text-slate-300"}`}>
                  {isBreached ? "07:42" : "> 6 hrs"}
                </div>
                <div className="t-body-sm font-mono text-slate-400">Trend: {isBreached ? "+0.3°C/min" : "Stable"}</div>
              </div>
            </div>

            {/* Live Chart */}
            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-2">
              <div className="flex items-center justify-between t-body-sm font-mono">
                <span className="text-slate-300 font-semibold">20-MINUTE REEFER TRAJECTORY (INSIDE VS OUTSIDE)</span>
                <div className="flex items-center gap-3">
                  <span className="text-cyan-400">● Inside Temp</span>
                  <span className="text-amber-400">● Outside Ambient</span>
                  <span className="text-emerald-400">■ Safe Band (2–8°C)</span>
                </div>
              </div>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <XAxis dataKey="time" stroke="#475569" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} />
                    <YAxis domain={[0, 48]} stroke="#475569" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} unit="°C" />
                    <Tooltip contentStyle={{ backgroundColor: "var(--canvas)", borderColor: "var(--border)", fontSize: "11px" }} />
                    <ReferenceArea y1={2} y2={8} fill="#10b981" fillOpacity={0.12} />
                    <Line type="monotone" dataKey="outside" stroke="#f59e0b" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="inside" stroke={isBreached ? "var(--critical)" : "var(--ai)"} strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: CARGO (SECTIONS 21-22) */}
        {activeTab === "cargo" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">CARGO TYPE</div>
                <div className="t-section font-bold font-mono text-white mt-1 uppercase">{vehicle.cargo?.cargo_type || "PHARMA"}</div>
                <div className="t-body-sm font-mono text-slate-400">Req: 2.0°C – 8.0°C</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">CURRENT LOAD</div>
                <div className="t-section font-bold font-mono text-white mt-1">{loadUnits} / {capUnits} units</div>
                <div className="t-micro font-mono text-cyan-400">{loadPct}% Capacity</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">CARGO HEALTH</div>
                <div className={`t-metric-lg font-bold font-mono mt-0.5 ${cargoHealth < 85 ? "text-amber-400" : "text-emerald-400"}`}>
                  {cargoHealth}%
                </div>
                <div className="t-micro font-mono text-slate-400">Exposure: {vehicle.trip?.exposure_ticks || 0} ticks</div>
              </div>
              <div className="bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
                <div className="t-micro font-mono text-slate-400">BATCH VALUE</div>
                <div className="t-metric-lg font-bold font-mono text-white mt-0.5">$124,000</div>
                <div className="t-body-sm font-mono text-emerald-400">Priority: Tier 1 Critical</div>
              </div>
            </div>

            {/* Cargo Transfer Visualizer (Section 38) */}
            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-3">
              <div className="flex items-center justify-between">
                <span className="t-body-sm font-mono font-semibold text-slate-300 flex items-center gap-2">
                  <ArrowLeftRight size={14} className="text-cyan-400" /> CROSS-TRUCK RELIEF CARGO TRANSFER (SECTION 38)
                </span>
                <button
                  onClick={handleTransfer}
                  disabled={transferring}
                  className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 t-body-sm font-semibold text-white transition-colors">
                  {transferring ? `Transferring (${transferProgress}%)` : "Simulate Relief Offload"}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <div className="bg-[var(--surface-subtle)] p-3 rounded-lg border border-[var(--border)]">
                  <div className="t-body-sm font-mono font-bold text-rose-400">DISTRESSED TRUCK ({vehicle.vehicle_id})</div>
                  <div className="t-section font-mono font-bold text-white mt-1">
                    {transferring ? Math.round(74 - (30 * transferProgress / 100)) : 74}% LOAD
                  </div>
                  <div className="t-micro font-mono text-slate-400 mt-0.5">Offloading to Relief Unit</div>
                </div>

                <div className="bg-[var(--surface-subtle)] p-3 rounded-lg border border-[var(--border)]">
                  <div className="t-body-sm font-mono font-bold text-emerald-400">RELIEF REEFER (SERVICE-01)</div>
                  <div className="t-section font-mono font-bold text-white mt-1">
                    {transferring ? Math.round(38 + (30 * transferProgress / 100)) : 38}% LOAD
                  </div>
                  <div className="t-body-sm font-mono text-slate-400 mt-0.5">Pre-chilled @ 3.8°C</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: VEHICLE HEALTH */}
        {activeTab === "vehicle" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 font-mono t-body-sm">
              {[
                { label: "Cooling Compressor", val: isBreached ? "34% (DEGRADED)" : "98% (NOMINAL)", hot: isBreached },
                { label: "Powertrain / Engine", val: "94% (HEALTHY)" },
                { label: "Battery / State of Charge", val: "88% (420 km range)" },
                { label: "Braking System", val: "92% (PADS OK)" },
                { label: "Tire Pressure", val: "108 PSI (OPTIMAL)" },
                { label: "Chamber Thermal Insulation", val: "91% (SEALED)" },
              ].map((m, i) => (
                <div key={i} className="bg-[var(--surface-card)] p-3.5 rounded-xl border border-[var(--border)]">
                  <div className="t-micro text-slate-400">{m.label}</div>
                  <div className={`t-body font-bold mt-1 ${m.hot ? "text-rose-400" : "text-white"}`}>{m.val}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 6: DRIVER */}
        {activeTab === "driver" && (
          <div className="bg-[var(--surface-card)] p-5 rounded-xl border border-[var(--border)] space-y-4 font-mono t-body-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-cyan-950 border border-cyan-800 grid place-items-center text-cyan-400 font-bold t-body">
                RS
              </div>
              <div>
                <div className="t-body font-bold text-white">{vehicle.driver?.name || "Rajesh Sharma"}</div>
                <div className="text-slate-400 t-label">ID: DRV-882 · Commercial Reefer Certified</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 pt-2">
              <div className="bg-[var(--surface-subtle)] p-3 rounded-lg border border-[var(--border)]">
                <span className="text-slate-400 t-micro">DRIVING SCORE</span>
                <div className="text-emerald-400 font-bold t-section mt-0.5">94 / 100</div>
              </div>
              <div className="bg-[var(--surface-subtle)] p-3 rounded-lg border border-[var(--border)]">
                <span className="text-slate-400 t-micro">HOURS ON DUTY</span>
                <div className="text-white font-bold t-section mt-0.5">4.2 hrs (Limit 8h)</div>
              </div>
              <div className="bg-[var(--surface-subtle)] p-3 rounded-lg border border-[var(--border)]">
                <span className="text-slate-400 t-micro">SAFETY RATING</span>
                <div className="text-cyan-400 font-bold t-section mt-0.5">GRADE A+</div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 7: ROUTE & TRAFFIC (SECTIONS 27-30) */}
        {activeTab === "route" && (
          <div className="space-y-4 font-mono t-body-sm">
            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-3">
              <div className="t-body-sm font-bold text-slate-300">ACTIVE CORRIDOR & TRAFFIC CONDITIONS</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-2.5 bg-[var(--surface-subtle)] rounded-lg border border-[var(--border)]">
                  <span className="text-slate-300">Corridor Segment 8A (Expressway):</span>
                  <span className="px-2 py-0.5 rounded t-micro font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">FREE FLOW (62 km/h)</span>
                </div>
                <div className="flex items-center justify-between p-2.5 bg-[var(--surface-subtle)] rounded-lg border border-[var(--border)]">
                  <span className="text-slate-300">Corridor Segment 8B (Metro Tollway):</span>
                  <span className="px-2 py-0.5 rounded t-micro font-bold bg-amber-950 text-amber-400 border border-amber-800">MODERATE (+4m delay)</span>
                </div>
                <div className="flex items-center justify-between p-2.5 bg-[var(--surface-subtle)] rounded-lg border border-[var(--border)]">
                  <span className="text-slate-300">Corridor Segment 8C (Industrial Link):</span>
                  <span className="px-2 py-0.5 rounded t-micro font-bold bg-rose-950 text-rose-400 border border-rose-800">SEVERE CONGESTION</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 8: AI OPERATIONS & WHAT-IF (SECTIONS 23-26, 32, 75) */}
        {activeTab === "ai_ops" && (
          <div className="space-y-5 font-mono t-body-sm">
            
            {/* 8-Stage Operations Stream */}
            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-3">
              <div className="t-body-sm font-bold text-slate-300 flex items-center gap-2">
                <Bot size={15} className="text-cyan-400" /> MULTI-AGENT STATE PROGRESSION STREAM
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { stage: "Monitoring", status: "ACTIVE", color: "text-emerald-400", dot: "bg-emerald-400" },
                  { stage: "Diagnosis", status: "COMPLETE", color: "text-emerald-400", dot: "bg-emerald-400" },
                  { stage: "Prediction", status: "ACTIVE", color: "text-cyan-400", dot: "bg-cyan-400 animate-pulse" },
                  { stage: "Risk Analysis", status: "EVALUATING", color: "text-amber-400", dot: "bg-amber-400" },
                  { stage: "Facility Match", status: "COMPLETE", color: "text-emerald-400", dot: "bg-emerald-400" },
                  { stage: "Route Detour", status: "LOCKED", color: "text-cyan-400", dot: "bg-cyan-400" },
                  { stage: "Response", status: "READY", color: "text-white", dot: "bg-white" },
                  { stage: "Verification", status: "STANDBY", color: "text-slate-400", dot: "bg-slate-400" },
                ].map((s, i) => (
                  <div key={i} className="bg-[var(--surface-subtle)] p-2 rounded-lg border border-[var(--border)] flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${s.dot}`}></span>
                    <div>
                      <div className="t-micro text-slate-400">{s.stage}</div>
                      <div className={`t-label font-bold ${s.color}`}>{s.status}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Candidate Facilities Table (Section 32) */}
            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-3">
              <div className="t-body-sm font-bold text-slate-300">FACILITY COMPARISON MATRIX (SECTION 32)</div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--border)] t-micro text-slate-400 uppercase">
                      <th className="py-2">Warehouse</th>
                      <th className="py-2">Distance</th>
                      <th className="py-2">Travel Time</th>
                      <th className="py-2">Dock Queue</th>
                      <th className="py-2">Free Capacity</th>
                      <th className="py-2">AI Rank</th>
                      <th className="py-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]/50">
                    <tr className="hover:bg-[#1A2333]/50">
                      <td className="py-2.5 font-bold text-white">Hub Alpha (WH-001)</td>
                      <td className="py-2.5 text-slate-300">4.2 km</td>
                      <td className="py-2.5 text-slate-300">15 min</td>
                      <td className="py-2.5 text-amber-400">Queue 20 min</td>
                      <td className="py-2.5 text-slate-300">120 pallets</td>
                      <td className="py-2.5 text-slate-400">Rank #2</td>
                      <td className="py-2.5 text-right">
                        <button onClick={() => handleDiversion("WH-001")} className="px-2 py-1 rounded bg-[#101622] hover:bg-[var(--border)] t-micro text-slate-300">Select</button>
                      </td>
                    </tr>
                    <tr className="bg-cyan-950/20 border border-cyan-800/40">
                      <td className="py-2.5 font-bold text-cyan-300 flex items-center gap-1.5">
                        <CheckCircle2 size={13} className="text-cyan-400" /> Hub Beta (WH-002)
                      </td>
                      <td className="py-2.5 text-white">6.8 km</td>
                      <td className="py-2.5 text-emerald-400 font-bold">9 min (Clear Toll)</td>
                      <td className="py-2.5 text-emerald-400 font-bold">Queue 4 min</td>
                      <td className="py-2.5 text-white">430 pallets</td>
                      <td className="py-2.5 text-cyan-300 font-bold">OPTIMAL (#1)</td>
                      <td className="py-2.5 text-right">
                        <button onClick={() => handleDiversion("WH-002")} className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 t-micro font-bold text-white">Divert Now</button>
                      </td>
                    </tr>
                    <tr className="hover:bg-[#1A2333]/50 opacity-60">
                      <td className="py-2.5 font-bold text-slate-400">Hub Gamma (WH-003)</td>
                      <td className="py-2.5 text-slate-400">3.9 km</td>
                      <td className="py-2.5 text-slate-400">12 min</td>
                      <td className="py-2.5 text-rose-400">Dock Full</td>
                      <td className="py-2.5 text-rose-400">0 pallets</td>
                      <td className="py-2.5 text-rose-400">Ineligible</td>
                      <td className="py-2.5 text-right">—</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* What-If Simulation Divergence (Section 75) */}
            <div className="bg-[var(--surface-card)] p-4 rounded-xl border border-[var(--border)] space-y-3">
              <div className="t-body-sm font-bold text-slate-300 flex items-center gap-2">
                <Split size={14} className="text-cyan-400" /> WHAT-IF TRAJECTORY DIVERGENCE (CONTINUE VS DIVERT)
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                {whatIfData.map((d, i) => (
                  <div key={i} className="bg-[var(--surface-subtle)] p-2.5 rounded-lg border border-[var(--border)]">
                    <div className="t-micro text-slate-400 font-bold">{d.step}</div>
                    <div className="t-body-sm text-rose-400 mt-1">Continue: {d.continueTemp}°C</div>
                    <div className="t-body-sm text-emerald-400">Divert: {d.divertTemp}°C</div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

      </div>
    </motion.div>
  );
}

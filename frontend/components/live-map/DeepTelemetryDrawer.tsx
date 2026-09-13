"use client";
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  X, Thermometer, ShieldAlert, ShieldCheck, Activity, Cpu, AlertTriangle, 
  ArrowRight, CheckCircle2, Bot, Navigation, Warehouse, Clock, Zap, Split, Truck
} from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceArea } from "recharts";

interface DeepTelemetryProps {
  vehicle: any;
  onClose: () => void;
  onApproveDiversion: (vehicleId: string, facilityId: string) => void;
  onInjectFailure: (vehicleId: string) => void;
}

export function DeepTelemetryDrawer({ vehicle, onClose, onApproveDiversion, onInjectFailure }: DeepTelemetryProps) {
  const [activeTab, setActiveTab] = useState<"telemetry" | "ai" | "whatif" | "subsystems">("telemetry");
  const [diverting, setDiverting] = useState(false);

  if (!vehicle) return null;

  const temp = vehicle.refrigeration?.temperature ?? 4.8;
  const outside = vehicle.outside_temperature ?? 41.8;
  const isBreached = temp > 8.0;
  const riskLevel = vehicle.cargo?.risk_level || (isBreached ? "CRITICAL" : "LOW");

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
      outside: ambientOut
    });
  }

  const handleDiversion = () => {
    setDiverting(true);
    setTimeout(() => {
      onApproveDiversion(vehicle.vehicle_id, "WH-002");
      setDiverting(false);
    }, 600);
  };

  return (
    <motion.div
      initial={{ y: "100%", opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: "100%", opacity: 0 }}
      transition={{ type: "spring", damping: 26, stiffness: 220 }}
      className="fixed bottom-0 left-0 right-0 z-50 max-h-[85vh] bg-[#0E121A] border-t border-[#1E2638] rounded-t-2xl shadow-2xl flex flex-col text-slate-100 overflow-hidden">
      
      {/* Drawer Drag Bar & Header */}
      <div className="p-4 border-b border-[#1E2638] flex items-center justify-between bg-[#080A0F]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#141B26] border border-[#1E2638] grid place-items-center">
            <Truck size={18} className="text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white font-mono">{vehicle.vehicle_id}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                riskLevel === "CRITICAL" ? "bg-rose-950 text-rose-400 border border-rose-800" :
                riskLevel === "HIGH" ? "bg-amber-950 text-amber-400 border border-amber-800" :
                "bg-emerald-950 text-emerald-400 border border-emerald-800"
              }`}>
                {riskLevel} RISK
              </span>
              <span className="text-xs text-slate-500 font-mono">· Corridor 8</span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono">
              Driver: {vehicle.driver?.name || "R. Sharma"} · Driving Score: {vehicle.driver?.driving_score || 94}
            </div>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-1 bg-[#141B26] p-1 rounded-lg border border-[#1E2638]">
          <button
            onClick={() => setActiveTab("telemetry")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${activeTab === "telemetry" ? "bg-[#1C2433] text-cyan-300" : "text-slate-400 hover:text-slate-200"}`}>
            Thermal Telemetry
          </button>
          <button
            onClick={() => setActiveTab("ai")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${activeTab === "ai" ? "bg-[#1C2433] text-cyan-300" : "text-slate-400 hover:text-slate-200"}`}>
            <Bot size={12} /> AI Rescue Ops
          </button>
          <button
            onClick={() => setActiveTab("whatif")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${activeTab === "whatif" ? "bg-[#1C2433] text-cyan-300" : "text-slate-400 hover:text-slate-200"}`}>
            <Split size={12} /> What-If Simulation
          </button>
          <button
            onClick={() => setActiveTab("subsystems")}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${activeTab === "subsystems" ? "bg-[#1C2433] text-cyan-300" : "text-slate-400 hover:text-slate-200"}`}>
            Diagnostics
          </button>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#141B26] transition-colors">
          <X size={18} />
        </button>
      </div>

      {/* Drawer Body Content */}
      <div className="p-6 overflow-y-auto max-h-[70vh] space-y-6">
        
        {/* Tab 1: Thermal Telemetry */}
        {activeTab === "telemetry" && (
          <div className="space-y-6">
            {/* Top Stat Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-[#141B26] p-4 rounded-xl border border-[#1E2638]">
                <div className="text-[10px] font-mono text-slate-400">INSIDE CORE TEMP</div>
                <div className="text-3xl font-bold font-mono text-white mt-1">{temp.toFixed(1)}°C</div>
                <div className="text-[10px] font-mono text-emerald-400 mt-0.5">Target: 2.0°C – 8.0°C</div>
              </div>

              <div className="bg-[#141B26] p-4 rounded-xl border border-[#1E2638]">
                <div className="text-[10px] font-mono text-slate-400">OUTSIDE AMBIENT</div>
                <div className="text-3xl font-bold font-mono text-amber-400 mt-1">{outside.toFixed(1)}°C</div>
                <div className="text-[10px] font-mono text-amber-500/80 mt-0.5">Heatwave Warning</div>
              </div>

              <div className="bg-[#141B26] p-4 rounded-xl border border-[#1E2638]">
                <div className="text-[10px] font-mono text-slate-400">ARRHENIUS RSL</div>
                <div className="text-3xl font-bold font-mono text-cyan-400 mt-1">16.8 hrs</div>
                <div className="text-[10px] font-mono text-slate-400 mt-0.5">Degradation: Nominal</div>
              </div>

              <div className="bg-[#141B26] p-4 rounded-xl border border-[#1E2638]">
                <div className="text-[10px] font-mono text-slate-400">RESCUE DOCK ETA</div>
                <div className="text-3xl font-bold font-mono text-white mt-1">
                  {vehicle.trip?.eta_min || 14} min
                </div>
                <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                  Dist: {vehicle.trip?.distance_remaining_km || 12.4} km
                </div>
              </div>
            </div>

            {/* Live Chart */}
            <div className="bg-[#141B26] p-5 rounded-xl border border-[#1E2638] space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-xs font-mono font-semibold text-slate-300">
                  TEMPERATURE TRAJECTORY SPECTRUM (INSIDE VS OUTSIDE)
                </div>
                <div className="flex items-center gap-4 text-xs font-mono">
                  <span className="flex items-center gap-1.5 text-cyan-400">
                    <span className="w-2.5 h-0.5 bg-cyan-400"></span> Core Temp
                  </span>
                  <span className="flex items-center gap-1.5 text-amber-400">
                    <span className="w-2.5 h-0.5 bg-amber-400"></span> Ambient Outside
                  </span>
                  <span className="flex items-center gap-1.5 text-emerald-400">
                    <span className="w-2.5 h-2 bg-emerald-950 border border-emerald-500"></span> Safe Zone (2-8°C)
                  </span>
                </div>
              </div>

              <div className="h-60 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <XAxis dataKey="time" stroke="#475569" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                    <YAxis domain={[0, 48]} stroke="#475569" tick={{ fontSize: 10, fill: "#94a3b8" }} unit="°C" />
                    <Tooltip contentStyle={{ backgroundColor: "#080A0F", borderColor: "#1E2638", fontSize: "11px" }} />
                    <ReferenceArea y1={2} y2={8} fill="#10b981" fillOpacity={0.12} />
                    <Line type="monotone" dataKey="outside" stroke="#f59e0b" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="inside" stroke={isBreached ? "#f43f5e" : "#06b6d4"} strokeWidth={3} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Action Bar */}
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => onInjectFailure(vehicle.vehicle_id)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition-colors">
                ⚡ Inject Compressor Degradation
              </button>

              <button
                onClick={handleDiversion}
                disabled={diverting}
                className="px-6 py-2.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-2 transition-colors">
                <Navigation size={14} /> {diverting ? "Executing Detour..." : "Trigger Autonomous Rescue Reroute"}
              </button>
            </div>
          </div>
        )}

        {/* Tab 2: AI Rescue Operations */}
        {activeTab === "ai" && (
          <div className="space-y-6">
            <div className="bg-[#141B26] p-5 rounded-xl border border-[#1E2638] space-y-4">
              <div className="flex items-center justify-between border-b border-[#1E2638] pb-3">
                <div className="flex items-center gap-2">
                  <Bot size={18} className="text-cyan-400" />
                  <h3 className="text-sm font-bold text-white font-mono">AUTONOMOUS MULTI-AGENT RESCUE FEED</h3>
                </div>
                <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                  DETERMINISTIC &lt;5ms
                </span>
              </div>

              {/* Agent Sequence */}
              <div className="space-y-3 font-mono text-xs">
                <div className="bg-[#080A0F] p-3 rounded-lg border border-[#1E2638] flex items-start gap-3">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 mt-1"></span>
                  <div>
                    <span className="text-emerald-400 font-bold">MONITORING AGENT:</span>
                    <p className="text-slate-300 mt-0.5">Spike-vs-shift Kalman gate active. Rate of climb: +0.28°C/min. Outside ambient steady at 41.8°C.</p>
                  </div>
                </div>

                <div className="bg-[#080A0F] p-3 rounded-lg border border-[#1E2638] flex items-start gap-3">
                  <span className="w-2 h-2 rounded-full bg-amber-400 mt-1"></span>
                  <div>
                    <span className="text-amber-400 font-bold">DIAGNOSIS AGENT:</span>
                    <p className="text-slate-300 mt-0.5">Mechanical cooling degraded to 34% efficiency. Secondary compression stage non-responsive.</p>
                  </div>
                </div>

                <div className="bg-[#080A0F] p-3 rounded-lg border border-[#1E2638] flex items-start gap-3">
                  <span className="w-2 h-2 rounded-full bg-rose-400 mt-1"></span>
                  <div>
                    <span className="text-rose-400 font-bold">PREDICTION & RISK AGENT:</span>
                    <p className="text-slate-300 mt-0.5">Critical excursion breach (&gt;8.0°C) estimated in 7m 42s. Arrhenius shelf-life degradation accelerating.</p>
                  </div>
                </div>

                <div className="bg-[#080A0F] p-3 rounded-lg border border-[#1E2638] flex items-start gap-3">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 mt-1"></span>
                  <div>
                    <span className="text-cyan-400 font-bold">FACILITY MATCHING AGENT:</span>
                    <p className="text-slate-300 mt-0.5">5 facilities evaluated. Hub Beta (WH-002) selected: 9 min detour, 430 available pallets, Pre-chilled staging dock 3 reserved.</p>
                  </div>
                </div>
              </div>

              {/* Recommendation Box */}
              <div className="p-4 rounded-xl bg-gradient-to-r from-cyan-950/40 to-[#141B26] border border-cyan-500/40 flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">AI RECOMMENDATION</div>
                  <div className="text-sm font-bold text-white mt-0.5">Divert to Hub Beta (Pre-chilled Bay 3)</div>
                  <div className="text-xs text-slate-400 font-mono mt-0.5">ETA: 9 min · Risk reduction: HIGH → LOW · Confidence: 91%</div>
                </div>
                <button
                  onClick={handleDiversion}
                  disabled={diverting}
                  className="px-5 py-2.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors">
                  {diverting ? "Routing..." : "Approve Diversion"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: What-If Simulation */}
        {activeTab === "whatif" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Option A */}
              <div className="bg-[#141B26] p-5 rounded-xl border border-rose-900/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-950 text-rose-400 border border-rose-800">
                    TRAJECTORY A: CONTINUE ON ROUTE
                  </span>
                  <span className="text-xs font-mono text-rose-400 font-bold">HIGH RISK</span>
                </div>
                <div className="text-2xl font-bold font-mono text-white">Spoilage in 7m 42s</div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Remaining distance to original destination is 34 km (44 min). With degraded compressor under 41.8°C heat, internal temperature will reach 14.2°C, causing total batch loss ($140,000).
                </p>
                <div className="p-3 bg-[#080A0F] rounded-lg border border-[#1E2638] text-xs font-mono text-rose-300">
                  Expected Loss: 100% · Arrhenius Decay: Critical
                </div>
              </div>

              {/* Option B */}
              <div className="bg-[#141B26] p-5 rounded-xl border border-emerald-900/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-400 border border-emerald-800">
                    TRAJECTORY B: DIVERT TO HUB BETA
                  </span>
                  <span className="text-xs font-mono text-emerald-400 font-bold">RECOMMENDED</span>
                </div>
                <div className="text-2xl font-bold font-mono text-white">Safe Dock in 9 min</div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Hub Beta is located 8.4 km away. Dock bay 3 is pre-chilled to 3.8°C. Vehicle arrives prior to Arrhenius threshold expiration, restoring cold chain safely.
                </p>
                <div className="p-3 bg-[#080A0F] rounded-lg border border-[#1E2638] text-xs font-mono text-emerald-300">
                  Expected Loss: 0% · Cargo Integrity: 98.4%
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleDiversion}
                className="px-6 py-2.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5 transition-colors">
                <CheckCircle2 size={14} /> Execute Option B (Divert)
              </button>
            </div>
          </div>
        )}

        {/* Tab 4: Subsystems */}
        {activeTab === "subsystems" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { name: "Cooling Compressor", val: 84, col: "bg-emerald-400" },
              { name: "Engine & Powertrain", val: 96, col: "bg-emerald-400" },
              { name: "Brake System", val: 92, col: "bg-emerald-400" },
              { name: "Tires & Pressure", val: 89, col: "bg-emerald-400" },
              { name: "Insulation Seals", val: 91, col: "bg-emerald-400" },
              { name: "Telemetry Gateway", val: 99, col: "bg-cyan-400" },
            ].map(sub => (
              <div key={sub.name} className="bg-[#141B26] p-4 rounded-xl border border-[#1E2638] space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-300">{sub.name}</span>
                  <span className="font-bold text-white">{sub.val}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className={`h-full ${sub.col}`} style={{ width: `${sub.val}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

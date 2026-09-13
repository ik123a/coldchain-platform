"use client";
import React from "react";
import { motion } from "framer-motion";
import { 
  X, Navigation, AlertTriangle, ShieldCheck, Thermometer, 
  ExternalLink, Zap, Compass, ChevronUp, Radio
} from "lucide-react";

interface FloatingInspectorProps {
  vehicle: any;
  onClose: () => void;
  onOpenDrawer: () => void;
  onTrack: () => void;
  isTracking: boolean;
  onInject: () => void;
}

export function FloatingVehicleInspector({
  vehicle,
  onClose,
  onOpenDrawer,
  onTrack,
  isTracking,
  onInject
}: FloatingInspectorProps) {
  if (!vehicle) return null;

  const temp = vehicle.refrigeration?.temperature ?? 4.8;
  const outside = vehicle.outside_temperature ?? 41.8;
  const isBreached = temp > 8.0;
  const riskLevel = vehicle.cargo?.risk_level || (isBreached ? "CRITICAL" : "LOW");

  return (
    <motion.div
      initial={{ opacity: 0, y: -12, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className="absolute top-4 right-4 z-30 w-80 bg-[#0E121A]/95 backdrop-blur-md border border-[#1E2638] rounded-xl p-4 shadow-2xl text-slate-100 space-y-3">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1E2638] pb-2.5">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${isBreached ? "bg-rose-500 animate-ping" : "bg-emerald-400"}`}></span>
          <span className="font-mono text-sm font-bold text-white">{vehicle.vehicle_id}</span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
            riskLevel === "CRITICAL" ? "bg-rose-950 text-rose-400 border border-rose-800" :
            riskLevel === "HIGH" ? "bg-amber-950 text-amber-400 border border-amber-800" :
            "bg-emerald-950 text-emerald-400 border border-emerald-800"
          }`}>
            {riskLevel}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-slate-400 hover:text-white transition-colors">
          <X size={14} />
        </button>
      </div>

      {/* Main Metric Spotlight */}
      <div className="grid grid-cols-2 gap-2.5">
        <div className="bg-[#141B26] p-2.5 rounded-lg border border-[#1E2638]">
          <div className="text-[10px] font-mono text-slate-400">CORE TEMP</div>
          <div className={`text-xl font-bold font-mono mt-0.5 ${isBreached ? "text-rose-400" : "text-white"}`}>
            {temp.toFixed(1)}°C
          </div>
          <div className="text-[9px] font-mono text-emerald-400">Target 2–8°C</div>
        </div>

        <div className="bg-[#141B26] p-2.5 rounded-lg border border-[#1E2638]">
          <div className="text-[10px] font-mono text-slate-400">SPEED / ETA</div>
          <div className="text-xl font-bold font-mono text-white mt-0.5">
            {Math.round(vehicle.speed_kmh || 42)} <span className="text-xs font-normal text-slate-400">km/h</span>
          </div>
          <div className="text-[9px] font-mono text-cyan-400">ETA {vehicle.trip?.eta_min || 14} min</div>
        </div>
      </div>

      {/* Secondary Row */}
      <div className="space-y-1 text-[11px] font-mono text-slate-300">
        <div className="flex justify-between">
          <span className="text-slate-400">Ambient Outside:</span>
          <span className="text-amber-400 font-semibold">{outside.toFixed(1)}°C</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Remaining Dist:</span>
          <span>{vehicle.trip?.distance_remaining_km || 12.4} km</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Compressor Status:</span>
          <span className={vehicle.refrigeration?.compressor_status === "ONLINE" ? "text-emerald-400" : "text-rose-400"}>
            {vehicle.refrigeration?.compressor_status || "ONLINE"}
          </span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="pt-2 border-t border-[#1E2638] flex items-center gap-2">
        <button
          onClick={onOpenDrawer}
          className="flex-1 py-1.5 px-2 rounded-lg text-xs font-semibold bg-cyan-600/90 hover:bg-cyan-500 text-white flex items-center justify-center gap-1 transition-colors">
          <ChevronUp size={14} /> Full Telemetry
        </button>

        <button
          onClick={onTrack}
          className={`py-1.5 px-2.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1 ${
            isTracking 
              ? "bg-cyan-950 text-cyan-300 border-cyan-800" 
              : "bg-[#141B26] text-slate-300 border-[#1E2638] hover:bg-[#1E2638]"
          }`}>
          <Radio size={12} className={isTracking ? "animate-pulse text-cyan-400" : ""} />
          {isTracking ? "Tracking" : "Follow"}
        </button>

        <button
          onClick={onInject}
          title="Inject Compressor Failure"
          className="py-1.5 px-2 rounded-lg text-xs bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition-colors">
          <Zap size={13} />
        </button>
      </div>
    </motion.div>
  );
}

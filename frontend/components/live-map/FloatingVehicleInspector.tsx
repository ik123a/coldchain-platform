"use client";
import React from "react";
import { motion } from "framer-motion";
import { 
  X, Navigation, AlertTriangle, ShieldCheck, Thermometer, 
  ExternalLink, Zap, Compass, ChevronUp, Radio, ArrowUpRight
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
  const speed = Math.round(vehicle.speed_kmh ?? 42);
  const headingDeg = Math.round(vehicle.heading ?? 74);
  const direction = vehicle.direction || (headingDeg < 45 || headingDeg >= 315 ? "NORTH" : headingDeg < 135 ? "EAST" : headingDeg < 225 ? "SOUTH" : "WEST");
  const eta = vehicle.trip?.eta_min ?? 14;
  const dist = (vehicle.trip?.distance_remaining_km ?? 12.7).toFixed(1);
  const cargoHealth = Math.round(vehicle.cargo?.cargo_health ?? 96);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
      className="absolute top-4 right-4 z-30 w-80 bg-[#0E121A]/95 backdrop-blur-md border border-[#1E2638] rounded-xl p-4 shadow-2xl text-slate-100 space-y-3 font-sans">
      
      {/* 1. Header: Truck ID & Live Status */}
      <div className="flex items-center justify-between border-b border-[#1E2638] pb-2.5">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${isBreached ? "bg-rose-500 animate-ping" : "bg-emerald-400"}`}></span>
          <span className="font-mono text-sm font-bold text-white tracking-wide">{vehicle.vehicle_id}</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#141B26] text-slate-300 border border-[#1E2638]">
            LIVE
          </span>
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
          aria-label="Close inspector"
          className="p-1 rounded text-slate-400 hover:text-white transition-colors">
          <X size={14} />
        </button>
      </div>

      {/* 2. Speed & Heading */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-[#141B26] p-2.5 rounded-lg border border-[#1E2638]">
          <div className="text-[10px] font-mono text-slate-400">SPEED / HEADING</div>
          <div className="text-lg font-bold font-mono text-white mt-0.5">
            {speed} <span className="text-xs font-normal text-slate-400">km/h</span>
          </div>
          <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1 mt-0.5">
            <Compass size={11} className="text-cyan-400" /> {direction} ({headingDeg}°)
          </div>
        </div>

        <div className="bg-[#141B26] p-2.5 rounded-lg border border-[#1E2638]">
          <div className="text-[10px] font-mono text-slate-400">ETA / REMAINING</div>
          <div className="text-lg font-bold font-mono text-cyan-400 mt-0.5">
            {eta} <span className="text-xs font-normal text-slate-400">min</span>
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-0.5">
            {dist} km remaining
          </div>
        </div>
      </div>

      {/* 3. Refrigeration Telemetry (Inside vs Outside) */}
      <div className="bg-[#101622] p-2.5 rounded-lg border border-[#1E2638] space-y-1.5">
        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-slate-400">INSIDE CORE:</span>
          <span className={`font-bold ${isBreached ? "text-rose-400" : "text-white"}`}>
            {temp.toFixed(1)}°C <span className="text-[9px] font-normal text-emerald-400">(Safe 2–8°C)</span>
          </span>
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-slate-400">OUTSIDE AMBIENT:</span>
          <span className="font-bold text-amber-400">{outside.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono pt-1 border-t border-[#1E2638]/60">
          <span className="text-slate-400">CARGO HEALTH:</span>
          <span className={`font-bold ${cargoHealth < 85 ? "text-amber-400" : "text-emerald-400"}`}>
            {cargoHealth}%
          </span>
        </div>
      </div>

      {/* 4. Action Controls */}
      <div className="pt-2 border-t border-[#1E2638] flex items-center gap-2">
        <button
          onClick={onOpenDrawer}
          className="flex-1 py-1.5 px-2 rounded-lg text-xs font-semibold bg-cyan-600/90 hover:bg-cyan-500 text-white flex items-center justify-center gap-1.5 transition-colors shadow-sm">
          <ChevronUp size={13} /> View Telemetry
        </button>

        <button
          onClick={onTrack}
          title={isTracking ? "Stop tracking vehicle" : "Track vehicle on map"}
          className={`py-1.5 px-2.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1 ${
            isTracking 
              ? "bg-cyan-950 text-cyan-300 border-cyan-800" 
              : "bg-[#141B26] text-slate-300 border-[#1E2638] hover:bg-[#1E2638]"
          }`}>
          <Radio size={12} className={isTracking ? "animate-pulse text-cyan-400" : ""} />
          {isTracking ? "Tracking" : "Track"}
        </button>

        <button
          onClick={onInject}
          title="Simulate Compressor Anomaly"
          className="py-1.5 px-2 rounded-lg text-xs bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition-colors">
          <Zap size={13} />
        </button>
      </div>
    </motion.div>
  );
}

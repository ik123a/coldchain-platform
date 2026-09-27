"use client";
import React from "react";
import { motion } from "framer-motion";
import { 
  X, Navigation, AlertTriangle, ShieldCheck, Thermometer, 
  ExternalLink, Zap, Compass, ChevronUp, Radio, ArrowUpRight
} from "lucide-react";
import { TelemetrySparkles } from "./TelemetrySparkles";
import { BorderBeam } from "@/components/ui/border-beam";
import { NumberTicker } from "@/components/ui/number-ticker";

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

  const temp = Number(vehicle.refrigeration?.temperature ?? 4.8);
  const outside = Number(vehicle.outside_temperature ?? 41.8);
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
      className="absolute top-4 right-4 z-30 w-84 bg-[#0E121A]/95 backdrop-blur-md border border-[#1E2638] rounded-xl p-4 shadow-2xl text-slate-100 space-y-3 font-sans overflow-hidden">
      
      {/* Awwwards Border Beam Glow */}
      <BorderBeam
        size={90}
        duration={isBreached ? 3.5 : 8}
        colorFrom={isBreached ? "#f43f5e" : "#38bdf8"}
        colorTo={isBreached ? "#fbbf24" : "#06b6d4"}
        borderWidth={1.5}
      />

      {/* 1. Header: Truck ID & Live Status */}
      <div className="flex items-center justify-between border-b border-[#1E2638] pb-2.5 relative z-10">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${isBreached ? "bg-rose-500 animate-ping" : "bg-emerald-400"}`}></span>
          <span className="font-mono t-body font-bold text-white tracking-wide">{vehicle.vehicle_id}</span>
          <span className="t-micro font-mono px-1.5 py-0.5 rounded bg-[#141B26] text-cyan-400 border border-cyan-800/40">
            LIVE TWIN
          </span>
          <span className={`px-1.5 py-0.5 rounded t-micro font-mono font-bold ${
            riskLevel === "CRITICAL" ? "bg-rose-950 text-rose-400 border border-rose-800 animate-pulse" :
            riskLevel === "HIGH" ? "bg-amber-950 text-amber-400 border border-amber-800" :
            "bg-emerald-950 text-emerald-400 border border-emerald-800"
          }`}>
            {riskLevel}
          </span>
        </div>
        <button
          onClick={onClose}
          aria-label="Close inspector"
          className="p-1 rounded text-slate-400 hover:text-white hover:bg-[#1E2638] transition-colors">
          <X size={14} />
        </button>
      </div>

      {/* 2. Speed & Heading with Animated Number Ticker */}
      <div className="grid grid-cols-2 gap-2 relative z-10">
        <div className="bg-[#141B26] p-2.5 rounded-lg border border-[#1E2638]">
          <div className="t-micro font-mono text-slate-400">SPEED / HEADING</div>
          <div className="t-section font-bold font-mono text-white mt-0.5 flex items-baseline gap-1">
            <NumberTicker value={speed} className="t-section font-bold text-white" />
            <span className="t-body-sm font-normal text-slate-400">km/h</span>
          </div>
          <div className="t-micro font-mono text-slate-400 flex items-center gap-1 mt-0.5">
            <Compass size={11} className="text-cyan-400" /> {direction} ({headingDeg}°)
          </div>
        </div>

        <div className="bg-[#141B26] p-2.5 rounded-lg border border-[#1E2638]">
          <div className="t-micro font-mono text-slate-400">ETA / REMAINING</div>
          <div className="t-section font-bold font-mono text-cyan-400 mt-0.5 flex items-baseline gap-1">
            <NumberTicker value={eta} className="t-section font-bold text-cyan-400" />
            <span className="t-body-sm font-normal text-slate-400">min</span>
          </div>
          <div className="t-micro font-mono text-slate-400 mt-0.5">
            {dist} km remaining
          </div>
        </div>
      </div>

      {/* 3. Refrigeration Telemetry (Inside vs Outside) */}
      <div className="bg-[#101622] p-2.5 rounded-lg border border-[#1E2638] space-y-1.5 relative z-10">
        <div className="flex items-center justify-between t-label font-mono">
          <span className="text-slate-400">INSIDE CORE:</span>
          <span className={`font-bold flex items-center gap-1.5 ${isBreached ? "text-rose-400" : "text-white"}`}>
            <NumberTicker 
              value={temp} 
              decimalPlaces={1} 
              suffix="°C" 
              className={isBreached ? "text-rose-400 font-bold" : "text-white font-bold"} 
            />
            <span className="t-body-sm font-normal text-emerald-400">(Safe 2–8°C)</span>
          </span>
        </div>
        <div className="flex items-center justify-between t-label font-mono">
          <span className="text-slate-400">OUTSIDE AMBIENT:</span>
          <NumberTicker 
            value={outside} 
            decimalPlaces={1} 
            suffix="°C" 
            className="font-bold text-amber-400" 
          />
        </div>
        <div className="flex items-center justify-between t-label font-mono pt-1 border-t border-[#1E2638]/60">
          <span className="text-slate-400">CARGO HEALTH:</span>
          <NumberTicker 
            value={cargoHealth} 
            suffix="%" 
            className={`font-bold ${cargoHealth < 85 ? "text-amber-400" : "text-emerald-400"}`} 
          />
        </div>
      </div>

      {/* 3.5 Rolling telemetry sparklines (15m window) */}
      <div className="relative z-10">
        <TelemetrySparkles vehicleId={vehicle.vehicle_id} />
      </div>

      {/* 4. Action Controls */}
      <div className="pt-2 border-t border-[#1E2638] flex items-center gap-2 relative z-10">
        <button
          onClick={onOpenDrawer}
          className="flex-1 py-1.5 px-2 rounded-lg t-body-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center gap-1.5 transition-colors shadow-sm cursor-pointer">
          <ChevronUp size={13} /> View Telemetry
        </button>

        <button
          onClick={onTrack}
          title={isTracking ? "Stop tracking vehicle" : "Track vehicle on map"}
          className={`py-1.5 px-2.5 rounded-lg t-body-sm font-medium border transition-colors flex items-center gap-1 cursor-pointer ${
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
          className="py-1.5 px-2 rounded-lg t-body-sm bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800/60 transition-colors cursor-pointer">
          <Zap size={13} />
        </button>
      </div>
    </motion.div>
  );
}

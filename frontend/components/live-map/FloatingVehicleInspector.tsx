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
      className="absolute top-4 right-4 z-30 w-84 bg-[var(--surface-raised)] backdrop-blur-md border border-[var(--border)] rounded-xl p-4 shadow-2xl text-[var(--surface-inset)] space-y-3 font-sans overflow-hidden">
      
      {/* Awwwards Border Beam Glow */}
      <BorderBeam
        size={90}
        duration={isBreached ? 3.5 : 8}
        colorFrom={isBreached ? "var(--critical)" : "var(--accent)"}
        colorTo={isBreached ? "var(--warning-soft)" : "var(--ai)"}
        borderWidth={1.5}
      />

      {/* 1. Header: Truck ID & Live Status */}
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-2.5 relative z-10">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${isBreached ? "bg-[var(--critical)] animate-ping" : "bg-[var(--nominal)]"}`}></span>
          <span className="font-mono t-body font-bold text-[var(--text)] tracking-wide">{vehicle.vehicle_id}</span>
          <span className="t-micro font-mono px-1.5 py-0.5 rounded bg-[var(--surface-card)] text-[var(--accent)] border border-[var(--border)]">
            LIVE TWIN
          </span>
          <span className={`px-1.5 py-0.5 rounded t-micro font-mono font-bold ${
            riskLevel === "CRITICAL" ? "bg-[var(--surface-inset)] text-[var(--critical)] border border-[var(--border)] animate-pulse" :
            riskLevel === "HIGH" ? "bg-[var(--surface-inset)] text-[var(--warning)] border border-[var(--border)]" :
            "bg-[var(--surface-inset)] text-[var(--nominal)] border border-[var(--border)]"
          }`}>
            {riskLevel}
          </span>
        </div>
        <button
          onClick={onClose}
          aria-label="Close inspector"
          className="p-1 rounded text-[var(--text-dim)] hover:text-[var(--text)] hover:bg-[var(--border)] transition-colors">
          <X size={14} />
        </button>
      </div>

      {/* 2. Speed & Heading with Animated Number Ticker */}
      <div className="grid grid-cols-2 gap-2 relative z-10">
        <div className="bg-[var(--surface-card)] p-2.5 rounded-lg border border-[var(--border)]">
          <div className="t-micro font-mono text-[var(--text-dim)]">SPEED / HEADING</div>
          <div className="t-section font-bold font-mono text-[var(--text)] mt-0.5 flex items-baseline gap-1">
            <NumberTicker value={speed} className="t-section font-bold text-[var(--text)]" />
            <span className="t-body-sm font-normal text-[var(--text-dim)]">km/h</span>
          </div>
          <div className="t-micro font-mono text-[var(--text-dim)] flex items-center gap-1 mt-0.5">
            <Compass size={11} className="text-[var(--accent)]" /> {direction} ({headingDeg}°)
          </div>
        </div>

        <div className="bg-[var(--surface-card)] p-2.5 rounded-lg border border-[var(--border)]">
          <div className="t-micro font-mono text-[var(--text-dim)]">ETA / REMAINING</div>
          <div className="t-section font-bold font-mono text-[var(--accent)] mt-0.5 flex items-baseline gap-1">
            <NumberTicker value={eta} className="t-section font-bold text-[var(--accent)]" />
            <span className="t-body-sm font-normal text-[var(--text-dim)]">min</span>
          </div>
          <div className="t-micro font-mono text-[var(--text-dim)] mt-0.5">
            {dist} km remaining
          </div>
        </div>
      </div>

      {/* 3. Refrigeration Telemetry (Inside vs Outside) */}
      <div className="bg-[var(--surface-inset)] p-2.5 rounded-lg border border-[var(--border)] space-y-1.5 relative z-10">
        <div className="flex items-center justify-between t-label font-mono">
          <span className="text-[var(--text-dim)]">INSIDE CORE:</span>
          <span className={`font-bold flex items-center gap-1.5 ${isBreached ? "text-[var(--critical)]" : "text-[var(--text)]"}`}>
            <NumberTicker 
              value={temp} 
              decimalPlaces={1} 
              suffix="°C" 
              className={isBreached ? "text-[var(--critical)] font-bold" : "text-[var(--text)] font-bold"} 
            />
            <span className="t-body-sm font-normal text-[var(--nominal)]">(Safe 2–8°C)</span>
          </span>
        </div>
        <div className="flex items-center justify-between t-label font-mono">
          <span className="text-[var(--text-dim)]">OUTSIDE AMBIENT:</span>
          <NumberTicker 
            value={outside} 
            decimalPlaces={1} 
            suffix="°C" 
            className="font-bold text-[var(--warning)]" 
          />
        </div>
        <div className="flex items-center justify-between t-label font-mono pt-1 border-t border-[var(--border)]">
          <span className="text-[var(--text-dim)]">CARGO HEALTH:</span>
          <NumberTicker 
            value={cargoHealth} 
            suffix="%" 
            className={`font-bold ${cargoHealth < 85 ? "text-[var(--warning)]" : "text-[var(--nominal)]"}`} 
          />
        </div>
      </div>

      {/* 3.5 Rolling telemetry sparklines (15m window) */}
      <div className="relative z-10">
        <TelemetrySparkles vehicleId={vehicle.vehicle_id} />
      </div>

      {/* 4. Action Controls */}
      <div className="pt-2 border-t border-[var(--border)] flex items-center gap-2 relative z-10">
        <button
          onClick={onOpenDrawer}
          className="flex-1 py-1.5 px-2 rounded-lg t-body-sm font-semibold bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--text)] flex items-center justify-center gap-1.5 transition-colors shadow-sm cursor-pointer">
          <ChevronUp size={13} /> View Telemetry
        </button>

        <button
          onClick={onTrack}
          title={isTracking ? "Stop tracking vehicle" : "Track vehicle on map"}
          className={`py-1.5 px-2.5 rounded-lg t-body-sm font-medium border transition-colors flex items-center gap-1 cursor-pointer ${
            isTracking 
              ? "bg-[var(--surface-inset)] text-[var(--text)] border-[var(--border)]" 
              : "bg-[var(--surface-card)] text-[var(--border-strong)] border-[var(--border)] hover:bg-[var(--border)]"
          }`}>
          <Radio size={12} className={isTracking ? "animate-pulse text-[var(--accent)]" : ""} />
          {isTracking ? "Tracking" : "Track"}
        </button>

        <button
          onClick={onInject}
          title="Simulate Compressor Anomaly"
          className="py-1.5 px-2 rounded-lg t-body-sm bg-[var(--surface-inset)] hover:bg-[var(--surface-inset)] text-[var(--critical)] border border-[var(--border)] transition-colors cursor-pointer">
          <Zap size={13} />
        </button>
      </div>
    </motion.div>
  );
}

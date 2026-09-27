"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface WeatherOverlayProps {
  condition: "clear" | "heatwave" | "rain" | "fog" | "storm";
  intensity?: number;
  className?: string;
}

export function WeatherOverlay({
  condition,
  intensity = 0.5,
  className,
}: WeatherOverlayProps) {
  if (condition === "clear") return null;

  return (
    <div 
      className={cn("pointer-events-none absolute inset-0 overflow-hidden mix-blend-screen", className)}
      aria-hidden="true"
    >
      {condition === "heatwave" && (
        <div 
          className="absolute inset-0 opacity-40 mix-blend-overlay animate-heatwave-distort"
          style={{
            backgroundImage: "radial-gradient(circle at 50% 50%, rgba(245, 158, 11, 0.15), transparent 60%)",
            backdropFilter: `blur(${intensity * 2}px)`,
          }}
        />
      )}

      {(condition === "rain" || condition === "storm") && (
        <div 
          className="absolute inset-0 opacity-50 bg-[length:20px_100px] animate-rain-stream"
          style={{
            backgroundImage: "linear-gradient(to bottom, transparent, rgba(56, 189, 248, 0.4) 80%, transparent)",
            opacity: intensity * 0.8,
          }}
        />
      )}

      {(condition === "fog" || condition === "storm") && (
        <div 
          className="absolute inset-0 bg-slate-500/10 animate-drift-fog opacity-30 blur-xl"
          style={{
            backgroundImage: "radial-gradient(ellipse at center, rgba(148, 163, 184, 0.2) 0%, transparent 70%)",
            opacity: intensity * 0.5,
          }}
        />
      )}

      {condition === "storm" && (
        <div 
          className="absolute inset-0 bg-white/10 animate-lightning-flash"
          style={{ opacity: intensity * 0.3 }}
        />
      )}
    </div>
  );
}

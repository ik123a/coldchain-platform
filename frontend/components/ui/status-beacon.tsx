"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface StatusBeaconProps {
  status: "online" | "warning" | "critical" | "offline";
  size?: "sm" | "md" | "lg";
  label?: string;
  showRipple?: boolean;
  className?: string;
}

const colorMap = {
  online: "bg-emerald-500",
  warning: "bg-amber-500",
  critical: "bg-rose-500",
  offline: "bg-slate-500",
};

const rippleMap = {
  online: "border-emerald-500",
  warning: "border-amber-500",
  critical: "border-rose-500",
  offline: "border-slate-500",
};

const sizeMap = {
  sm: "h-2 w-2",
  md: "h-3 w-3",
  lg: "h-4 w-4",
};

export function StatusBeacon({
  status,
  size = "md",
  label,
  showRipple = true,
  className,
}: StatusBeaconProps) {
  const isPulsing = status !== "offline" && showRipple;
  const baseColor = colorMap[status];
  const rippleColor = rippleMap[status];
  const dimensions = sizeMap[size];

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className={cn("relative flex items-center justify-center", dimensions)}>
        {/* Core dot */}
        <div className={cn("absolute rounded-full", dimensions, baseColor, status === "critical" && "animate-pulse")} />

        {/* Ripples */}
        {isPulsing && (
          <>
            <div
              className={cn("absolute rounded-full border opacity-0 animate-ping", dimensions, rippleColor)}
              style={{ animationDuration: "2s", animationDelay: "0s" }}
            />
            <div
              className={cn("absolute rounded-full border opacity-0 animate-ping", dimensions, rippleColor)}
              style={{ animationDuration: "2s", animationDelay: "0.3s" }}
            />
            <div
              className={cn("absolute rounded-full border opacity-0 animate-ping", dimensions, rippleColor)}
              style={{ animationDuration: "2s", animationDelay: "0.6s" }}
            />
          </>
        )}
      </div>
      {label && <span className="t-body-sm font-medium text-slate-300">{label}</span>}
    </div>
  );
}

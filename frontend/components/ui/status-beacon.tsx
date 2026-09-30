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
  online: "bg-[var(--nominal)]",
  warning: "bg-[var(--warning)]",
  critical: "bg-[var(--critical)]",
  offline: "bg-[var(--text-dim)]",
};

const rippleMap = {
  online: "border-[var(--nominal)]",
  warning: "border-[var(--warning)]",
  critical: "border-[var(--critical)]",
  offline: "border-[var(--text-dim)]",
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
      {label && <span className="t-body-sm font-medium text-[var(--border-strong)]">{label}</span>}
    </div>
  );
}

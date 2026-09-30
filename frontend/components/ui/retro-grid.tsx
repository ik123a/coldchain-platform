"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface RetroGridProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
  angle?: number;
  cellSize?: number;
  opacity?: number;
  lineColor?: string;
}

export function RetroGrid({
  className,
  angle = 65,
  cellSize = 50,
  opacity = 0.25,
  lineColor = "#1e293b",
  ...props
}: RetroGridProps) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden [perspective:200px]",
        className
      )}
      style={{ opacity }}
      {...props}
    >
      {/* Grid container with 3D rotation */}
      <div className="absolute inset-0 [transform-origin:100%_0_0]">
        <div
          className="animate-retro-grid absolute -inset-[100%] h-[300vh] w-[600vw] origin-[100%_0_0]"
          style={{
            transform: `rotateX(${angle}deg)`,
            backgroundImage: `linear-gradient(to right, ${lineColor} 1px, transparent 0), linear-gradient(to bottom, ${lineColor} 1px, transparent 0)`,
            backgroundSize: `${cellSize}px ${cellSize}px`,
            backgroundRepeat: "repeat",
          }}
        />
      </div>

      {/* Background gradient fade */}
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--canvas)] via-transparent to-transparent" />
    </div>
  );
}

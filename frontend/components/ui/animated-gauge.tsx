"use client";

import React, { useEffect, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnimatedGaugeProps {
  value: number;
  label: string;
  unit: string;
  colorFrom: string;
  colorTo: string;
  warningThreshold?: number;
  criticalThreshold?: number;
  size?: number;
  animated?: boolean;
  className?: string;
}

export function AnimatedGauge({
  value,
  label,
  unit,
  colorFrom,
  colorTo,
  warningThreshold = 75,
  criticalThreshold = 90,
  size = 120,
  animated = true,
  className,
}: AnimatedGaugeProps) {
  const safeValue = typeof value === "number" && !isNaN(value) ? Math.min(Math.max(value, 0), 100) : 0;
  const strokeWidth = size * 0.1;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  
  // 270 degree arc
  const arcLength = 270;
  const arcOffset = 135;

  const springValue = useSpring(0, {
    stiffness: 60,
    damping: 20,
    mass: 1,
  });

  useEffect(() => {
    if (animated) {
      springValue.set(safeValue);
    } else {
      springValue.jump(safeValue);
    }
  }, [safeValue, animated, springValue]);

  const strokeDashoffset = useTransform(springValue, (v) => {
    const fraction = (typeof v === "number" && !isNaN(v) ? v : 0) / 100;
    const filledArcLength = (arcLength / 360) * circumference * fraction;
    return circumference - filledArcLength;
  });

  const displayValue = useTransform(springValue, (v) => (typeof v === "number" && !isNaN(v) ? Math.round(v) : 0));

  const isCritical = safeValue >= criticalThreshold;
  const isWarning = safeValue >= warningThreshold && safeValue < criticalThreshold;
  const statusColor = isCritical ? "var(--critical)" : isWarning ? "var(--warning)" : "var(--nominal)";
  
  const [currentDisplayValue, setCurrentDisplayValue] = useState(Math.round(safeValue));

  useEffect(() => {
    return displayValue.on("change", (v) => {
      setCurrentDisplayValue(v);
    });
  }, [displayValue]);

  const safeLabelId = label.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase();
  const numberPx = Math.max(11, Math.min(24, Math.round(size * 0.3)));
  const unitPx = Math.max(10, Math.min(12, Math.round(size * 0.15)));
  const labelPx = 10;

  return (
    <div 
      className={cn("relative flex flex-col items-center justify-center font-mono", className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="overflow-visible"
      >
        <defs>
          <filter id={`glow-${safeLabelId}`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation={isCritical ? "4" : "2"} result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <linearGradient id={`grad-${safeLabelId}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={colorFrom} />
            <stop offset="100%" stopColor={colorTo} />
          </linearGradient>
        </defs>

        {/* Background Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${(arcLength / 360) * circumference} ${circumference}`}
          transform={`rotate(${arcOffset} ${size / 2} ${size / 2})`}
        />

        {/* Foreground Track */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={isCritical || isWarning ? statusColor : `url(#grad-${safeLabelId})`}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          style={{ strokeDashoffset }}
          transform={`rotate(${arcOffset} ${size / 2} ${size / 2})`}
          filter={(isCritical || isWarning) ? `url(#glow-${safeLabelId})` : undefined}
          className={cn("transition-colors duration-500", isCritical && "animate-pulse")}
        />

        {/* Ticks */}
        {Array.from({ length: 5 }).map((_, i) => {
          const angle = (arcLength / 4) * i - (arcLength / 2);
          const radians = (angle * Math.PI) / 180;
          const r1 = radius - strokeWidth - 2;
          const r2 = radius - strokeWidth - 6;
          const cx = size / 2;
          const cy = size / 2;
          const x1 = cx + r1 * Math.sin(radians);
          const y1 = cy - r1 * Math.cos(radians);
          const x2 = cx + r2 * Math.sin(radians);
          const y2 = cy - r2 * Math.cos(radians);

          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="var(--border-strong)"
              strokeWidth={1.5}
            />
          );
        })}
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="flex items-baseline leading-none">
          <span
            className="font-bold tracking-tighter"
            style={{ color: statusColor, fontSize: numberPx }}
          >
            {currentDisplayValue}
          </span>
          <span className="ml-0.5" style={{ color: "var(--text-muted)", fontSize: unitPx }}>
            {unit}
          </span>
        </div>
        <span
          className="mt-0.5 uppercase leading-none"
          style={{ color: "var(--text-dim)", fontSize: labelPx, letterSpacing: "0.08em" }}
        >
          {label}
        </span>
      </div>
    </div>
  );
}

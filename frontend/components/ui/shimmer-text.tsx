"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface ShimmerTextProps {
  children: React.ReactNode;
  className?: string;
  shimmerColor?: string;
  duration?: number;
}

export function ShimmerText({
  children,
  className,
  shimmerColor = "rgba(56,189,248,0.4)",
  duration = 3,
}: ShimmerTextProps) {
  return (
    <span
      className={cn(
        "inline-flex bg-[length:200%_100%] bg-clip-text text-transparent animate-shimmer-pan",
        className
      )}
      style={{
        backgroundImage: `linear-gradient(to right, currentColor 20%, ${shimmerColor} 50%, currentColor 80%)`,
        animationDuration: `${duration}s`,
      }}
    >
      {children}
    </span>
  );
}

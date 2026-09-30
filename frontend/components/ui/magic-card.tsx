"use client";

import React, { useCallback, useRef } from "react";
import { motion, useMotionTemplate, useMotionValue } from "framer-motion";
import { cn } from "@/lib/utils";

interface MagicCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
  className?: string;
  gradientSize?: number;
  gradientColor?: string;
  gradientOpacity?: number;
  borderColor?: string;
}

export function MagicCard({
  children,
  className,
  gradientSize = 240,
  gradientColor = "rgba(56, 189, 248, 0.15)",
  gradientOpacity = 0.8,
  borderColor = "rgba(56, 189, 248, 0.35)",
  ...props
}: MagicCardProps) {
  const mouseX = useMotionValue(-gradientSize);
  const mouseY = useMotionValue(-gradientSize);

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      mouseX.set(e.clientX - rect.left);
      mouseY.set(e.clientY - rect.top);
    },
    [mouseX, mouseY]
  );

  const handlePointerLeave = useCallback(() => {
    mouseX.set(-gradientSize);
    mouseY.set(-gradientSize);
  }, [mouseX, mouseY, gradientSize]);

  return (
    <div
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      className={cn(
        "group relative isolate overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] transition-colors duration-200 hover:border-[var(--border-strong)]",
        className
      )}
      style={{
        boxShadow: "inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 8px 32px -4px rgba(0, 0, 0, 0.65)",
      }}
      {...props}
    >
      {/* Dynamic mouse spotlight glow */}
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-10 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: useMotionTemplate`
            radial-gradient(${gradientSize}px circle at ${mouseX}px ${mouseY}px,
              ${gradientColor},
              transparent 80%
            )
          `,
        }}
      />

      {/* Dynamic border highlight on hover */}
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-px z-10 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background: useMotionTemplate`
            radial-gradient(${gradientSize * 0.8}px circle at ${mouseX}px ${mouseY}px,
              ${borderColor},
              transparent 70%
            )
          `,
          mask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
          maskComposite: "exclude",
          WebkitMaskComposite: "xor",
          padding: "1px",
        }}
      />

      <div className="relative z-20 h-full">{children}</div>
    </div>
  );
}

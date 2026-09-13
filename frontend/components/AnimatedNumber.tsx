"use client";
import { useEffect, useState } from "react";

export function AnimatedNumber({ value, decimals = 0, suffix = "", color }: {
  value: number | null | undefined; decimals?: number; suffix?: string; color?: string;
}) {
  const [display, setDisplay] = useState<number>(0);
  useEffect(() => {
    if (value == null) return;
    const prev = display;
    const diff = value - prev;
    const start = performance.now();
    const dur = 420;
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(prev + diff * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  if (value == null) return <span className="text-[var(--text3)]">—</span>;
  return <span className="kpi-num" style={color ? { color } : undefined}>{display.toFixed(decimals)}{suffix}</span>;
}

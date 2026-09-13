"use client";
import { motion } from "framer-motion";

const COLORS: Record<string, string> = { LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#f8734d", CRITICAL: "#f87171" };

export function RiskGauge({ score, level }: { score: number | null; level: string | null }) {
  const s = score ?? 0;
  const c = COLORS[level || ""] || COLORS.LOW;
  const ang = (s / 100) * 240 - 120;
  return (
    <div className="relative w-32 h-20">
      <svg viewBox="0 0 100 62" className="w-full">
        <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="#1d2a3a" strokeWidth="8" strokeLinecap="round" />
        <motion.path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke={c} strokeWidth="8" strokeLinecap="round"
                     strokeDasharray={`${(s / 100) * 125.6} 126`}
                     initial={{ strokeDasharray: "0 126" }} animate={{ strokeDasharray: `${(s / 100) * 125.6} 126` }}
                     transition={{ duration: 0.6, ease: "easeOut" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center pt-3">
        <div>
          <div className="text-xl font-bold kpi-num" style={{ color: c }}>
            {score == null ? "—" : Math.round(s)}
          </div>
          <div className="text-[9px] tracking-widest" style={{ color: c }}>{level || "…"}</div>
        </div>
      </div>
    </div>
  );
}

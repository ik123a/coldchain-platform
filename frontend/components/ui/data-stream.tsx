"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

interface DataStreamProps {
  className?: string;
  speed?: number;
  maxLines?: number;
}

interface LogLine {
  id: string;
  text: string;
  type: "normal" | "warning" | "critical";
  timestamp: Date;
}

const GENERATORS = [
  () => `TRUCK-${Math.floor(Math.random() * 900) + 100} core_temp=${(Math.random() * 10 - 2).toFixed(1)}°C compressor=${Math.random() > 0.1 ? 'NOMINAL' : 'SPIKE'} speed=${Math.floor(Math.random() * 40) + 40}km/h`,
  () => `WH-${String(Math.floor(Math.random() * 10)).padStart(3, '0')} dock_${Math.floor(Math.random() * 8) + 1} pre-cool=${(Math.random() * 5).toFixed(1)}°C humidity=${Math.floor(Math.random() * 20) + 30}%`,
  () => `AI_AGENT evaluate route_score=${(Math.random() * 0.3 + 0.7).toFixed(2)} reroute=${Math.random() > 0.8 ? 'TRUE' : 'FALSE'}`,
  () => `SYS_DIAG mesh_node_${Math.floor(Math.random() * 50)} latency=${Math.floor(Math.random() * 100) + 10}ms packet_loss=${(Math.random() * 2).toFixed(2)}%`,
];

export function DataStream({ className, speed = 2000, maxLines = 12 }: DataStreamProps) {
  const [lines, setLines] = useState<LogLine[]>([]);

  useEffect(() => {
    let counter = 0;
    
    const interval = setInterval(() => {
      const generator = GENERATORS[Math.floor(Math.random() * GENERATORS.length)];
      const rawText = generator();
      
      let type: "normal" | "warning" | "critical" = "normal";
      if (rawText.includes("reroute=TRUE") || rawText.includes("compressor=SPIKE")) {
        type = "warning";
      }
      if (rawText.includes("core_temp=8") || rawText.includes("core_temp=9") || rawText.includes("packet_loss=2")) {
        type = "critical";
      }

      const now = new Date();
      const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
      
      const newLine: LogLine = {
        id: `log-${counter++}-${Date.now()}`,
        text: `${timeStr} ${rawText}`,
        type,
        timestamp: now,
      };

      setLines((prev) => {
        const next = [...prev, newLine];
        if (next.length > maxLines) {
          return next.slice(next.length - maxLines);
        }
        return next;
      });
    }, speed);

    return () => clearInterval(interval);
  }, [speed, maxLines]);

  return (
    <div className={cn("flex flex-col justify-end overflow-hidden font-mono t-micro sm:t-label leading-relaxed", className)}>
      <AnimatePresence initial={false}>
        {lines.map((line, index) => {
          const age = lines.length - 1 - index;
          const opacity = Math.max(0.1, 1 - age * 0.15);

          const colorClass = 
            line.type === "critical" ? "text-[var(--critical)]" :
            line.type === "warning" ? "text-[var(--warning)]" :
            "text-[var(--nominal)]";

          return (
            <motion.div
              key={line.id}
              initial={{ opacity: 0, y: 10, filter: "blur(4px)" }}
              animate={{ opacity, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, transition: { duration: 0.2 } }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className={cn("whitespace-nowrap overflow-hidden text-ellipsis", colorClass)}
              style={{ opacity }}
            >
              {line.text}
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

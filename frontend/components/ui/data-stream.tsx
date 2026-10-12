"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * DataStream — renders REAL events from the store, never fabricated telemetry.
 *
 * HISTORY: this component generated Math.random() lines (random truck ids,
 * random temperatures, fake "AI_AGENT" decisions) and the dashboard labelled the
 * result "LIVE TELEMETRY FEED". Every number on screen was fiction while real
 * events were already flowing through the store.
 *
 * The caller now passes actual store events (`st.events`, populated by the
 * authenticated WebSocket and the REST polls). When there are no events the
 * component says so instead of inventing activity — an empty feed is a truthful
 * empty feed.
 */

export interface DataStreamEvent {
  id: string | number;
  text: string;
  type?: "normal" | "warning" | "critical";
  timestamp?: string | Date;
}

interface DataStreamProps {
  events: DataStreamEvent[];
  className?: string;
  maxLines?: number;
}

function classify(text: string): "normal" | "warning" | "critical" {
  const t = text.toLowerCase();
  if (t.includes("critical") || t.includes("escalat") || t.includes("failure")
      || t.includes("breach")) return "critical";
  if (t.includes("warning") || t.includes("pending") || t.includes("high")
      || t.includes("divert") || t.includes("approval")) return "warning";
  return "normal";
}

export function DataStream({ events, className, maxLines = 12 }: DataStreamProps) {
  const visible = events.slice(0, maxLines);

  return (
    <div className={cn("flex flex-col justify-end overflow-hidden font-mono t-micro sm:t-label leading-relaxed", className)}>
      <AnimatePresence initial={false}>
        {visible.length === 0 ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.55 }}
            className="text-[var(--text-dim)]"
          >
            NO EVENTS YET — the feed shows real simulation events as they occur.
          </motion.div>
        ) : (
          visible.map((event, index) => {
            const age = visible.length - 1 - index;
            const opacity = Math.max(0.1, 1 - age * 0.15);
            const type = event.type ?? classify(event.text);
            const colorClass =
              type === "critical" ? "text-[var(--critical)]" :
              type === "warning" ? "text-[var(--warning)]" :
              "text-[var(--nominal)]";

            const ts = event.timestamp ? new Date(event.timestamp) : null;
            const timeStr = ts && !isNaN(ts.getTime())
              ? `[${ts.getHours().toString().padStart(2, "0")}:${ts.getMinutes().toString().padStart(2, "0")}:${ts.getSeconds().toString().padStart(2, "0")}] `
              : "";

            return (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, y: 10, filter: "blur(4px)" }}
                animate={{ opacity, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                className={cn("whitespace-nowrap overflow-hidden text-ellipsis", colorClass)}
                style={{ opacity }}
              >
                {timeStr}{event.text}
              </motion.div>
            );
          })
        )}
      </AnimatePresence>
    </div>
  );
}

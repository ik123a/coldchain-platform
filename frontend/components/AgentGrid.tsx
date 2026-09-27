"use client";
import { motion, AnimatePresence } from "framer-motion";

const AGENT_LABELS: Record<string, string> = {
  monitoring: "Monitoring",
  diagnosis: "Diagnosis",
  risk_analyst: "Risk Analyst",
  response_planner: "Response Planner",
  recovery_verifier: "Recovery Verifier",
  reporter: "Reporter",
};
const ORDER = ["monitoring", "diagnosis", "risk_analyst", "response_planner", "recovery_verifier", "reporter"];

export function AgentGrid({ agentsStatus }: { agentsStatus: Record<string, { status: string; note?: string }> }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {ORDER.map(k => {
        const a = agentsStatus[k] || { status: "STANDBY", note: "" };
        const busy = a.status === "ANALYZING" || a.status === "ACTIVE";
        const done = a.status === "COMPLETE" || a.status === "VERIFIED";
        return (
          <div key={k}
               className={`base-card p-2.5 transition-colors ${busy ? "border-[var(--cyan)]/40" : done ? "border-[var(--green)]/40" : ""}`}>
            <div className="flex items-center gap-1.5 t-label font-semibold">
              <span className={`status-dot ${busy ? "pulse" : done ? "" : "amber"}`}
                    style={busy ? { background: "var(--cyan)" } : done ? { background: "var(--green)" } : { background: "var(--text3)" }}></span>
              {AGENT_LABELS[k]}
            </div>
            <AnimatePresence mode="wait">
              <motion.div key={a.status + (a.note || "")}
                          initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                          transition={{ duration: 0.2 }}
                          className={`t-micro mt-0.5 ${busy ? "text-[var(--cyan)]" : done ? "text-[var(--green)]" : "text-[var(--text3)]"}`}>
                {a.status}{a.note ? ` · ${a.note}` : ""}
              </motion.div>
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}

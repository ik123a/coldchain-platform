"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { Activity, Bot, FlaskConical, MapPin, Play, Snowflake, Truck } from "lucide-react";
import { useStore } from "@/lib/store";
import { post } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function Home() {
  const { st } = useStore();
  const router = useRouter();
  const launch = async (autopilot: boolean) => {
    await post(`/api/demo/launch?autopilot=${autopilot}&failure=compressor_failure&after_ticks=10`);
    router.push("/dashboard");
  };
  return (
    <div className="max-w-6xl mx-auto pt-8 fade-in">
      <div className="flex items-start gap-12">
        <div className="flex-1">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <div className="badge badge-cyan mb-5">capstone · T3 · T5 · T7 · T9</div>
            <h1 className="text-6xl font-bold headline mb-3 leading-[1.02]">
              COLDCHAIN<br />RESCUE
            </h1>
            <p className="text-lg text-[var(--text2)] mb-2">Simulate. Detect. Investigate. Recover.</p>
            <p className="text-[13px] text-[var(--text3)] max-w-lg leading-relaxed mb-8">
              AI-powered cold-chain monitoring, simulation, prediction and autonomous incident response.
              Multi-agent operations team — deterministic by default, LLM-ready via environment config.
              No physical hardware required.
            </p>
            <div className="flex gap-3">
              <button onClick={() => launch(true)} className="btn btn-primary text-[14px] px-6 py-3 flex items-center gap-2">
                <Play size={15} /> Launch Demo (autopilot)
              </button>
              <button onClick={() => launch(false)} className="btn text-[14px] px-6 py-3 flex items-center gap-2">
                <FlaskConical size={15} /> Start blank simulation
              </button>
              <Link href="/dashboard" className="btn text-[14px] px-6 py-3 flex items-center gap-2">
                <Activity size={15} /> Dashboard
              </Link>
            </div>
          </motion.div>
          <div className="flex gap-5 mt-10 text-[11px] text-[var(--text2)]">
            <span className="flex items-center gap-1.5"><span className="status-dot pulse"></span> AI SYSTEM ONLINE</span>
            <span className="flex items-center gap-1.5"><span className="status-dot pulse"></span> SIMULATION ENGINE ONLINE</span>
            <span className="flex items-center gap-1.5"><span className="status-dot pulse"></span> DIGITAL TWIN ONLINE</span>
          </div>
        </div>

        <motion.div className="w-80 shrink-0 floaty" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.15 }}>
          <div className="base-card p-4">
            <div className="text-[10px] text-[var(--text3)] tracking-widest mb-3">LIVE DIGITAL TWIN</div>
            <div className="grid grid-cols-2 gap-2">
              {(["Zone A", "Zone B", "Zone C", "Zone D"] as const).map((z, i) => (
                <div key={z} className="zone-glass p-3">
                  <div className="flex items-center justify-between text-[10px] text-[var(--text3)]">
                    {z} <Snowflake size={10} className="text-[var(--cyan)]" />
                  </div>
                  <div className="text-lg font-bold kpi-num mt-1">
                    {st.sim ? st.sim.true_temperature.toFixed(1) : "4." + (i * 3 + 1)}°C
                  </div>
                  <div className={`text-[9px] mt-0.5 ${st.sim && st.sim.true_temperature > st.sim.zone.mx ? "text-[var(--red)]" : "text-[var(--green)]"}`}>
                    {st.sim && st.sim.true_temperature > st.sim.zone.mx ? "CRITICAL" : "HEALTHY"}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-3 text-[10px] text-[var(--text3)]">
              <Truck size={11} /> {st.sim ? `${st.sim.cargo_type.replace("_", " ")} · cargo ${st.sim.cargo_health}%` : "3 facilities · 4 zones · 4 demo shipments"}
            </div>
          </div>
          <div className="base-card p-4 mt-3">
            <div className="text-[10px] text-[var(--text3)] tracking-widest mb-2">AGENTS</div>
            {["Monitoring", "Diagnosis", "Risk Analyst", "Response Planner", "Recovery Verifier", "Reporter"].map((a, i) => (
              <div key={a} className="flex items-center gap-2 text-[11px] text-[var(--text2)] py-1">
                <Bot size={11} className={i === 0 ? "text-[var(--cyan)]" : "text-[var(--text3)]"} /> {a}
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import { 
  Activity, ArrowRight, Bot, CheckCircle2, ChevronRight, Compass, 
  Droplets, ExternalLink, Flame, FlaskConical, Layers, MapPin, 
  Navigation, Play, ShieldAlert, ShieldCheck, Snowflake, Sparkles, Thermometer, Truck, Zap 
} from "lucide-react";
import { useStore } from "@/lib/store";
import { post } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function Home() {
  const { st } = useStore();
  const router = useRouter();

  const launch = async (autopilot: boolean) => {
    await post(`/api/demo/launch?autopilot=${autopilot}&failure=compressor_failure&after_ticks=10`);
    router.push("/live-map");
  };

  return (
    <div className="max-w-6xl mx-auto space-y-24 pb-28 text-slate-100">
      
      {/* 1. HERO SECTION */}
      <section className="relative pt-12 md:pt-20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-12">
          <div className="flex-1 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0E121A] border border-[#1E2638] text-[11px] font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-slate-400">DIGITAL TWIN 2.0</span>
              <span className="text-slate-600">·</span>
              <span className="text-cyan-400 font-semibold">ARRHENIUS RESCUE AGENTS</span>
            </div>

            <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-white leading-[1.05]">
              Keep every shipment inside the safe zone.
            </h1>

            <p className="text-lg md:text-xl text-slate-400 max-w-xl font-normal leading-relaxed">
              AI for the moments cold-chain operations go wrong. Real-time reefer kinetics, thermal degradation forecasting, and autonomous emergency rerouting to cold storage.
            </p>

            <div className="flex flex-wrap items-center gap-3.5 pt-2">
              <button
                onClick={() => launch(true)}
                className="px-6 py-3.5 rounded-xl font-semibold text-sm bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-2 transition-all shadow-lg shadow-cyan-900/30">
                <Play size={16} fill="currentColor" /> Launch Rescue Demo
              </button>

              <Link
                href="/live-map"
                className="px-6 py-3.5 rounded-xl font-semibold text-sm bg-[#141B26] hover:bg-[#1E2638] text-slate-200 border border-[#1E2638] flex items-center gap-2 transition-colors">
                <Navigation size={16} className="text-cyan-400" /> Open Live Map
              </Link>

              <Link
                href="/design-reference-board"
                className="px-5 py-3.5 rounded-xl font-semibold text-sm text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors">
                <Layers size={16} /> Reference Board <ChevronRight size={14} />
              </Link>
            </div>

            {/* Micro Trust & Telemetry Bar */}
            <div className="flex items-center gap-6 pt-6 text-xs text-slate-500 font-mono border-t border-[#1E2638]/70">
              <span className="flex items-center gap-1.5 text-slate-300">
                <ShieldCheck size={14} className="text-emerald-400" /> 0% Cargo Loss
              </span>
              <span className="flex items-center gap-1.5 text-slate-300">
                <Activity size={14} className="text-cyan-400" /> &lt;5s Breach Response
              </span>
              <span className="flex items-center gap-1.5 text-slate-300">
                <Thermometer size={14} className="text-amber-400" /> Arrhenius Shelf-Life Model
              </span>
            </div>
          </div>

          {/* Interactive Floating Telemetry Card */}
          <div className="w-full lg:w-96 shrink-0">
            <div className="relative rounded-2xl bg-[#0E121A] border border-[#1E2638] p-5 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-[#1E2638] pb-3">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
                  <span className="text-xs font-mono font-bold text-white">TRUCK-104</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
                    NOMINAL
                  </span>
                </div>
                <span className="text-[11px] font-mono text-slate-500">CORRIDOR 8</span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="text-[10px] font-mono text-slate-400">INSIDE CORE</div>
                  <div className="text-2xl font-bold font-mono text-white mt-1">4.8°C</div>
                  <div className="text-[10px] text-emerald-400 font-mono mt-0.5">Target: 2.0–8.0°C</div>
                </div>
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="text-[10px] font-mono text-slate-400">OUTSIDE AMBIENT</div>
                  <div className="text-2xl font-bold font-mono text-amber-400 mt-1">41.8°C</div>
                  <div className="text-[10px] text-amber-500/80 font-mono mt-0.5">Heatwave Warning</div>
                </div>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>Compressor Health</span>
                  <span className="text-emerald-400">94%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-emerald-400 w-[94%]"></div>
                </div>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>Remaining Shelf Life (RSL)</span>
                  <span className="text-cyan-400">18.4 hrs</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-cyan-400 w-[82%]"></div>
                </div>
              </div>

              <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638] text-xs font-mono flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-1.5">
                  <MapPin size={13} className="text-cyan-400" /> Dest: Dock 12
                </span>
                <span className="text-slate-400">ETA 14 min</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. THE COLD-CHAIN PROBLEM */}
      <section className="space-y-6">
        <div className="border-t border-[#1E2638] pt-12">
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider mb-2">OPERATIONAL REALITY</div>
          <h2 className="text-3xl font-bold text-white tracking-tight">
            When ambient heat hits 42°C, traditional logistics fail silently.
          </h2>
          <p className="text-sm text-slate-400 max-w-2xl mt-2 leading-relaxed">
            A single compressor degradation can cause catastrophic spoilage before drivers even notice a cockpit alert. 
            ColdChain Rescue uses Arrhenius reaction kinetics to calculate true remaining shelf-life in real time.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-amber-950/60 border border-amber-800/40 text-amber-400 grid place-items-center">
              <Flame size={20} />
            </div>
            <h3 className="text-base font-bold text-white">42°C Outside Heat</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Extreme environmental heat puts exponential load on reefer compressors. A 15% mechanical degradation triggers rapid internal temperature creep.
            </p>
          </div>

          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-rose-950/60 border border-rose-800/40 text-rose-400 grid place-items-center">
              <ShieldAlert size={20} />
            </div>
            <h3 className="text-base font-bold text-white">Arrhenius Degradation</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Biological degradation accelerates exponentially: <code className="text-rose-300">k(T) = A·exp(-Ea/RT)</code>. 
              Our Arrhenius kinetics engine computes exact time-to-critical countdowns.
            </p>
          </div>

          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-950/60 border border-emerald-800/40 text-emerald-400 grid place-items-center">
              <Navigation size={20} />
            </div>
            <h3 className="text-base font-bold text-white">Autonomous Rescue</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              When breach is projected in under 10 minutes, the multi-agent supervisor dynamically searches candidate cold hubs, reserves dock bays, and recalculates the route.
            </p>
          </div>
        </div>
      </section>

      {/* 3. MULTI-AGENT STATE PIPELINE */}
      <section className="bg-[#0E121A] rounded-2xl border border-[#1E2638] p-8 space-y-6">
        <div>
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider mb-1">DECISION ARCHITECTURE</div>
          <h3 className="text-2xl font-bold text-white">The 8-Stage Autonomous Rescue Loop</h3>
          <p className="text-xs text-slate-400 mt-1">Deterministic speed (&lt;5ms reservation) with optional LLM reasoning explanation.</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 text-xs font-mono">
          {[
            { stage: "01", name: "MONITOR", desc: "Kalman gate", col: "text-emerald-400" },
            { stage: "02", name: "DIAGNOSE", desc: "Compressor wear", col: "text-amber-400" },
            { stage: "03", name: "PREDICT", desc: "Arrhenius RSL", col: "text-rose-400" },
            { stage: "04", name: "SEVERITY", desc: "Critical Lane", col: "text-rose-400" },
            { stage: "05", name: "SEARCH", desc: "5 Cold Hubs", col: "text-cyan-400" },
            { stage: "06", name: "RESERVE", desc: "Bay 3 pre-chill", col: "text-cyan-400" },
            { stage: "07", name: "REROUTE", desc: "Detour active", col: "text-emerald-400" },
            { stage: "08", name: "VERIFY", desc: "0% loss verified", col: "text-emerald-400" },
          ].map(s => (
            <div key={s.stage} className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638] space-y-1">
              <div className="text-[10px] text-slate-500">{s.stage}</div>
              <div className={`font-bold ${s.col}`}>{s.name}</div>
              <div className="text-[10px] text-slate-400 truncate">{s.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. VISUAL REFERENCE CALLOUT */}
      <section className="bg-gradient-to-r from-[#0E121A] to-[#141B26] rounded-2xl border border-[#1E2638] p-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400">
            <Sparkles size={14} /> GEMINI & VEO REFERENCE REPOSITORY
          </div>
          <h3 className="text-xl font-bold text-white">Explore the 28 Image & 15 Motion Visual References</h3>
          <p className="text-xs text-slate-400 max-w-xl leading-relaxed">
            Every screen layout, telemetry card, and motion curve was evaluated through Gemini's Design Critique Agent 
            before interface coding commenced.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <Link
            href="/design-references"
            className="px-5 py-2.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors">
            Reference Library
          </Link>
          <Link
            href="/design-reference-board"
            className="px-4 py-2.5 rounded-lg text-xs font-semibold bg-[#1C2433] hover:bg-[#253043] text-slate-200 border border-[#1E2638] transition-colors">
            Moodboard
          </Link>
        </div>
      </section>
    </div>
  );
}

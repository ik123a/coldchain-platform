"use client";
import { useState } from "react";
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
  const [activeVideo, setActiveVideo] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);

  // Pick live distressed vehicle if exists, else first vehicle or default telemetry
  const vehicles = (st as any)?.fleetVehicles || (st as any)?.vehicles || [];
  const liveTruck = vehicles.find((v: any) => v.status === "CRITICAL" || v.status === "AT_RISK") || vehicles[0];

  const launch = async (autopilot: boolean) => {
    setDemoLoading(true);
    try {
      await post(`/api/demo/launch?autopilot=${autopilot}&failure=compressor_failure&after_ticks=10`);
      router.push("/live-map");
    } catch {
      router.push("/live-map");
    } finally {
      setDemoLoading(false);
    }
  };

  const sampleVideos = [
    {
      id: "vid-01",
      src: "/design-references/videos/vid-01-live-map-push.mp4",
      thumb: "/design-references/videos/vid-01-live-map-push-thumb.png",
      title: "Centering Camera & Route Push",
      tag: "CAMERA KINETICS"
    },
    {
      id: "vid-04",
      src: "/design-references/videos/vid-04-ai-route-decision.mp4",
      thumb: "/design-references/videos/vid-04-ai-route-decision-thumb.png",
      title: "Multi-Agent Detour Calculation",
      tag: "AI DECISION"
    },
    {
      id: "vid-05",
      src: "/design-references/videos/vid-05-rerouting-transition.mp4",
      thumb: "/design-references/videos/vid-05-rerouting-transition-thumb.png",
      title: "Real-Time Vector Rerouting",
      tag: "TELEMETRY"
    },
    {
      id: "vid-08",
      src: "/design-references/videos/vid-08-cargo-transfer.mp4",
      thumb: "/design-references/videos/vid-08-cargo-transfer-thumb.png",
      title: "Cross-Truck Offload Sequence",
      tag: "RECOVERY"
    },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-24 pb-28 text-slate-100 relative">
      
      {/* 1. HERO SECTION WITH ATMOSPHERIC VEO BACKGROUND */}
      <section className="relative pt-8 md:pt-16 overflow-hidden">
        {/* Ambient Looping Video Layer */}
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-[120vw] h-[550px] overflow-hidden pointer-events-none -z-10 select-none opacity-25">
          <video 
            autoPlay 
            loop 
            muted 
            playsInline 
            className="w-full h-full object-cover filter blur-[2px] brightness-75 scale-105"
          >
            <source src="/design-references/videos/vid-01-live-map-push.mp4" type="video/mp4" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-b from-[#080A0F]/60 via-[#080A0F]/85 to-[#080A0F]"></div>
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_15%,_#080A0F_80%)]"></div>
        </div>

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-12 relative z-10">
          <div className="flex-1 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0E121A]/90 backdrop-blur-md border border-[#1E2638] text-[11px] font-mono shadow-lg">
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
                disabled={demoLoading}
                className="px-6 py-3.5 rounded-xl font-semibold text-sm bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-2 transition-all shadow-lg shadow-cyan-900/30 disabled:opacity-50">
                <Play size={16} fill="currentColor" /> {demoLoading ? "Initializing Simulation..." : "Launch Rescue Demo"}
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

          {/* Interactive Floating Telemetry Card (Live Connected) */}
          <div className="w-full lg:w-96 shrink-0">
            <div className="relative rounded-2xl bg-[#0E121A]/95 backdrop-blur-md border border-[#1E2638] p-5 shadow-2xl space-y-4 hover:border-cyan-500/40 transition-colors">
              <div className="flex items-center justify-between border-b border-[#1E2638] pb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${liveTruck?.status === "CRITICAL" ? "bg-rose-400 animate-ping" : liveTruck?.status === "AT_RISK" ? "bg-amber-400 animate-pulse" : "bg-emerald-400"}`}></span>
                  <span className="text-xs font-mono font-bold text-white">{liveTruck?.vehicle_id || "TRUCK-104"}</span>
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${liveTruck?.status === "CRITICAL" ? "bg-rose-950/60 text-rose-400 border-rose-800/40" : liveTruck?.status === "AT_RISK" ? "bg-amber-950/60 text-amber-400 border-amber-800/40" : "bg-emerald-950/60 text-emerald-400 border-emerald-800/40"}`}>
                    {liveTruck?.status || "NOMINAL"}
                  </span>
                </div>
                <span className="text-[11px] font-mono text-slate-500">CORRIDOR 8</span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="text-[10px] font-mono text-slate-400">INSIDE CORE</div>
                  <div className={`text-2xl font-bold font-mono mt-1 ${liveTruck && liveTruck.temperature > 8 ? "text-rose-400" : liveTruck && liveTruck.temperature > 6 ? "text-amber-400" : "text-white"}`}>
                    {liveTruck ? liveTruck.temperature.toFixed(1) : "4.8"}°C
                  </div>
                  <div className="text-[10px] text-emerald-400 font-mono mt-0.5">Target: 2.0–8.0°C</div>
                </div>
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="text-[10px] font-mono text-slate-400">OUTSIDE AMBIENT</div>
                  <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
                    {liveTruck?.ambient_temperature ? liveTruck.ambient_temperature.toFixed(1) : "41.8"}°C
                  </div>
                  <div className="text-[10px] text-amber-500/80 font-mono mt-0.5">Heatwave Active</div>
                </div>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>Compressor Health</span>
                  <span className={liveTruck?.compressor_health && liveTruck.compressor_health < 50 ? "text-rose-400 font-bold" : "text-emerald-400"}>
                    {liveTruck?.compressor_health ? Math.round(liveTruck.compressor_health) : 94}%
                  </span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div 
                    className={`h-full ${liveTruck?.compressor_health && liveTruck.compressor_health < 50 ? "bg-rose-500" : "bg-emerald-400"}`} 
                    style={{ width: `${liveTruck?.compressor_health || 94}%` }}
                  ></div>
                </div>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-[11px] font-mono text-slate-400">
                  <span>Remaining Shelf Life (RSL)</span>
                  <span className="text-cyan-400">
                    {liveTruck ? (liveTruck.remaining_shelf_life_hours || 18.4).toFixed(1) : "18.4"} hrs
                  </span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div 
                    className="h-full bg-cyan-400"
                    style={{ width: `${Math.min(100, Math.max(10, ((liveTruck?.remaining_shelf_life_hours || 18.4) / 24) * 100))}%` }}
                  ></div>
                </div>
              </div>

              <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638] text-xs font-mono flex items-center justify-between text-slate-300">
                <span className="flex items-center gap-1.5">
                  <MapPin size={13} className="text-cyan-400" /> Dest: {liveTruck?.destination || "Dock 12 (Phoenix Hub)"}
                </span>
                <span className="text-slate-400">ETA {liveTruck?.eta_minutes ? `${Math.round(liveTruck.eta_minutes)} min` : "14 min"}</span>
              </div>

              <Link
                href={`/live-map?truck=${liveTruck?.vehicle_id || "TRUCK-104"}`}
                className="block text-center py-2 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 border border-cyan-800/50 text-cyan-400 text-xs font-mono font-semibold transition-colors">
                Track Vehicle Telemetry →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 2. THE COLD-CHAIN PROBLEM & ARRHENIUS DEGRADATION KINETICS */}
      <section className="space-y-6">
        <div className="border-t border-[#1E2638] pt-12">
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider mb-2">THERMAL PHYSICS ENGINE</div>
          <h2 className="text-3xl md:text-4xl font-bold text-white tracking-tight">
            When ambient heat hits 42°C, traditional logistics fail silently.
          </h2>
          <p className="text-sm md:text-base text-slate-400 max-w-2xl mt-2 leading-relaxed">
            A single compressor mechanical failure causes rapid temperature creep inside insulated trailers. 
            ColdChain Rescue integrates the Arrhenius reaction equation to model real biological spoilage curves.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-amber-950/60 border border-amber-800/40 text-amber-400 grid place-items-center">
              <Flame size={20} />
            </div>
            <h3 className="text-base font-bold text-white">42°C Outside Heatwave</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Extreme ambient heat puts exponential load on reefer compressors. A 15% mechanical degradation triggers rapid thermal runaway inside cargo trailers.
            </p>
          </div>

          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-rose-950/60 border border-rose-800/40 text-rose-400 grid place-items-center">
              <ShieldAlert size={20} />
            </div>
            <h3 className="text-base font-bold text-white">Arrhenius Degradation</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Biological breakdown accelerates exponentially: <code className="text-rose-300 font-mono">k(T) = A·exp(-Ea/RT)</code>. 
              Our Arrhenius engine calculates exact minutes until irreversible protein or active ingredient spoilage.
            </p>
          </div>

          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-950/60 border border-emerald-800/40 text-emerald-400 grid place-items-center">
              <Navigation size={20} />
            </div>
            <h3 className="text-base font-bold text-white">Autonomous Rescue</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              When breach is projected within 10 minutes, the multi-agent supervisor searches candidate cold hubs, reserves dock bays, and recalculates the detour vector.
            </p>
          </div>
        </div>

        {/* Arrhenius Shelf-Life Rate Comparison Matrix */}
        <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#1E2638] pb-3">
            <div>
              <span className="text-xs font-mono text-cyan-400 font-bold uppercase">KINETICS BENCHMARK</span>
              <h4 className="text-sm font-semibold text-white mt-0.5">Thermal Degradation Rate Multiplier vs Temperature</h4>
            </div>
            <div className="text-[11px] font-mono text-slate-500">
              Ea = 78.4 kJ/mol · Reference: 4.0°C Nominal
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded-xl bg-[#141B26] border border-emerald-800/40">
              <div className="text-slate-400 text-[10px]">4.0°C (NOMINAL)</div>
              <div className="text-xl font-bold text-emerald-400 mt-1">1.0x</div>
              <div className="text-[10px] text-slate-400 mt-1">Baseline shelf-life: 24.0h</div>
            </div>
            <div className="p-3 rounded-xl bg-[#141B26] border border-amber-800/40">
              <div className="text-slate-400 text-[10px]">8.0°C (THRESHOLD)</div>
              <div className="text-xl font-bold text-amber-400 mt-1">1.6x</div>
              <div className="text-[10px] text-amber-400/80 mt-1">Safe shelf-life: 14.8h</div>
            </div>
            <div className="p-3 rounded-xl bg-[#141B26] border border-rose-800/40">
              <div className="text-slate-400 text-[10px]">12.0°C (BREACH)</div>
              <div className="text-xl font-bold text-rose-400 mt-1">4.2x</div>
              <div className="text-[10px] text-rose-400/80 mt-1">Critical threshold: 5.7h</div>
            </div>
            <div className="p-3 rounded-xl bg-[#141B26] border border-rose-950 bg-rose-950/20">
              <div className="text-slate-400 text-[10px]">18.0°C (EXCURSION)</div>
              <div className="text-xl font-bold text-rose-500 mt-1">11.8x</div>
              <div className="text-[10px] text-rose-500 mt-1">Catastrophic loss in &lt;2.0h</div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. WHAT-IF TRAJECTORY BIFURCATION */}
      <section className="space-y-6">
        <div className="border-t border-[#1E2638] pt-12">
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider mb-2">DUAL-TRAJECTORY FORECASTING</div>
          <h2 className="text-3xl font-bold text-white tracking-tight">
            Compare the Status Quo vs. Autonomous Rescue
          </h2>
          <p className="text-sm text-slate-400 max-w-2xl mt-2 leading-relaxed">
            When mechanical failure strikes, two futures diverge. Our secondary physics clone computes the exact financial and cargo impact of doing nothing versus executing autonomous rerouting.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Future A: Do Nothing */}
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-rose-900/40 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                <span className="text-xs font-mono font-bold text-rose-400">TRAJECTORY A: STATUS QUO</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950/80 text-rose-400 border border-rose-800">
                100% CARGO LOSS
              </span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Vehicle continues on original 42-minute route to Phoenix Central. Core temperature climbs unchecked past the 8.0°C safe threshold within 12 minutes.
            </p>

            <div className="grid grid-cols-3 gap-3 text-xs font-mono bg-[#141B26] p-3 rounded-xl border border-[#1E2638]">
              <div>
                <div className="text-[10px] text-slate-500">PEAK TEMP</div>
                <div className="text-base font-bold text-rose-400 mt-0.5">14.8°C</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">SPOILAGE TIME</div>
                <div className="text-base font-bold text-rose-400 mt-0.5">18 min</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">EST. LOSS</div>
                <div className="text-base font-bold text-rose-400 mt-0.5">$145,000</div>
              </div>
            </div>
          </div>

          {/* Future B: Autonomous Detour */}
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-emerald-900/40 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
                <span className="text-xs font-mono font-bold text-emerald-400">TRAJECTORY B: AUTONOMOUS DETOUR</span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                0% CARGO LOSS
              </span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Supervisor diverts to ColdHub South (ETA 9.2 min). Pre-chill bay 03 auto-reserved at 2.0°C. Secondary reefer docked before thermal breach threshold.
            </p>

            <div className="grid grid-cols-3 gap-3 text-xs font-mono bg-[#141B26] p-3 rounded-xl border border-[#1E2638]">
              <div>
                <div className="text-[10px] text-slate-500">RECOVERY TEMP</div>
                <div className="text-base font-bold text-emerald-400 mt-0.5">5.2°C</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">ARRIVAL TIME</div>
                <div className="text-base font-bold text-emerald-400 mt-0.5">9.2 min</div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500">SAVED VALUE</div>
                <div className="text-base font-bold text-emerald-400 mt-0.5">$145,000</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. MULTI-AGENT RESCUE PIPELINE */}
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

      {/* 5. CINEMATIC VEO VIDEO REEL & REFERENCE SHOWCASE */}
      <section className="space-y-6">
        <div className="border-t border-[#1E2638] pt-12 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="text-xs font-mono text-cyan-400 uppercase tracking-wider mb-2">CINEMATIC VISUAL REPOSITORY</div>
            <h2 className="text-3xl font-bold text-white tracking-tight">
              Veo Motion References & Design Systems
            </h2>
            <p className="text-sm text-slate-400 max-w-2xl mt-1">
              15 generated Veo motion sequences and 28 high-precision interface references grounding the product architecture.
            </p>
          </div>
          <Link 
            href="/design-references" 
            className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 shrink-0">
            View All 43 References <ArrowRight size={14} />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {sampleVideos.map(v => (
            <div 
              key={v.id}
              className="group relative rounded-xl bg-[#0E121A] border border-[#1E2638] overflow-hidden hover:border-cyan-500/50 transition-all">
              <div className="relative aspect-video bg-black overflow-hidden">
                <video 
                  src={v.src}
                  poster={v.thumb}
                  muted 
                  loop 
                  playsInline
                  onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
                  onMouseLeave={e => { const vid = (e.target as HTMLVideoElement); vid.pause(); vid.currentTime = 0; }}
                  className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-300"
                />
                <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/70 backdrop-blur-sm text-[9px] font-mono text-cyan-400 border border-cyan-800/40">
                  {v.tag}
                </div>
              </div>
              <div className="p-3">
                <div className="text-xs font-semibold text-white truncate">{v.title}</div>
                <div className="text-[10px] font-mono text-slate-500 mt-1 flex items-center justify-between">
                  <span>VEO 2.0 MOTION</span>
                  <span className="text-cyan-400 group-hover:underline flex items-center gap-1">Hover to play</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 6. CALL TO ACTION FOOTER */}
      <section className="bg-gradient-to-r from-[#0E121A] to-[#141B26] rounded-2xl border border-[#1E2638] p-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400">
            <Sparkles size={14} /> READY FOR AUTONOMOUS DEMO
          </div>
          <h3 className="text-2xl font-bold text-white">Experience ColdChain Rescue Live</h3>
          <p className="text-xs text-slate-400 max-w-xl leading-relaxed">
            Launch the live twin with simulated compressor failure, watch the Arrhenius rate surge, and observe sub-second autonomous hub diversion.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => launch(true)}
            className="px-6 py-3 rounded-xl text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-all shadow-lg shadow-cyan-900/30 flex items-center gap-2">
            <Play size={14} fill="currentColor" /> Run Demo Now
          </button>
          <Link
            href="/simulation"
            className="px-5 py-3 rounded-xl text-xs font-semibold bg-[#1C2433] hover:bg-[#253043] text-slate-200 border border-[#1E2638] transition-colors">
            Simulation Controls
          </Link>
        </div>
      </section>
    </div>
  );
}


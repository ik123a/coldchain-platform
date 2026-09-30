"use client";
import { useState, useRef } from "react";
import Link from "next/link";
import { 
  Activity, ArrowRight, ChevronRight, 
  Flame, MapPin, Navigation,
  Play, ShieldAlert, ShieldCheck, Thermometer, Zap, Sparkles 
} from "lucide-react";
import { useStore } from "@/lib/store";
import { post } from "@/lib/api";
import { useRouter } from "next/navigation";
import { ParticleField } from "@/components/ui/particle-field";
import { ShimmerText } from "@/components/ui/shimmer-text";
import { StatusBeacon } from "@/components/ui/status-beacon";
import { RetroGrid } from "@/components/ui/retro-grid";
import { ShineBorder } from "@/components/ui/shine-border";
import { AnimatedBeam } from "@/components/ui/animated-beam";
import OpsHero from "@/components/ops/OpsHero";
import OpsCapabilities from "@/components/ops/OpsCapabilities";

export default function Home() {
  const { st } = useStore();
  const router = useRouter();
  const [activeVideo, setActiveVideo] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);

  // Pick live distressed vehicle if exists, else first vehicle or default telemetry
  const vehicles = (st as any)?.fleetVehicles || (st as any)?.vehicles || [];
  const liveTruck = vehicles.find((v: any) => v?.status === "CRITICAL" || v?.status === "AT_RISK") || vehicles[0];

  const truckTemp = liveTruck?.refrigeration?.temperature ?? (typeof liveTruck?.temperature === "number" ? liveTruck.temperature : 4.8);
  const truckAmbient = liveTruck?.outside_temperature ?? (typeof liveTruck?.ambient_temperature === "number" ? liveTruck.ambient_temperature : 41.8);
  const truckCompHealth = liveTruck?.refrigeration?.cooling_efficiency ?? liveTruck?.vehicle?.vehicle_health ?? (typeof liveTruck?.compressor_health === "number" ? liveTruck.compressor_health : 94);
  const truckRsl = typeof liveTruck?.remaining_shelf_life_hours === "number" 
    ? liveTruck.remaining_shelf_life_hours 
    : (typeof liveTruck?.cargo?.time_to_critical_min === "number" ? liveTruck.cargo.time_to_critical_min / 60 : 18.4);
  const truckDest = liveTruck?.trip?.destination_id || liveTruck?.destination || "Dock 12 (Phoenix Hub)";
  const truckEta = liveTruck?.trip?.eta_min ?? liveTruck?.eta_minutes ?? 14;

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
    <div className="max-w-6xl mx-auto space-y-24 pb-28 text-[var(--surface-inset)] relative">
      
      {/* 1. HERO — ops redesign (references: DAQ numbered sections, Cerebrium liquid depth) */}
      <OpsHero onLaunch={launch} loading={demoLoading} />

      <OpsCapabilities />
      {/* 2. THE COLD-CHAIN PROBLEM & ARRHENIUS DEGRADATION KINETICS */}
      <section className="space-y-6">
        <div className="border-t border-[var(--border)] pt-12">
          <div className="t-body-sm font-mono text-[var(--accent)] uppercase tracking-wider mb-2">THERMAL PHYSICS ENGINE</div>
          <h2 className="t-metric-lg md:t-display font-bold text-[var(--text)] tracking-tight">
            When ambient heat hits 42°C, traditional logistics fail silently.
          </h2>
          <p className="t-body md:t-title text-[var(--text-dim)] max-w-2xl mt-2 leading-relaxed">
            A single compressor mechanical failure causes rapid temperature creep inside insulated trailers. 
            ColdChain Rescue integrates the Arrhenius reaction equation to model real biological spoilage curves.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-[var(--surface-raised)] p-6 rounded-2xl border border-[var(--border)] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--surface-inset)] border border-[var(--border)] text-[var(--warning)] grid place-items-center">
              <Flame size={20} />
            </div>
            <h3 className="t-title font-bold text-[var(--text)]">42°C Outside Heatwave</h3>
            <p className="t-body-sm text-[var(--text-dim)] leading-relaxed">
              Extreme ambient heat puts exponential load on reefer compressors. A 15% mechanical degradation triggers rapid thermal runaway inside cargo trailers.
            </p>
          </div>

          <div className="bg-[var(--surface-raised)] p-6 rounded-2xl border border-[var(--border)] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--surface-inset)] border border-[var(--border)] text-[var(--critical)] grid place-items-center">
              <ShieldAlert size={20} />
            </div>
            <h3 className="t-title font-bold text-[var(--text)]">Arrhenius Degradation</h3>
            <p className="t-body-sm text-[var(--text-dim)] leading-relaxed">
              Biological breakdown accelerates exponentially: <code className="text-[var(--critical)] font-mono">k(T) = A·exp(-Ea/RT)</code>. 
              Our Arrhenius engine calculates exact minutes until irreversible protein or active ingredient spoilage.
            </p>
          </div>

          <div className="bg-[var(--surface-raised)] p-6 rounded-2xl border border-[var(--border)] space-y-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--surface-inset)] border border-[var(--border)] text-[var(--nominal)] grid place-items-center">
              <Navigation size={20} />
            </div>
            <h3 className="t-title font-bold text-[var(--text)]">Autonomous Rescue</h3>
            <p className="t-body-sm text-[var(--text-dim)] leading-relaxed">
              When breach is projected within 10 minutes, the multi-agent supervisor searches candidate cold hubs, reserves dock bays, and recalculates the detour vector.
            </p>
          </div>
        </div>

        {/* Arrhenius Shelf-Life Rate Comparison Matrix */}
        <div className="bg-[var(--surface-raised)] p-6 rounded-2xl border border-[var(--border)] space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[var(--border)] pb-3">
            <div>
              <span className="t-body-sm font-mono text-[var(--accent)] font-bold uppercase">KINETICS BENCHMARK</span>
              <h4 className="t-body font-semibold text-[var(--text)] mt-0.5">Thermal Degradation Rate Multiplier vs Temperature</h4>
            </div>
            <div className="t-label font-mono text-[var(--text-dim)]">
              Ea = 78.4 kJ/mol · Reference: 4.0°C Nominal
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 t-body-sm font-mono">
            <div className="p-3 rounded-xl bg-[var(--surface-card)] border border-[var(--border)]">
              <div className="text-[var(--text-dim)] t-body-sm">4.0°C (NOMINAL)</div>
              <div className="t-metric font-bold text-[var(--nominal)] mt-1">1.0x</div>
              <div className="t-body-sm text-[var(--text-dim)] mt-1">Baseline shelf-life: 24.0h</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--surface-card)] border border-[var(--border)]">
              <div className="text-[var(--text-dim)] t-body-sm">8.0°C (THRESHOLD)</div>
              <div className="t-metric font-bold text-[var(--warning)] mt-1">1.6x</div>
              <div className="t-body-sm text-[var(--warning)] mt-1">Safe shelf-life: 14.8h</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--surface-card)] border border-[var(--border)]">
              <div className="text-[var(--text-dim)] t-body-sm">12.0°C (BREACH)</div>
              <div className="t-metric font-bold text-[var(--critical)] mt-1">4.2x</div>
              <div className="t-body-sm text-[var(--critical)] mt-1">Critical threshold: 5.7h</div>
            </div>
            <div className="p-3 rounded-xl bg-[var(--surface-card)] border border-[var(--surface-inset)] bg-[var(--surface-inset)]">
              <div className="text-[var(--text-dim)] t-body-sm">18.0°C (EXCURSION)</div>
              <div className="t-metric font-bold text-[var(--critical)] mt-1">11.8x</div>
              <div className="t-body-sm text-[var(--critical)] mt-1">Catastrophic loss in &lt;2.0h</div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. WHAT-IF TRAJECTORY BIFURCATION */}
      <section className="space-y-6">
        <div className="border-t border-[var(--border)] pt-12">
          <div className="t-body-sm font-mono text-[var(--accent)] uppercase tracking-wider mb-2">DUAL-TRAJECTORY FORECASTING</div>
          <h2 className="t-metric-lg font-bold text-[var(--text)] tracking-tight">
            Compare the Status Quo vs. Autonomous Rescue
          </h2>
          <p className="t-body text-[var(--text-dim)] max-w-2xl mt-2 leading-relaxed">
            When mechanical failure strikes, two futures diverge. Our secondary physics clone computes the exact financial and cargo impact of doing nothing versus executing autonomous rerouting.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Future A: Do Nothing */}
          <div className="bg-[var(--surface-raised)] p-6 rounded-2xl border border-[var(--surface-inset)] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--critical)]"></span>
                <span className="t-body-sm font-mono font-bold text-[var(--critical)]">TRAJECTORY A: STATUS QUO</span>
              </div>
              <span className="t-micro font-mono px-2 py-0.5 rounded bg-[var(--surface-inset)] text-[var(--critical)] border border-[var(--border)]">
                100% CARGO LOSS
              </span>
            </div>

            <p className="t-body-sm text-[var(--text-dim)] leading-relaxed">
              Vehicle continues on original 42-minute route to Phoenix Central. Core temperature climbs unchecked past the 8.0°C safe threshold within 12 minutes.
            </p>

            <div className="grid grid-cols-3 gap-3 t-body-sm font-mono bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
              <div>
                <div className="t-micro text-[var(--text-dim)]">PEAK TEMP</div>
                <div className="t-title font-bold text-[var(--critical)] mt-0.5">14.8°C</div>
              </div>
              <div>
                <div className="t-micro text-[var(--text-dim)]">SPOILAGE TIME</div>
                <div className="t-title font-bold text-[var(--critical)] mt-0.5">18 min</div>
              </div>
              <div>
                <div className="t-micro text-[var(--text-dim)]">EST. LOSS</div>
                <div className="t-title font-bold text-[var(--critical)] mt-0.5">$145,000</div>
              </div>
            </div>
          </div>

          {/* Future B: Autonomous Detour */}
          <div className="bg-[var(--surface-raised)] p-6 rounded-2xl border border-[var(--surface-inset)] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[var(--nominal)]"></span>
                <span className="t-body-sm font-mono font-bold text-[var(--nominal)]">TRAJECTORY B: AUTONOMOUS DETOUR</span>
              </div>
              <span className="t-micro font-mono px-2 py-0.5 rounded bg-[var(--surface-inset)] text-[var(--nominal)] border border-[var(--border)]">
                0% CARGO LOSS
              </span>
            </div>

            <p className="t-body-sm text-[var(--text-dim)] leading-relaxed">
              Supervisor diverts to ColdHub South (ETA 9.2 min). Pre-chill bay 03 auto-reserved at 2.0°C. Secondary reefer docked before thermal breach threshold.
            </p>

            <div className="grid grid-cols-3 gap-3 t-body-sm font-mono bg-[var(--surface-card)] p-3 rounded-xl border border-[var(--border)]">
              <div>
                <div className="t-micro text-[var(--text-dim)]">RECOVERY TEMP</div>
                <div className="t-title font-bold text-[var(--nominal)] mt-0.5">5.2°C</div>
              </div>
              <div>
                <div className="t-micro text-[var(--text-dim)]">ARRIVAL TIME</div>
                <div className="t-title font-bold text-[var(--nominal)] mt-0.5">9.2 min</div>
              </div>
              <div>
                <div className="t-micro text-[var(--text-dim)]">SAVED VALUE</div>
                <div className="t-title font-bold text-[var(--nominal)] mt-0.5">$145,000</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. MULTI-AGENT RESCUE PIPELINE */}
      <section className="bg-[var(--surface-raised)] rounded-2xl border border-[var(--border)] p-8 space-y-6">
        <div>
          <div className="t-body-sm font-mono text-[var(--accent)] uppercase tracking-wider mb-1">DECISION ARCHITECTURE</div>
          <h3 className="t-metric-lg font-bold text-[var(--text)]">The 8-Stage Autonomous Rescue Loop</h3>
          <p className="t-body-sm text-[var(--text-dim)] mt-1">Deterministic speed (&lt;5ms reservation) with optional LLM reasoning explanation.</p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 t-body-sm font-mono">
          {[
            { stage: "01", name: "MONITOR", desc: "Kalman gate", col: "text-[var(--nominal)]" },
            { stage: "02", name: "DIAGNOSE", desc: "Compressor wear", col: "text-[var(--warning)]" },
            { stage: "03", name: "PREDICT", desc: "Arrhenius RSL", col: "text-[var(--critical)]" },
            { stage: "04", name: "SEVERITY", desc: "Critical Lane", col: "text-[var(--critical)]" },
            { stage: "05", name: "SEARCH", desc: "5 Cold Hubs", col: "text-[var(--accent)]" },
            { stage: "06", name: "RESERVE", desc: "Bay 3 pre-chill", col: "text-[var(--accent)]" },
            { stage: "07", name: "REROUTE", desc: "Detour active", col: "text-[var(--nominal)]" },
            { stage: "08", name: "VERIFY", desc: "0% loss verified", col: "text-[var(--nominal)]" },
          ].map(s => (
            <div key={s.stage} className="bg-[var(--surface-card)] p-3 rounded-lg border border-[var(--border)] space-y-1">
              <div className="t-micro text-[var(--text-dim)]">{s.stage}</div>
              <div className={`font-bold ${s.col}`}>{s.name}</div>
              <div className="t-micro text-[var(--text-dim)] truncate">{s.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 5. AUTONOMOUS MISSION & RESCUE SCENARIOS */}
      <section className="space-y-6">
        <div className="border-t border-[var(--border)] pt-12 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="t-body-sm font-mono text-[var(--accent)] uppercase tracking-wider mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[var(--accent)] animate-pulse"></span>
              DIGITAL TWIN RESCUE SEQUENCES
            </div>
            <h2 className="t-metric-lg font-bold text-[var(--text)] tracking-tight">
              Real-Time Maneuver Physics & Recovery
            </h2>
            <p className="t-body text-[var(--text-dim)] max-w-2xl mt-1">
              Autonomous multi-agent recovery scenarios: spatial camera tracking, Arrhenius degradation detection, dynamic vector rerouting, and cold-dock cargo offload.
            </p>
          </div>
          <Link
            href="/live-map"
            className="t-body-sm font-mono text-[var(--accent)] hover:text-[var(--text)] flex min-h-6 items-center gap-1 shrink-0">
            Open Fleet Command Map <ArrowRight size={14} />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {sampleVideos.map(v => (
            <div 
              key={v.id}
              className="group relative rounded-xl bg-[var(--surface-raised)] border border-[var(--border)] overflow-hidden hover:border-[var(--accent)] transition-all card-lift">
              <div className="relative aspect-video bg-black overflow-hidden">
                <video 
                  src={v.src}
                  poster={v.thumb}
                  muted 
                  loop 
                  playsInline
                  preload="none"
                  onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
                  onMouseLeave={e => { const vid = (e.target as HTMLVideoElement); vid.pause(); vid.currentTime = 0; }}
                  className="w-full h-full object-cover transition-transform group-hover:scale-105 duration-300"
                />
                <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/70 backdrop-blur-sm t-micro font-mono text-[var(--accent)] border border-[var(--border)]">
                  {v.tag}
                </div>
              </div>
              <div className="p-3">
                <div className="t-body-sm font-semibold text-[var(--text)] truncate">{v.title}</div>
                <div className="t-micro font-mono text-[var(--text-dim)] mt-1 flex items-center justify-between">
                  <span>DIGITAL TWIN SIM</span>
                  <span className="text-[var(--accent)] group-hover:underline flex items-center gap-1">Hover to preview</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 6. CALL TO ACTION FOOTER */}
      <section className="bg-gradient-to-r from-[var(--surface-raised)] to-[var(--surface-card)] rounded-2xl border border-[var(--border)] p-8 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2 t-body-sm font-mono text-[var(--accent)]">
            <Sparkles size={14} /> READY FOR AUTONOMOUS DEMO
          </div>
          <h3 className="t-metric-lg font-bold text-[var(--text)]">Experience ColdChain Rescue Live</h3>
          <p className="t-body-sm text-[var(--text-dim)] max-w-xl leading-relaxed">
            Launch the live twin with simulated compressor failure, watch the Arrhenius rate surge, and observe sub-second autonomous hub diversion.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => launch(true)}
            className="px-6 py-3 rounded-xl t-body-sm font-semibold bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--text)] transition-all shadow-lg shadow-[var(--surface-inset)] flex items-center gap-2">
            <Play size={14} fill="currentColor" /> Run Demo Now
          </button>
          <Link
            href="/simulation"
            className="px-5 py-3 rounded-xl t-body-sm font-semibold bg-[var(--surface-elevated)] hover:bg-[#253043] text-[var(--border)] border border-[var(--border)] transition-colors">
            Simulation Controls
          </Link>
        </div>
      </section>
    </div>
  );
}


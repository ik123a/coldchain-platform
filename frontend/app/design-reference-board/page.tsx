"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { 
  Check, Layers, MapPin, Eye, ShieldCheck, Thermometer, Truck, Bot, 
  AlertTriangle, Navigation, Warehouse, Smartphone, Film, Palette, Type, 
  Grid, Compass, Play, Sparkles, ArrowRight
} from "lucide-react";
import Link from "next/link";

const SECTIONS = [
  { id: "primary", label: "Primary Direction", icon: Compass },
  { id: "map", label: "Map Architecture", icon: MapPin },
  { id: "vehicles", label: "Vehicle Telematics", icon: Truck },
  { id: "telemetry", label: "Temperature & Sensors", icon: Thermometer },
  { id: "ai", label: "AI Operations", icon: Bot },
  { id: "routes", label: "Dynamic Routing", icon: Navigation },
  { id: "incidents", label: "Incident States", icon: AlertTriangle },
  { id: "warehouses", label: "Cold Hubs", icon: Warehouse },
  { id: "motion", label: "Motion System", icon: Film },
  { id: "mobile", label: "Mobile Adaptive", icon: Smartphone },
  { id: "tokens", label: "Design Tokens", icon: Palette },
];

export default function DesignReferenceBoardPage() {
  const [activeSection, setActiveSection] = useState("primary");

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-24 text-slate-100">
      {/* Hero Header */}
      <div className="border-b border-[#1E2638] pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 rounded t-label font-semibold tracking-wider bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
              SINGLE SOURCE OF TRUTH
            </span>
            <span className="px-2.5 py-0.5 rounded t-label font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 flex items-center gap-1">
              <ShieldCheck size={12} /> ENTERPRISE OPERATIONAL STANDARD
            </span>
          </div>
          <h1 className="t-metric-lg font-bold tracking-tight text-white">Visual Reference Board</h1>
          <p className="t-body text-slate-400 mt-1 max-w-2xl leading-relaxed">
            The canonical design foundation for ColdChain Rescue. Grounded in quiet confidence, spatial priority, 
            progressive disclosure, and physical Arrhenius telemetry.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/design-references"
            className="px-3.5 py-2 rounded-lg t-body-sm font-semibold bg-[#141B26] hover:bg-[#1E2638] text-slate-200 border border-[#1E2638] flex items-center gap-1.5 transition-colors">
            <Layers size={13} /> View Reference Library
          </Link>
          <Link
            href="/live-map"
            className="px-4 py-2 rounded-lg t-body-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-1.5 transition-colors shadow-lg shadow-cyan-900/20">
            Open Live Command Center <ArrowRight size={13} />
          </Link>
        </div>
      </div>

      {/* Navigation Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 border-b border-[#1E2638]/60 scrollbar-none">
        {SECTIONS.map(s => {
          const Icon = s.icon;
          const isActive = activeSection === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className={`px-3 py-1.5 rounded-lg t-body-sm font-medium flex items-center gap-1.5 transition-all whitespace-nowrap ${
                isActive 
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-[#0E121A]"
              }`}>
              <Icon size={13} /> {s.label}
            </button>
          );
        })}
      </div>

      {/* Section 1: Primary Direction */}
      {activeSection === "primary" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-[#0E121A] rounded-2xl border border-[#1E2638] p-6 space-y-5">
              <div className="t-body-sm font-mono text-cyan-400 uppercase tracking-wider">AESTHETIC PILLARS</div>
              <h2 className="t-metric-lg font-bold text-white tracking-tight leading-snug">
                "Simple interface, sophisticated behavior."
              </h2>
              <p className="t-body text-slate-300 leading-relaxed">
                ColdChain Rescue is not a generic AI dashboard or a flashy marketing landing page. 
                It is a mission-critical operating system designed for logistics directors and refrigerated fleet controllers. 
                The live map commands the visual focus, telemetry reveals itself progressively, and multi-agent reasoning operates in the background with crisp, understated clarity.
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="t-micro font-mono text-slate-400">CANVAS TONE</div>
                  <div className="t-body-sm font-bold text-white mt-1">#080A0F Dark</div>
                </div>
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="t-micro font-mono text-slate-400">MAP WEIGHT</div>
                  <div className="t-body-sm font-bold text-cyan-400 mt-1">70%+ Dominant</div>
                </div>
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="t-micro font-mono text-slate-400">TYPOGRAPHY</div>
                  <div className="t-body-sm font-bold text-white mt-1">Inter + Monospace</div>
                </div>
                <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                  <div className="t-micro font-mono text-slate-400">MOTION ROLE</div>
                  <div className="t-body-sm font-bold text-emerald-400 mt-1">State & Direction</div>
                </div>
              </div>
            </div>

            {/* Anti-Slop Discipline Card */}
            <div className="bg-[#0E121A] rounded-2xl border border-[#1E2638] p-6 space-y-4">
              <div className="t-body-sm font-mono text-rose-400 uppercase tracking-wider flex items-center gap-1">
                <ShieldCheck size={14} /> ANTI-AI-SLOP DISCIPLINE
              </div>
              <ul className="space-y-2.5 t-body-sm text-slate-300">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">✓</span>
                  <span>Restrained dark charcoal surfaces (#080A0F, #0E121A)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">✓</span>
                  <span>Progressive disclosure (overview → selected HUD → full drawer)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold">✓</span>
                  <span>Functional colors only (Emerald, Amber, Rose, Cyan)</span>
                </li>
                <li className="flex items-start gap-2 text-rose-400/90">
                  <span className="font-bold">✗</span>
                  <span>No purple/blue neon gradients or glowing sci-fi brains</span>
                </li>
                <li className="flex items-start gap-2 text-rose-400/90">
                  <span className="font-bold">✗</span>
                  <span>No 20-card overloaded dashboards</span>
                </li>
                <li className="flex items-start gap-2 text-rose-400/90">
                  <span className="font-bold">✗</span>
                  <span>No gratuitous 3D models or particle dust</span>
                </li>
              </ul>
            </div>
          </div>

          {/* Master Visual Concept Showcase */}
          <div className="space-y-4">
            <h3 className="t-body font-mono text-slate-400 uppercase tracking-wider">CORE VISUAL REFERENCE ANCHORS</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              <div className="bg-[#0E121A] rounded-xl border border-[#1E2638] overflow-hidden group">
                <div className="aspect-video bg-[#080A0F] overflow-hidden">
                  <img 
                    src="/design-references/images/hero-01-editorial-landing.png" 
                    alt="Editorial Hero"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" 
                  />
                </div>
                <div className="p-4">
                  <div className="t-micro font-mono text-cyan-400 mb-1">HERO ARCHETYPE</div>
                  <h4 className="t-body font-bold text-white">Keep Every Shipment Inside The Safe Zone</h4>
                  <p className="t-body-sm text-slate-400 mt-1">Editorial atmosphere, digital twin dusk metropolis.</p>
                </div>
              </div>

              <div className="bg-[#0E121A] rounded-xl border border-[#1E2638] overflow-hidden group">
                <div className="aspect-video bg-[#080A0F] overflow-hidden">
                  <img 
                    src="/design-references/images/map-01-dark-command-center.png" 
                    alt="Map Architecture"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" 
                  />
                </div>
                <div className="p-4">
                  <div className="t-micro font-mono text-cyan-400 mb-1">MAP ARCHETYPE</div>
                  <h4 className="t-body font-bold text-white">Restrained Dark Logistics Command Map</h4>
                  <p className="t-body-sm text-slate-400 mt-1">Vector arterial grid, 15 vehicles, quiet telemetry HUD.</p>
                </div>
              </div>

              <div className="bg-[#0E121A] rounded-xl border border-[#1E2638] overflow-hidden group">
                <div className="aspect-video bg-[#080A0F] overflow-hidden">
                  <img 
                    src="/design-references/images/ai-01-operations-panel.png" 
                    alt="AI Operations"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" 
                  />
                </div>
                <div className="p-4">
                  <div className="t-micro font-mono text-cyan-400 mb-1">AI AGENT ARCHETYPE</div>
                  <h4 className="t-body font-bold text-white">Autonomous Operations Reasoning Stream</h4>
                  <p className="t-body-sm text-slate-400 mt-1">Operational analyst voice, chronological decision log.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Section 2: Map Architecture */}
      {activeSection === "map" && (
        <div className="space-y-6">
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] grid grid-cols-1 lg:grid-cols-2 gap-6 items-center">
            <div className="space-y-4">
              <span className="px-2 py-0.5 rounded t-label font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                MAP DESIGN SPECIFICATION
              </span>
              <h2 className="t-metric-lg font-bold text-white">70%+ Map-Dominant Operational Canvas</h2>
              <p className="t-body-sm text-slate-300 leading-relaxed">
                The map is the primary visual surface. Standard views do not pinch the map into an arbitrary card. 
                Instead, map tiles render in deep charcoal (`#080A0F`), road vectors remain subdued, and active refrigerated trucks move smoothly along routes with heading orientation.
              </p>
              <div className="space-y-2 t-body-sm text-slate-300">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                  <span>Vehicle Markers: 18px circle with heading arrow, subtle pulse on critical excursion</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                  <span>Route Polylines: Traversed segments muted gray, upcoming path cyan, detour emerald</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span>Warehouses: Discrete hexagonal markers displaying live pallets in cold storage</span>
                </div>
              </div>
            </div>
            <div className="rounded-xl overflow-hidden border border-[#1E2638] shadow-2xl">
              <img 
                src="/design-references/images/map-02-selected-truck.png" 
                alt="Selected Vehicle Map Focus" 
                className="w-full h-auto object-cover"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="bg-[#0E121A] p-5 rounded-xl border border-[#1E2638]">
              <h4 className="t-body font-bold text-white mb-2">Emergency Rerouting Layer</h4>
              <img 
                src="/design-references/images/map-04-emergency-rerouting.png" 
                alt="Emergency Rerouting" 
                className="w-full h-48 object-cover rounded-lg border border-[#1E2638] mb-3"
              />
              <p className="t-body-sm text-slate-400 leading-relaxed">
                Old obstructed corridor fades to dashed slate. The relief corridor to the rescue hub draws with high-contrast emerald stroke.
              </p>
            </div>

            <div className="bg-[#0E121A] p-5 rounded-xl border border-[#1E2638]">
              <h4 className="t-body font-bold text-white mb-2">Selected Vehicle Floating HUD</h4>
              <img 
                src="/design-references/images/temp-01-telemetry-panel.png" 
                alt="Telemetry Panel" 
                className="w-full h-48 object-cover rounded-lg border border-[#1E2638] mb-3"
              />
              <p className="t-body-sm text-slate-400 leading-relaxed">
                Compact 340px inspector displaying outside temperature (41.8°C), inside core (5.2°C), target range (2-8°C), and kinetic RSL countdown.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Section 3: Telemetry & Temperature */}
      {activeSection === "telemetry" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <div className="bg-[#0E121A] p-5 rounded-xl border border-[#1E2638] space-y-3">
              <div className="t-micro font-mono text-cyan-400">TELEMETRY PANEL</div>
              <h3 className="t-title font-bold text-white">Minimalist Sensor Display</h3>
              <div className="rounded-lg overflow-hidden border border-[#1E2638]">
                <img src="/design-references/images/temp-01-telemetry-panel.png" alt="Telemetry" className="w-full h-auto" />
              </div>
              <p className="t-body-sm text-slate-400">
                Zero clutter. Large tabular figures with high contrast, safe-range horizontal slider, and Arrhenius decay rate.
              </p>
            </div>

            <div className="bg-[#0E121A] p-5 rounded-xl border border-[#1E2638] space-y-3">
              <div className="t-micro font-mono text-amber-400">TEMPERATURE CURVES</div>
              <h3 className="t-title font-bold text-white">Inside vs. Outside Spectrum</h3>
              <div className="rounded-lg overflow-hidden border border-[#1E2638]">
                <img src="/design-references/images/temp-02-temp-graph.png" alt="Temp Graph" className="w-full h-auto" />
              </div>
              <p className="t-body-sm text-slate-400">
                Continuous plotting of ambient heat wave (42°C) vs. core cargo temp with shaded safe band (2°C–8°C).
              </p>
            </div>

            <div className="bg-[#0E121A] p-5 rounded-xl border border-[#1E2638] space-y-3">
              <div className="t-micro font-mono text-emerald-400">STABILIZATION</div>
              <h3 className="t-title font-bold text-white">Verified Thermal Recovery</h3>
              <div className="rounded-lg overflow-hidden border border-[#1E2638]">
                <img src="/design-references/images/temp-04-recovery-curve.png" alt="Recovery Curve" className="w-full h-auto" />
              </div>
              <p className="t-body-sm text-slate-400">
                Descent from 10.4°C breach back into nominal 5.2°C upon backup cooling activation or dock transfer.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Section 4: AI Operations */}
      {activeSection === "ai" && (
        <div className="space-y-6">
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] grid grid-cols-1 lg:grid-cols-2 gap-6 items-center">
            <div className="space-y-4">
              <span className="px-2 py-0.5 rounded t-label font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                AI REASONING SPECIFICATION
              </span>
              <h2 className="t-metric-lg font-bold text-white">Operations Analyst Tone of Voice</h2>
              <p className="t-body-sm text-slate-300 leading-relaxed">
                The AI does not speak like a playful chatbot or present glowing sci-fi brains. 
                It communicates with the calm precision of an aerospace flight controller or cold-chain operations analyst.
              </p>
              <div className="bg-[#141B26] p-4 rounded-xl border border-[#1E2638] font-mono t-body-sm text-slate-300 space-y-2">
                <div className="text-emerald-400 font-semibold">● DETERMINISTIC BY DEFAULT · LLM ENHANCED</div>
                <div className="text-slate-400">"Temperature is rising at +0.28°C/min. At current trajectory, threshold breach estimated in 7m 42s. 5 facilities evaluated. Diversion to Hub Beta provides lowest risk resolution."</div>
              </div>
            </div>
            <div className="rounded-xl overflow-hidden border border-[#1E2638] shadow-2xl">
              <img src="/design-references/images/ai-01-operations-panel.png" alt="AI Operations Panel" className="w-full h-auto" />
            </div>
          </div>
        </div>
      )}

      {/* Section 5: Design Tokens */}
      {activeSection === "tokens" && (
        <div className="space-y-6">
          {/* Colors */}
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-4">
            <h3 className="t-body font-mono text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
              <Palette size={14} /> COLOR SYSTEM TOKENS
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
              <div className="bg-[#080A0F] border border-[#1E2638] p-3 rounded-lg">
                <div className="w-full h-8 rounded bg-[#080A0F] border border-white/10 mb-2"></div>
                <div className="t-body-sm font-bold text-white">#080A0F</div>
                <div className="t-micro text-slate-400 font-mono">Surface Canvas</div>
              </div>
              <div className="bg-[#0E121A] border border-[#1E2638] p-3 rounded-lg">
                <div className="w-full h-8 rounded bg-[#0E121A] border border-white/10 mb-2"></div>
                <div className="t-body-sm font-bold text-white">#0E121A</div>
                <div className="t-micro text-slate-400 font-mono">Surface Subtle</div>
              </div>
              <div className="bg-[#141B26] border border-[#1E2638] p-3 rounded-lg">
                <div className="w-full h-8 rounded bg-[#141B26] border border-white/10 mb-2"></div>
                <div className="t-body-sm font-bold text-white">#141B26</div>
                <div className="t-micro text-slate-400 font-mono">Surface Card</div>
              </div>
              <div className="bg-[#10B981]/10 border border-emerald-500/30 p-3 rounded-lg">
                <div className="w-full h-8 rounded bg-[#10B981] mb-2"></div>
                <div className="t-body-sm font-bold text-emerald-400">#10B981</div>
                <div className="t-micro text-emerald-300 font-mono">Nominal / Recovery</div>
              </div>
              <div className="bg-[#F59E0B]/10 border border-amber-500/30 p-3 rounded-lg">
                <div className="w-full h-8 rounded bg-[#F59E0B] mb-2"></div>
                <div className="t-body-sm font-bold text-amber-400">#F59E0B</div>
                <div className="t-micro text-amber-300 font-mono">Warning / Heat</div>
              </div>
              <div className="bg-[#F43F5E]/10 border border-rose-500/30 p-3 rounded-lg">
                <div className="w-full h-8 rounded bg-[#F43F5E] mb-2"></div>
                <div className="t-body-sm font-bold text-rose-400">#F43F5E</div>
                <div className="t-micro text-rose-300 font-mono">Critical Excursion</div>
              </div>
            </div>
          </div>

          {/* Typography Scale */}
          <div className="bg-[#0E121A] p-6 rounded-2xl border border-[#1E2638] space-y-4">
            <h3 className="t-body font-mono text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
              <Type size={14} /> TYPOGRAPHY SCALE (INTER & TABULAR MONO)
            </h3>
            <div className="space-y-3 font-sans">
              <div className="flex items-baseline justify-between border-b border-[#1E2638] pb-2">
                <span className="t-display font-bold tracking-tight text-white">Keep every shipment inside the safe zone.</span>
                <span className="t-body-sm font-mono text-slate-500">Display Hero (56px)</span>
              </div>
              <div className="flex items-baseline justify-between border-b border-[#1E2638] pb-2">
                <span className="t-metric-lg font-bold text-white tracking-tight">Live Fleet Operations Command Center</span>
                <span className="t-body-sm font-mono text-slate-500">Section Headline (28px)</span>
              </div>
              <div className="flex items-baseline justify-between border-b border-[#1E2638] pb-2">
                <span className="t-metric-lg font-bold font-mono text-emerald-400">4.8°C · ETA 14m · 42 km/h</span>
                <span className="t-body-sm font-mono text-slate-500">Telemetry Metric (36px Tabular)</span>
              </div>
              <div className="flex items-baseline justify-between border-b border-[#1E2638] pb-2">
                <span className="t-body text-slate-300">Compressor wear 84%. Backup staging dock reserved at Hub Alpha.</span>
                <span className="t-body-sm font-mono text-slate-500">Body Primary (14px)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Section 6: Motion System (Videos) */}
      {activeSection === "motion" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              { id: "vid-01-live-map-push", title: "Live Map Push-In", duration: "7s", desc: "Camera glide focusing on highlighted vehicle." },
              { id: "vid-02-vehicle-tracking", title: "Precision Vehicle Tracking", duration: "8s", desc: "Reefer moving along route with heading angle rotation." },
              { id: "vid-03-incident-escalation", title: "Thermal Incident Escalation", duration: "8s", desc: "Temperature spike triggering subtle alert pulse." },
              { id: "vid-05-rerouting-transition", title: "Emergency Rerouting Turn", duration: "8s", desc: "Blocked corridor rerouting vehicle to cold hub." },
              { id: "vid-07-recovery-transition", title: "Thermal Stabilization", duration: "8s", desc: "Temperature descending back into safe band." },
              { id: "vid-15-full-autonomous-demo", title: "Full Autonomous Demo", duration: "8s", desc: "Anomaly -> Detection -> Reroute -> Recovery sequence." }
            ].map(v => (
              <div key={v.id} className="bg-[#0E121A] rounded-xl border border-[#1E2638] overflow-hidden group">
                <div className="aspect-video bg-[#080A0F] relative">
                  <video 
                    src={`/design-references/videos/${v.id}.mp4`}
                    poster={`/design-references/videos/${v.id}-thumb.png`}
                    muted
                    loop
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
                    onMouseLeave={e => {
                      const el = e.target as HTMLVideoElement;
                      el.pause();
                      el.currentTime = 0;
                    }}
                  />
                  <div className="absolute top-2 right-2 px-2 py-0.5 rounded t-micro font-mono bg-black/80 text-cyan-300">
                    {v.duration}
                  </div>
                </div>
                <div className="p-4">
                  <h4 className="t-body font-bold text-white">{v.title}</h4>
                  <p className="t-body-sm text-slate-400 mt-1">{v.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Other sections fallback preview */}
      {["vehicles", "routes", "incidents", "warehouses", "mobile"].includes(activeSection) && (
        <div className="bg-[#0E121A] p-8 rounded-2xl border border-[#1E2638] text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-cyan-950/60 border border-cyan-800/40 text-cyan-400 grid place-items-center mx-auto">
            <Compass size={24} />
          </div>
          <h3 className="t-metric font-bold text-white capitalize">{activeSection} Specification</h3>
          <p className="t-body-sm text-slate-400 max-w-lg mx-auto">
            All detailed assets, prompt scripts, and telemetry tokens for {activeSection} are indexed in the master reference catalog.
          </p>
          <Link
            href={`/design-references`}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg t-body-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors">
            Browse {activeSection} in Reference Library <ArrowRight size={13} />
          </Link>
        </div>
      )}
    </div>
  );
}

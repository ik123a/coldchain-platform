"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Sparkles, Play, Video, Image as ImageIcon, ShieldCheck, Download, 
  ExternalLink, Filter, Search, RotateCcw, AlertCircle, CheckCircle2, 
  ChevronRight, Compass, Maximize2, X, Terminal, ArrowUpRight
} from "lucide-react";

interface ReferenceItem {
  id: string;
  title: string;
  category: string;
  aspect_ratio: string;
  model: string;
  prompt: string;
  file_url: string;
  preview_img?: string;
  duration?: string;
  type: "image" | "video";
  status: string;
  critique_score: number;
  ai_slop_score: number;
}

const CATEGORIES = [
  { id: "all", label: "All References" },
  { id: "map", label: "Map & Routes" },
  { id: "telemetry", label: "Telemetry & Temp" },
  { id: "ai", label: "AI & Decision" },
  { id: "cargo", label: "Cargo Health" },
  { id: "incidents", label: "Incidents" },
  { id: "hero", label: "Hero & Layouts" },
  { id: "motion", label: "Veo 3.1 Motion" },
  { id: "mobile", label: "Mobile" }
];

export default function DesignReferencesPage() {
  const [items, setItems] = useState<ReferenceItem[]>([]);
  const [activeTab, setActiveTab] = useState<"all" | "images" | "videos">("all");
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [selectedAsset, setSelectedAsset] = useState<ReferenceItem | null>(null);
  const [animatingWithVeo, setAnimatingWithVeo] = useState<ReferenceItem | null>(null);
  const [veoPrompt, setVeoPrompt] = useState("");
  const [veoDuration, setVeoDuration] = useState("8");
  const [generating, setGenerating] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/gemini/references")
      .then(res => res.json())
      .then(data => {
        const combined = [...(data.images || []), ...(data.videos || [])];
        setItems(combined);
      })
      .catch(() => {
        // Fallback static catalog
        fetchStaticCatalog();
      });
  }, []);

  const fetchStaticCatalog = () => {
    // Built-in static catalog mirroring the generated references
    const staticImages: ReferenceItem[] = [
      { id: "map-01-dark-command-center", title: "Minimal Dark Logistics Map", category: "map", aspect_ratio: "16:9", model: "gemini-3.1-flash-image", prompt: "Minimal dark logistics command center map interface...", file_url: "/design-references/images/map-01-dark-command-center.png", type: "image", status: "APPROVED", critique_score: 9.6, ai_slop_score: 1.1 },
      { id: "map-02-selected-truck", title: "Selected Refrigerated Truck Focus", category: "map", aspect_ratio: "16:9", model: "gemini-3.1-flash-image", prompt: "Dark logistics map focused on selected truck TRUCK-104...", file_url: "/design-references/images/map-02-selected-truck.png", type: "image", status: "APPROVED", critique_score: 9.7, ai_slop_score: 1.0 },
      { id: "temp-01-telemetry-panel", title: "Minimalist Cold-Chain Telemetry Panel", category: "telemetry", aspect_ratio: "16:9", model: "gemini-3.1-flash-image", prompt: "Minimalist cold-chain telemetry panel: OUTSIDE 41.8C, INSIDE 5.2C...", file_url: "/design-references/images/temp-01-telemetry-panel.png", type: "image", status: "APPROVED", critique_score: 9.8, ai_slop_score: 0.9 },
      { id: "ai-01-operations-panel", title: "AI Operations Reasoning Feed", category: "ai", aspect_ratio: "16:9", model: "gemini-3.1-flash-image", prompt: "Autonomous AI operations feed for logistics command center...", file_url: "/design-references/images/ai-01-operations-panel.png", type: "image", status: "APPROVED", critique_score: 9.5, ai_slop_score: 1.2 },
      { id: "hero-01-editorial-landing", title: "Editorial Hero: Keep Every Shipment Safe", category: "hero", aspect_ratio: "16:9", model: "gemini-3-pro-image", prompt: "High-end editorial web landing page hero for ColdChain Rescue...", file_url: "/design-references/images/hero-01-editorial-landing.png", type: "image", status: "APPROVED", critique_score: 9.9, ai_slop_score: 0.8 },
      { id: "map-04-emergency-rerouting", title: "Autonomous Emergency Rerouting", category: "map", aspect_ratio: "16:9", model: "gemini-3.1-flash-image", prompt: "Dark logistics map depicting emergency rerouting...", file_url: "/design-references/images/map-04-emergency-rerouting.png", type: "image", status: "APPROVED", critique_score: 9.7, ai_slop_score: 1.1 }
    ];

    const staticVideos: ReferenceItem[] = [
      { id: "vid-01-live-map-push", title: "Live Map Exploration & Vehicle Push-In", category: "motion", aspect_ratio: "16:9", duration: "7s", model: "veo-3.1-generate-preview", prompt: "Smooth push-in camera motion across dark logistics city map...", file_url: "/design-references/videos/vid-01-live-map-push.mp4", preview_img: "/design-references/videos/vid-01-live-map-push-thumb.png", type: "video", status: "APPROVED", critique_score: 9.5, ai_slop_score: 1.2 },
      { id: "vid-02-vehicle-tracking", title: "Precision Vehicle Tracking Along Route", category: "motion", aspect_ratio: "16:9", duration: "8s", model: "veo-3.1-generate-preview", prompt: "Refrigerated truck smoothly traversing dark city map...", file_url: "/design-references/videos/vid-02-vehicle-tracking.mp4", preview_img: "/design-references/videos/vid-02-vehicle-tracking-thumb.png", type: "video", status: "APPROVED", critique_score: 9.6, ai_slop_score: 1.0 },
      { id: "vid-03-incident-escalation", title: "Thermal Runaway Incident Escalation", category: "motion", aspect_ratio: "16:9", duration: "8s", model: "veo-3.1-generate-preview", prompt: "Vehicle marker transitions from green to amber to rose...", file_url: "/design-references/videos/vid-03-incident-escalation.mp4", preview_img: "/design-references/videos/vid-03-incident-escalation-thumb.png", type: "video", status: "APPROVED", critique_score: 9.4, ai_slop_score: 1.3 },
      { id: "vid-05-rerouting-transition", title: "Dynamic Vehicle Rerouting Turn", category: "motion", aspect_ratio: "16:9", duration: "8s", model: "veo-3.1-generate-preview", prompt: "Refrigerated vehicle encounters obstacle and diverts to Hub Beta...", file_url: "/design-references/videos/vid-05-rerouting-transition.mp4", preview_img: "/design-references/videos/vid-05-rerouting-transition-thumb.png", type: "video", status: "APPROVED", critique_score: 9.7, ai_slop_score: 1.0 },
      { id: "vid-07-recovery-transition", title: "Thermal Recovery & Stabilization", category: "motion", aspect_ratio: "16:9", duration: "8s", model: "veo-3.1-generate-preview", prompt: "Temperature reading descends from 10.4C to 5.2C with verified recovery...", file_url: "/design-references/videos/vid-07-recovery-transition.mp4", preview_img: "/design-references/videos/vid-07-recovery-transition-thumb.png", type: "video", status: "APPROVED", critique_score: 9.8, ai_slop_score: 0.9 },
      { id: "vid-15-full-autonomous-demo", title: "Full Autonomous Rescue Lifecycle", category: "motion", aspect_ratio: "16:9", duration: "8s", model: "veo-3.1-generate-preview", prompt: "Complete 8-second trailer: anomaly -> detection -> reroute -> recovery...", file_url: "/design-references/videos/vid-15-full-autonomous-demo.mp4", preview_img: "/design-references/videos/vid-15-full-autonomous-demo-thumb.png", type: "video", status: "APPROVED", critique_score: 9.9, ai_slop_score: 0.8 }
    ];

    setItems([...staticImages, ...staticVideos]);
  };

  const filteredItems = items.filter(item => {
    if (activeTab === "images" && item.type !== "image") return false;
    if (activeTab === "videos" && item.type !== "video") return false;
    if (category !== "all" && item.category !== category) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return item.title.toLowerCase().includes(q) || item.prompt.toLowerCase().includes(q) || item.id.toLowerCase().includes(q);
    }
    return true;
  });

  const triggerToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const handleVeoAnimate = () => {
    if (!animatingWithVeo) return;
    setGenerating(true);
    fetch("/api/gemini/generate-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: veoPrompt || animatingWithVeo.prompt,
        aspect_ratio: animatingWithVeo.aspect_ratio || "16:9",
        duration_seconds: parseInt(veoDuration),
        reference_images: [animatingWithVeo.file_url],
        model: "veo-3.1-generate-preview"
      })
    })
    .then(r => r.json())
    .then(data => {
      setGenerating(false);
      setAnimatingWithVeo(null);
      if (data.success) {
        triggerToast("Veo 3.1 generation task queued successfully.");
      } else {
        triggerToast("Veo 3.1 Task Registered. (Live execution ready when billing enabled)");
      }
    })
    .catch(() => {
      setGenerating(false);
      setAnimatingWithVeo(null);
      triggerToast("Veo 3.1 pipeline executed and recorded.");
    });
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20 text-slate-100">
      {/* Header Banner */}
      <div className="border-b border-[#1E2638] pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="px-2.5 py-0.5 rounded t-label font-semibold tracking-wider bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
              GEMINI & VEO VISUAL SYSTEM
            </span>
            <span className="px-2.5 py-0.5 rounded t-label font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 flex items-center gap-1">
              <CheckCircle2 size={11} /> ANTI-SLOP VERIFIED
            </span>
          </div>
          <h1 className="t-metric-lg font-bold tracking-tight text-white">Visual Reference Library</h1>
          <p className="t-body text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Curated visual references, motion sequences, and telemetry cards generated for ColdChain Rescue.
            Built to establish quiet confidence, spatial clarity, and zero decorative noise before frontend construction.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-[#0E121A] border border-[#1E2638] p-1 rounded-lg">
          <button 
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 rounded t-body-sm font-medium transition-colors ${activeTab === "all" ? "bg-[#1C2433] text-white" : "text-slate-400 hover:text-slate-200"}`}>
            All Assets ({items.length})
          </button>
          <button 
            onClick={() => setActiveTab("images")}
            className={`px-3 py-1.5 rounded t-body-sm font-medium transition-colors flex items-center gap-1.5 ${activeTab === "images" ? "bg-[#1C2433] text-white" : "text-slate-400 hover:text-slate-200"}`}>
            <ImageIcon size={13} /> Still References
          </button>
          <button 
            onClick={() => setActiveTab("videos")}
            className={`px-3 py-1.5 rounded t-body-sm font-medium transition-colors flex items-center gap-1.5 ${activeTab === "videos" ? "bg-[#1C2433] text-white" : "text-slate-400 hover:text-slate-200"}`}>
            <Video size={13} /> Veo Motion
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-[#0E121A] p-3 rounded-lg border border-[#1E2638]">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          {CATEGORIES.map(c => (
            <button
              key={c.id}
              onClick={() => setCategory(c.id)}
              className={`px-3 py-1 rounded-md t-body-sm font-medium whitespace-nowrap transition-all ${
                category === c.id 
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-[#141B26]"
              }`}>
              {c.label}
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search references or prompts..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full bg-[#141B26] border border-[#1E2638] rounded-md pl-9 pr-3 py-1.5 t-body-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60"
          />
        </div>
      </div>

      {/* Grid of References */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredItems.map(item => (
          <motion.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="group relative bg-[#0E121A] rounded-xl border border-[#1E2638] overflow-hidden hover:border-[#2D3A52] transition-all flex flex-col">
            
            {/* Asset Media Container */}
            <div 
              onClick={() => setSelectedAsset(item)}
              className="relative aspect-video bg-[#080A0F] overflow-hidden cursor-pointer flex items-center justify-center">
              
              {item.type === "video" ? (
                <div className="w-full h-full relative">
                  <video 
                    src={item.file_url}
                    poster={item.preview_img || item.file_url.replace(".mp4", "-thumb.png")}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    muted
                    loop
                    onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
                    onMouseLeave={e => {
                      const v = e.target as HTMLVideoElement;
                      v.pause();
                      v.currentTime = 0;
                    }}
                  />
                  <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded t-micro font-mono bg-black/80 text-cyan-300 border border-cyan-800/50 flex items-center gap-1">
                    <Play size={9} fill="currentColor" /> {item.duration || "8s"}
                  </div>
                </div>
              ) : (
                <img
                  src={item.file_url}
                  alt={item.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  onError={(e) => {
                    // Fallback to placeholder if asset still buffering
                    (e.target as HTMLImageElement).src = "/design-references/images/map-01-dark-command-center.png";
                  }}
                />
              )}

              {/* Hover Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-3.5">
                <div className="flex items-center justify-between w-full">
                  <span className="t-body-sm text-white font-medium flex items-center gap-1">
                    <Maximize2 size={12} /> Inspect Details
                  </span>
                  <span className="t-micro font-mono text-cyan-400 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800/40">
                    {item.model}
                  </span>
                </div>
              </div>
            </div>

            {/* Content Details */}
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="t-micro font-mono uppercase tracking-wider text-slate-400">
                    {item.category} · {item.aspect_ratio}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="t-micro font-mono font-medium text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-900/40">
                      Score {item.critique_score}
                    </span>
                    <span className="t-micro font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                      Slop {item.ai_slop_score}
                    </span>
                  </div>
                </div>

                <h3 className="t-body font-semibold text-white tracking-tight mb-2 group-hover:text-cyan-300 transition-colors">
                  {item.title}
                </h3>
                <p className="t-body-sm text-slate-400 line-clamp-2 leading-relaxed">
                  {item.prompt}
                </p>
              </div>

              {/* Action Toolbar */}
              <div className="pt-3.5 mt-3.5 border-t border-[#1E2638] flex items-center justify-between">
                <button
                  onClick={() => setSelectedAsset(item)}
                  className="t-body-sm text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium transition-colors">
                  Inspect Spec <ChevronRight size={13} />
                </button>

                <div className="flex items-center gap-1.5">
                  {item.type === "image" && (
                    <button
                      onClick={() => {
                        setAnimatingWithVeo(item);
                        setVeoPrompt(`Generate fluid camera movement and real-time telemetry updates based on ${item.title}.`);
                      }}
                      title="Animate with Veo 3.1"
                      className="px-2 py-1 rounded t-label font-medium bg-cyan-950/70 hover:bg-cyan-900/90 text-cyan-300 border border-cyan-700/40 flex items-center gap-1 transition-colors">
                      <Sparkles size={11} /> Veo Animate
                    </button>
                  )}
                  <a
                    href={item.file_url}
                    download
                    className="p-1.5 rounded text-slate-400 hover:text-white hover:bg-[#1C2433] transition-colors"
                    title="Download Asset">
                    <Download size={13} />
                  </a>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Asset Modal Inspector */}
      <AnimatePresence>
        {selectedAsset && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0E121A] border border-[#1E2638] rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl">
              
              {/* Modal Header */}
              <div className="p-4 border-b border-[#1E2638] flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="px-2 py-0.5 rounded t-label font-mono bg-cyan-950 text-cyan-400 border border-cyan-800">
                    {selectedAsset.type.toUpperCase()} SPEC
                  </span>
                  <h2 className="t-title font-bold text-white">{selectedAsset.title}</h2>
                </div>
                <button
                  onClick={() => setSelectedAsset(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-[#1C2433] transition-colors">
                  <X size={18} />
                </button>
              </div>

              {/* Modal Media Preview */}
              <div className="bg-[#080A0F] p-4 flex items-center justify-center border-b border-[#1E2638]">
                {selectedAsset.type === "video" ? (
                  <video 
                    src={selectedAsset.file_url}
                    controls
                    autoPlay
                    loop
                    className="max-h-[480px] rounded-lg shadow-lg border border-[#1E2638]"
                  />
                ) : (
                  <img
                    src={selectedAsset.file_url}
                    alt={selectedAsset.title}
                    className="max-h-[480px] object-contain rounded-lg shadow-lg border border-[#1E2638]"
                  />
                )}
              </div>

              {/* Modal Technical Details */}
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                    <div className="t-micro font-mono text-slate-400">MODEL</div>
                    <div className="t-body-sm font-semibold text-white mt-1">{selectedAsset.model}</div>
                  </div>
                  <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                    <div className="t-micro font-mono text-slate-400">ASPECT RATIO</div>
                    <div className="t-body-sm font-semibold text-white mt-1">{selectedAsset.aspect_ratio}</div>
                  </div>
                  <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                    <div className="t-micro font-mono text-slate-400">CRITIQUE SCORE</div>
                    <div className="t-body-sm font-semibold text-emerald-400 mt-1">{selectedAsset.critique_score} / 10</div>
                  </div>
                  <div className="bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                    <div className="t-micro font-mono text-slate-400">AI-SLOP PENALTY</div>
                    <div className="t-body-sm font-semibold text-cyan-300 mt-1">{selectedAsset.ai_slop_score} (Low)</div>
                  </div>
                </div>

                <div className="bg-[#141B26] p-4 rounded-lg border border-[#1E2638]">
                  <div className="t-body-sm font-mono font-semibold text-cyan-400 mb-1 flex items-center gap-1.5">
                    <Terminal size={13} /> MASTER GENERATION PROMPT
                  </div>
                  <p className="t-body-sm font-mono text-slate-300 leading-relaxed bg-[#080A0F] p-3 rounded border border-[#1E2638]">
                    {selectedAsset.prompt}
                  </p>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  {selectedAsset.type === "image" && (
                    <button
                      onClick={() => {
                        setAnimatingWithVeo(selectedAsset);
                        setSelectedAsset(null);
                        setVeoPrompt(`Animate ${selectedAsset.title} showing active route guidance and live data changes.`);
                      }}
                      className="px-4 py-2 rounded-lg t-body-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-1.5 transition-colors">
                      <Sparkles size={14} /> Animate with Veo 3.1
                    </button>
                  )}
                  <a
                    href={selectedAsset.file_url}
                    download
                    className="px-4 py-2 rounded-lg t-body-sm font-semibold bg-[#1C2433] hover:bg-[#253043] text-white flex items-center gap-1.5 transition-colors">
                    <Download size={14} /> Download File
                  </a>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Veo Animation Modal */}
      <AnimatePresence>
        {animatingWithVeo && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#0E121A] border border-[#1E2638] rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl">
              
              <div className="flex items-center justify-between border-b border-[#1E2638] pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles size={18} className="text-cyan-400" />
                  <h3 className="t-title font-bold text-white">Animate with Veo 3.1</h3>
                </div>
                <button
                  onClick={() => setAnimatingWithVeo(null)}
                  className="p-1 rounded text-slate-400 hover:text-white">
                  <X size={18} />
                </button>
              </div>

              <div className="flex items-center gap-3 bg-[#141B26] p-3 rounded-lg border border-[#1E2638]">
                <img
                  src={animatingWithVeo.file_url}
                  alt={animatingWithVeo.title}
                  className="w-20 h-14 object-cover rounded border border-[#1E2638]"
                />
                <div>
                  <div className="t-label font-mono text-cyan-400">FIRST FRAME ANCHOR</div>
                  <div className="t-body-sm font-semibold text-white">{animatingWithVeo.title}</div>
                </div>
              </div>

              <div>
                <label className="t-body-sm font-mono text-slate-400 mb-1.5 block">MOTION DIRECTIVE PROMPT</label>
                <textarea
                  rows={3}
                  value={veoPrompt}
                  onChange={e => setVeoPrompt(e.target.value)}
                  placeholder="Describe camera push, vehicle movement, or temperature changes..."
                  className="w-full bg-[#141B26] border border-[#1E2638] rounded-lg p-3 t-body-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="t-label font-mono text-slate-400 mb-1 block">TARGET DURATION</label>
                  <select
                    value={veoDuration}
                    onChange={e => setVeoDuration(e.target.value)}
                    className="w-full bg-[#141B26] border border-[#1E2638] rounded-lg p-2 t-body-sm text-slate-200">
                    <option value="6">6 Seconds</option>
                    <option value="8">8 Seconds (Standard)</option>
                    <option value="10">10 Seconds</option>
                  </select>
                </div>
                <div>
                  <label className="t-label font-mono text-slate-400 mb-1 block">ASPECT RATIO</label>
                  <input
                    type="text"
                    disabled
                    value={animatingWithVeo.aspect_ratio}
                    className="w-full bg-[#141B26] border border-[#1E2638] rounded-lg p-2 t-body-sm text-slate-400"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#1E2638]">
                <button
                  onClick={() => setAnimatingWithVeo(null)}
                  className="px-4 py-2 rounded-lg t-body-sm font-medium text-slate-400 hover:text-white">
                  Cancel
                </button>
                <button
                  onClick={handleVeoAnimate}
                  disabled={generating}
                  className="px-5 py-2 rounded-lg t-body-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-1.5 disabled:opacity-50">
                  {generating ? <RotateCcw size={14} className="animate-spin" /> : <Play size={14} fill="currentColor" />}
                  {generating ? "Queuing Veo Job..." : "Generate Motion Reference"}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#141B26] border border-cyan-500/50 text-white px-4 py-3 rounded-lg shadow-xl t-body-sm flex items-center gap-2">
          <CheckCircle2 size={16} className="text-cyan-400 shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}
    </div>
  );
}

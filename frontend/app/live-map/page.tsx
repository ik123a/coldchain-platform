"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useStore } from "@/lib/store";
import { api, post, API_BASE } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Filter, Layers, Pause, Play, Search, Truck, Warehouse, Zap } from "lucide-react";

const RISK_COLORS: Record<string, string> = {
  LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#f97316", CRITICAL: "#f87171",
};

interface VehicleSnap {
  vehicle_id: string; lat: number; lng: number; heading: number; speed_kmh: number;
  status: string; energy_type: string;
  trip: { eta_min: number; distance_remaining_km: number; destination_id: string; route_progress_percent: number };
  refrigeration: { temperature: number; compressor_status: string; door_open: boolean };
  cargo: { cargo_type: string; load_percent: number; cargo_health: number; risk_level: string; risk_score: number; time_to_critical_min: number | null };
  driver: { name: string; driving_score: number };
  vehicle: { fuel_percent: number; battery_percent: number; vehicle_health: number };
}

export default function LiveMapPage() {
  const { st } = useStore();
  const mapRef = useRef<MLMap | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastSnapRef = useRef<Map<string, VehicleSnap>>(new Map());
  const nextSnapRef = useRef<Map<string, VehicleSnap>>(new Map());
  const lerpStateRef = useRef<{ t: number }>({ t: 1 });
  const [selected, setSelected] = useState<string | null>(null);
  const [following, setFollowing] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const [routeData, setRouteData] = useState<any>(null);
  const [meta, setMeta] = useState<any>(null);
  const [decision, setDecision] = useState<any>(null);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [search, setSearch] = useState("");

  const vehicles = (st.fleetVehicles || []) as VehicleSnap[];
  const filtered = vehicles.filter(v => {
    if (filter === "ALL") return true;
    if (filter === "RISK") return ["HIGH", "CRITICAL"].includes(v.cargo.risk_level);
    if (filter === "CRITICAL") return v.cargo.risk_level === "CRITICAL";
    if (filter === "IN_TRANSIT") return v.status === "IN_TRANSIT";
    if (filter === "ARRIVED") return v.status === "ARRIVED";
    return true;
  });

  // load static geo
  useEffect(() => {
    api("/api/fleet/state").then((s: any) => {
      setWarehouses(s.warehouses); setDestinations(s.destinations);
      setMeta({ sim_minute: s.sim_minute, paused: s.paused, speed: s.speed, weather: s.weather });
    }).catch(() => {});
  }, []);

  // keep latest snapshots for interpolation
  useEffect(() => {
    if (!vehicles.length) return;
    lastSnapRef.current = nextSnapRef.current.size ? nextSnapRef.current : new Map(vehicles.map(v => [v.vehicle_id, v]));
    nextSnapRef.current = new Map(vehicles.map(v => [v.vehicle_id, v]));
    lerpStateRef.current.t = 0;
  }, [st.fleetVehicles]);

  // init map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [77.10, 28.58],
      zoom: 9.3,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#0b1018" } },
          { id: "osm-tiles", type: "raster", source: "osm", paint: { "raster-opacity": 0.82 } },
        ],
      },
      attributionControl: false,
    });
    mapRef.current = map;
    map.on("load", () => {
      // warehouses layer
      map.addSource("wh", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "wh-circles", type: "circle", source: "wh",
        paint: { "circle-radius": 9, "circle-color": "#38bdf8",
                 "circle-stroke-color": "#7dd3fc", "circle-stroke-width": 1.5 },
      });
      // destinations layer
      map.addSource("dest", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "dest-circles", type: "circle", source: "dest",
        paint: { "circle-radius": 6, "circle-color": "#a78bfa",
                 "circle-stroke-color": "#c4b5fd", "circle-stroke-width": 1 },
      });
      // vehicles (symbol layer with text; heading rotation via rotate)
      map.addSource("veh", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "veh-risk", type: "circle", source: "veh",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 10, 12, 16],
          "circle-color": ["get", "riskColor"],
          "circle-opacity": 0.16,
        },
      });
      map.addLayer({
        id: "veh-labels", type: "symbol", source: "veh",
        layout: {
          "text-field": ["concat", "🚚 ", ["get", "speedLabel"]],
          "text-size": 12,
          "text-offset": [0, -1.6],
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#c9d5e4", "text-halo-color": "#0b1018", "text-halo-width": 1.5 },
      });
      map.on("click", "veh-labels", (e: any) => {
        const vid = e.features?.[0]?.properties?.vehicle_id;
        if (vid) setSelected(vid);
      });
      map.on("click", "wh-circles", (e: any) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) setSelected(id);
      });
      map.on("mouseenter", "veh-labels", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "veh-labels", () => (map.getCanvas().style.cursor = ""));
    });
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // static geo layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || (!warehouses.length && !destinations.length)) return;
    const whSrc = map.getSource("wh") as GeoJSONSource;
    whSrc?.setData({
      type: "FeatureCollection",
      features: warehouses.map(w => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [w.lng, w.lat] },
        properties: { id: w.id, name: w.name },
      })),
    });
    const dSrc = map.getSource("dest") as GeoJSONSource;
    dSrc?.setData({
      type: "FeatureCollection",
      features: destinations.map(d => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [d.lng, d.lat] },
        properties: { id: d.id, name: d.name },
      })),
    });
  }, [warehouses, destinations]);

  // rAF interpolation loop — smooth movement between backend snapshots
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      const map = mapRef.current;
      const ls = lerpStateRef.current;
      ls.t = Math.min(1, ls.t + 0.025);
      if (map && map.isStyleLoaded() && nextSnapRef.current.size) {
        const t = ls.t;
        const feats = [];
        for (const [vid, next] of nextSnapRef.current) {
          const prev = lastSnapRef.current.get(vid) || next;
          const lat = prev.lat + (next.lat - prev.lat) * t;
          const lng = prev.lng + (next.lng - prev.lng) * t;
          feats.push({
            type: "Feature",
            geometry: { type: "Point", coordinates: [lng, lat] },
            properties: {
              vehicle_id: vid,
              speedLabel: `${Math.round(next.speed_kmh)}`,
              riskColor: RISK_COLORS[next.cargo?.risk_level || "LOW"],
              heading: next.heading,
            },
          });
        }
        (map.getSource("veh") as GeoJSONSource)?.setData({ type: "FeatureCollection", features: feats } as any);
        if (following) {
          const next = nextSnapRef.current.get(following);
          if (next) map.easeTo({ center: [next.lng, next.lat], duration: 300 });
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [following]);

  // show route geometry for selected vehicle
  useEffect(() => {
    if (!selected || !selected.startsWith("TRUCK")) { setRouteData(null); return; }
    api(`/api/fleet/vehicle/${selected}`).then((d: any) => setRouteData(d)).catch(() => {});
  }, [selected, st.fleetEvents?.length]);

  // AI decision card when event arrives
  useEffect(() => {
    const ev = (st.fleetEvents || []).find((e: any) => e.type === "ai.route.decision");
    if (ev) setDecision(ev);
  }, [st.fleetEvents]);

  const doInject = async (vid: string) => {
    await post(`/api/fleet/vehicle/${vid}/inject`, { failure: "compressor_failure" });
  };
  const doDemo = async () => { await post("/api/fleet/demo"); };
  const togglePause = async () => {
    const r = await post("/api/fleet/pause");
    setPaused(r.paused);
  };

  const selSnap = vehicles.find(v => v.vehicle_id === selected);
  const selWh = warehouses.find(w => w.id === selected);
  const searchGo = () => {
    const q = search.toLowerCase();
    const v = vehicles.find(x => x.vehicle_id.toLowerCase().includes(q));
    const w = [...warehouses, ...destinations].find(x => x.id.toLowerCase().includes(q) || x.name.toLowerCase().includes(q));
    if (v) { setSelected(v.vehicle_id); mapRef.current?.easeTo({ center: [v.lng, v.lat], zoom: 11, duration: 800 }); }
    else if (w) { setSelected(w.id); mapRef.current?.easeTo({ center: [w.lng, w.lat], zoom: 11, duration: 800 }); }
  };

  return (
    <div className="fade-in h-[calc(100vh-88px)] flex flex-col gap-3">
      {/* top bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <b className="text-[15px] flex items-center gap-2"><Truck size={16} className="text-[var(--accent)]" /> LIVE FLEET</b>
        <span className="badge badge-green">{vehicles.length} vehicles</span>
        <span className="badge badge-cyan">{warehouses.length} warehouses</span>
        <span className={`badge ${vehicles.filter(v => v.cargo.risk_level === "CRITICAL").length ? "badge-red pulse-red" : "badge-green"}`}>
          {vehicles.filter(v => ["HIGH", "CRITICAL"].includes(v.cargo.risk_level)).length} at risk
        </span>
        {meta && <span className="badge">sim {Math.round(meta.sim_minute || st.fleetMeta?.simMinute || 0)}m · {meta.weather?.weather || st.fleetMeta?.weather || "…"}</span>}
        <div className="flex-1" />
        <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && searchGo()}
               placeholder="search TRUCK / WH / destination…" className="w-52 text-[12px]" />
        <button onClick={searchGo} className="btn text-[11px] flex items-center gap-1"><Search size={12} /> Find</button>
        <button onClick={togglePause} className="btn text-[11px] flex items-center gap-1">
          {paused ? <><Play size={12} /> Resume</> : <><Pause size={12} /> Pause</>}
        </button>
        <button onClick={doDemo} className="btn btn-amber text-[11px] flex items-center gap-1">
          <Zap size={12} /> Run Autonomous Demo
        </button>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-3 min-h-0">
        {/* left: filters + incidents */}
        <div className="col-span-2 flex flex-col gap-3 min-h-0">
          <div className="base-card p-3">
            <div className="text-[11px] text-[var(--text3)] uppercase mb-2 flex items-center gap-1"><Filter size={11} /> Filter</div>
            <div className="flex flex-wrap gap-1">
              {["ALL", "RISK", "CRITICAL", "IN_TRANSIT", "ARRIVED"].map(f => (
                <button key={f} onClick={() => setFilter(f)} className={`chip text-[10px] ${filter === f ? "on" : ""}`}>{f.replace("_", " ")}</button>
              ))}
            </div>
          </div>
          <div className="base-card p-3 flex-1 overflow-y-auto scroll-thin">
            <div className="text-[11px] text-[var(--text3)] uppercase mb-2">Active incidents</div>
            {(st.fleetEvents || []).filter((e: any) => e.type === "fleet.incident.created").slice(0, 6).map((e: any, i: number) => (
              <button key={i} onClick={() => { setSelected(e.vehicle_id);
                  const v = vehicles.find(x => x.vehicle_id === e.vehicle_id);
                  if (v) mapRef.current?.easeTo({ center: [v.lng, v.lat], zoom: 11.5, duration: 800 }); }}
                className={`w-full text-left p-2 rounded-lg mb-1.5 border ${e.severity === "CRITICAL" ? "border-[var(--red)]/60 pulse-red" : "border-[var(--amber)]/50"}`}>
                <div className="text-[11.5px] font-semibold flex justify-between">
                  <span>{e.vehicle_id}</span>
                  <span className={`text-[9.5px] ${e.severity === "CRITICAL" ? "text-[var(--red)]" : "text-[var(--amber)]"}`}>{e.severity}</span>
                </div>
                <div className="text-[10px] text-[var(--text3)]">{e.root_cause?.replace(/_/g, " ")}</div>
              </button>
            ))}
            {!(st.fleetEvents || []).some((e: any) => e.type === "fleet.incident.created") &&
              <div className="text-[11px] text-[var(--text3)] py-3">no incidents — inject a failure or run the demo</div>}
          </div>
        </div>

        {/* center: map */}
        <div className="col-span-7 base-card overflow-hidden relative">
          <div ref={containerRef} className="absolute inset-0" />
          {routeData?.geometry && (
            <svg className="absolute inset-0 pointer-events-none w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              <polyline fill="none" stroke="#38bdf8" strokeWidth="0.4" strokeOpacity="0.7"
                        points={routeData.geometry.map((p: number[]) => `${p[0]},${p[1]}`).join(" ")} />
            </svg>
          )}
          {following && (
            <button onClick={() => setFollowing(null)}
                    className="absolute top-3 left-3 z-10 btn btn-primary text-[11px]">
              FOLLOWING {following} — stop
            </button>
          )}
          <div className="absolute bottom-2 right-2 text-[9.5px] text-[var(--text3)] bg-[#0b1018cc] px-2 py-1 rounded">
            ● vehicle ◆ warehouse ✦ destination | SIMULATION ONLY
          </div>
        </div>

        {/* right: vehicle panel / warehouse + AI */}
        <div className="col-span-3 flex flex-col gap-3 min-h-0">
          <AnimatePresence mode="wait">
            {selSnap ? (
              <motion.div key={selSnap.vehicle_id} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
                          className="base-card p-3 overflow-y-auto scroll-thin">
                <div className="flex items-center justify-between mb-2">
                  <b className="text-[14px]">{selSnap.vehicle_id}</b>
                  <span className={`badge ${selSnap.cargo.risk_level === "CRITICAL" ? "badge-red" : selSnap.cargo.risk_level === "HIGH" ? "badge-amber" : "badge-green"}`}>
                    {selSnap.cargo.risk_level} RISK
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-[var(--text2)]">
                  <Stat l="Speed" v={`${selSnap.speed_kmh} km/h`} />
                  <Stat l="Temp" v={`${selSnap.refrigeration.temperature}°C`}
                        hot={selSnap.refrigeration.compressor_status !== "ONLINE"} />
                  <Stat l="ETA" v={`${selSnap.trip.eta_min} min`} />
                  <Stat l="Remaining" v={`${selSnap.trip.distance_remaining_km} km`} />
                  <Stat l="Cargo" v={`${selSnap.cargo.cargo_type.replace("_", " ")} · ${selSnap.cargo.load_percent}%`} />
                  <Stat l="Cargo health" v={`${selSnap.cargo.cargo_health}%`} />
                  <Stat l="Compressor" v={selSnap.refrigeration.compressor_status}
                        hot={selSnap.refrigeration.compressor_status !== "ONLINE"} />
                  <Stat l="Door" v={selSnap.refrigeration.door_open ? "OPEN" : "SHUT"} hot={selSnap.refrigeration.door_open} />
                  <Stat l="Energy" v={selSnap.energy_type === "ELECTRIC"
                     ? `🔋 ${selSnap.vehicle.battery_percent}%` : `⛽ ${selSnap.vehicle.fuel_percent}%`} />
                  <Stat l="Veh. health" v={`${selSnap.vehicle.vehicle_health}%`} />
                  <Stat l="Driver" v={`${selSnap.driver.name} (${selSnap.driver.driving_score})`} />
                  <Stat l="Dest" v={selSnap.trip.destination_id} />
                  {selSnap.cargo.time_to_critical_min != null &&
                    <Stat l="Time to critical" v={`${selSnap.cargo.time_to_critical_min} min`} hot />}
                </div>
                <div className="flex gap-1.5 mt-3 flex-wrap">
                  <button onClick={() => setFollowing(following === selSnap.vehicle_id ? null : selSnap.vehicle_id)}
                          className="btn text-[10.5px]">{following === selSnap.vehicle_id ? "Unfollow" : "Track Vehicle"}</button>
                  <button onClick={() => doInject(selSnap.vehicle_id)} className="btn btn-red text-[10.5px]">Inject Failure</button>
                  <button onClick={async () => {
                    const rc = await api(`/api/fleet/route-compare/${selSnap.vehicle_id}`);
                    setDecision({ ...rc, vehicle_id: selSnap.vehicle_id, manual: true });
                  }} className="btn btn-primary text-[10.5px]">AI Analysis</button>
                </div>
              </motion.div>
            ) : selWh ? (
              <motion.div key={selWh.id} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="base-card p-3">
                <b className="text-[13px]">{selWh.name}</b>
                <div className="grid grid-cols-2 gap-1 mt-2 text-[11px] text-[var(--text2)]">
                  <Stat l="Status" v={selWh.status} />
                  <Stat l="Free capacity" v={`${selWh.available_capacity} / ${selWh.capacity}u`} />
                  <Stat l="Queue" v={`${selWh.queue_min} min`} />
                  <Stat l="Docks" v={`${selWh.docks - selWh.busy_docks}/${selWh.docks} free`} />
                </div>
              </motion.div>
            ) : (
              <div className="base-card p-6 text-[12px] text-[var(--text3)] text-center">
                Select a vehicle or warehouse on the map
              </div>
            )}
          </AnimatePresence>

          {/* AI decision card */}
          <AnimatePresence>
            {decision && (
              <motion.div key={decision.decision + (decision.target || "")}
                          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                          className="base-card p-3 border-[var(--cyan)]/40">
                <div className="flex items-center gap-1.5 text-[12px] font-semibold text-[var(--cyan)] mb-1.5">
                  <Bot size={13} /> AI FLEET COORDINATOR
                </div>
                <div className="text-[11px] text-[var(--text2)] mb-1">
                  <b>{decision.vehicle_id}</b> — <b className={decision.decision === "DIVERT" ? "text-[var(--amber)]" : "text-[var(--green)]"}>{decision.decision}</b>
                  {decision.target ? ` -> ${decision.target}` : ""}
                </div>
                <div className="text-[10.5px] text-[var(--text3)] leading-relaxed">{decision.reason}</div>
                {(decision.candidates || []).filter((c: any) => c.compatible).slice(0, 3).map((c: any) => (
                  <div key={c.id} className="flex justify-between text-[10px] text-[var(--text2)] mt-1 border-t border-[var(--border)] pt-1">
                    <span>{c.name}</span>
                    <span>{c.eta_total_min}m · score {c.score}</span>
                  </div>
                ))}
                {decision.manual && <button onClick={() => setDecision(null)} className="btn text-[10px] mt-2">close</button>}
              </motion.div>
            )}
          </AnimatePresence>

          {/* event feed */}
          <div className="base-card p-3 flex-1 overflow-hidden flex flex-col min-h-[140px]">
            <div className="text-[11px] text-[var(--text3)] uppercase mb-1.5">Live events</div>
            <div className="flex-1 overflow-y-auto scroll-thin space-y-1">
              {(st.fleetEvents || []).slice(0, 24).map((e: any, i: number) => (
                <div key={i} className="text-[10.5px] flex gap-2 leading-snug">
                  <span className="text-[var(--text3)] shrink-0">
                    {new Date((e.ts || e.payload?.ts || Date.now() * (e.payload?.ts ? 1 : 0)) * (e.payload?.ts ? 1000 : 1)).toLocaleTimeString?.() || ""}
                  </span>
                  <span className="text-[var(--text2)]">
                    {e.type === "vehicle.event" && (e.payload?.text || "")}
                    {e.type === "fleet.incident.created" && `⚠ INCIDENT ${e.vehicle_id}: ${e.root_cause}`}
                    {e.type === "ai.route.decision" && `🤖 AI ${e.decision} -> ${e.target}`}
                    {e.type === "vehicle.route.changed" && `🔀 ${e.vehicle_id} rerouted -> ${e.new_target}`}
                    {e.type === "cargo.transferred" && `📦 ${e.vehicle_id} delivered ${e.units}u to ${e.facility_id}`}
                    {e.type === "vehicle.failure.injected" && `⚡ ${e.vehicle_id}: ${e.failure}`}
                  </span>
                </div>
              ))}
              {!(st.fleetEvents || []).length && <div className="text-[11px] text-[var(--text3)]">waiting for events…</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ l, v, hot }: { l: string; v: string; hot?: boolean }) {
  return (
    <div>
      <span className="text-[var(--text3)]">{l}</span>{" "}
      <b className={hot ? "text-[var(--red)]" : "text-[var(--text)]"}>{v}</b>
    </div>
  );
}

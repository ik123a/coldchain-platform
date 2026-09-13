"use client";
import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useStore } from "@/lib/store";
import { api, post } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Maximize2, Minimize2, Pause, Play, Search, Truck, Zap } from "lucide-react";
import { FleetTable } from "@/components/live-map/FleetTable";

const RISK_COLORS: Record<string, string> = {
  LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#f97316", CRITICAL: "#f87171",
};

interface VSnap {
  vehicle_id: string; lat: number; lng: number; heading: number; speed_kmh: number;
  status: string; energy_type: string; type: string;
  trip: { eta_min: number; distance_remaining_km: number; destination_id: string; origin_id: string; route_progress_percent: number };
  refrigeration: { temperature: number; compressor_status: string; door_open: boolean };
  cargo: { cargo_type: string; load_percent: number; cargo_health: number; risk_level: string; risk_score: number; time_to_critical_min: number | null };
  driver: { name: string; driving_score: number };
  vehicle: { fuel_percent: number; battery_percent: number; vehicle_health: number };
  outside_temperature: number;
}

/** Split a route polyline at progress% into completed (solid) + upcoming (dashed). */
function splitRoute(geometry: [number, number][], progressPct: number) {
  const total = geometry.length - 1;
  const cut = Math.max(1, Math.min(total, Math.round(total * progressPct / 100)));
  return { done: geometry.slice(0, cut + 1), todo: geometry.slice(cut) };
}

export default function LiveMapPage() {
  const { st } = useStore();
  const mapRef = useRef<MLMap | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevRef = useRef<Map<string, VSnap>>(new Map());
  const nextRef = useRef<Map<string, VSnap>>(new Map());
  const lerpRef = useRef(1);
  const trailsRef = useRef<Map<string, [number, number][]>>(new Map());
  const followRef = useRef<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [following, setFollowing] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState("ALL");
  const [routeData, setRouteData] = useState<any>(null);
  const [decision, setDecision] = useState<any>(null);
  const [geo, setGeo] = useState<{ warehouses: any[]; destinations: any[] }>({ warehouses: [], destinations: [] });
  const [search, setSearch] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [showTimeline, setShowTimeline] = useState(true);
  const [timelineTab, setTimelineTab] = useState<"events" | "timeline">("events");
  const [vehicleHistory, setVehicleHistory] = useState<any[]>([]);
  const [clock, setClock] = useState(0);

  const vehicles = (st.fleetVehicles || []) as VSnap[];
  const fleetEvents = (st.fleetEvents || []) as any[];

  useEffect(() => {
    api("/api/fleet/state").then((s: any) =>
      setGeo({ warehouses: s.warehouses, destinations: s.destinations })).catch(() => {});
    setFullscreen(localStorage.getItem("lm-fullscreen") === "1");
  }, []);

  useEffect(() => {
    if (!vehicles.length) return;
    prevRef.current = nextRef.current.size ? nextRef.current : new Map(vehicles.map(v => [v.vehicle_id, v]));
    nextRef.current = new Map(vehicles.map(v => [v.vehicle_id, v]));
    lerpRef.current = 0;
    const trails = trailsRef.current;
    for (const v of vehicles) {
      const t = trails.get(v.vehicle_id) || [];
      t.push([v.lng, v.lat]);
      trails.set(v.vehicle_id, t.slice(-40));
    }
    setClock(c => c + 1);
  }, [st.fleetVehicles]);

  // ---------- map init ----------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const TRUCK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="46" height="46" viewBox="0 0 46 46">
      <path d="M6 16 L26 16 L26 27 L6 27 Z" fill="#e6edf5" stroke="#0b1018" stroke-width="2"/>
      <path d="M26 20 L36 20 L40 25 L40 27 L26 27 Z" fill="#9db4d0" stroke="#0b1018" stroke-width="2"/>
      <circle cx="13" cy="30" r="4" fill="#0b1018" stroke="#e6edf5" stroke-width="2"/>
      <circle cx="34" cy="30" r="4" fill="#0b1018" stroke="#e6edf5" stroke-width="2"/>
      <path d="M14 14 L20 14 L20 9 L14 9 Z" fill="#7ec8ff"/>
    </svg>`;
    const img = new Image(46, 46);
    img.src = "data:image/svg+xml;base64," + (typeof window !== "undefined"
      ? window.btoa(unescape(encodeURIComponent(TRUCK_SVG))) : "");

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [77.10, 28.58],
      zoom: 9.3,
      style: {
        version: 8,
        sources: {
          osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                 tileSize: 256, attribution: "© OpenStreetMap contributors" },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#0b1018" } },
          { id: "osm-tiles", type: "raster", source: "osm", paint: { "raster-opacity": 0.75 } },
        ],
      } as any,
      attributionControl: false,
    });
    mapRef.current = map;
    map.on("load", () => {
      map.addImage("truck-icon", img);
      map.addSource("wh", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("dest", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("veh", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("trail", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("inc", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "wh-c", type: "circle", source: "wh",
        paint: { "circle-radius": 9, "circle-color": "#38bdf8",
                 "circle-stroke-color": "#7dd3fc", "circle-stroke-width": 1.5 },
      });
      map.addLayer({
        id: "wh-l", type: "symbol", source: "wh",
        layout: { "text-field": ["get", "label"], "text-size": 9.5, "text-offset": [0, 1.2], "text-anchor": "top" },
        paint: { "text-color": "#7dd3fc", "text-halo-color": "#0b1018", "text-halo-width": 1.2 },
      });
      map.addLayer({
        id: "dest-c", type: "circle", source: "dest",
        paint: { "circle-radius": 5.5, "circle-color": "#a78bfa",
                 "circle-stroke-color": "#c4b5fd", "circle-stroke-width": 1 },
      });
      map.addLayer({
        id: "trail-line", type: "line", source: "trail",
        paint: { "line-color": "#38bdf8", "line-width": 1.6, "line-opacity": 0.4 },
        layout: { "line-cap": "round" },
      });
      map.addLayer({
        id: "route-line", type: "line", source: "route",
        paint: { "line-color": ["get", "color"], "line-width": 3,
                 "line-opacity": 0.85, "line-dasharray": ["get", "dash"] },
        layout: { "line-cap": "round" },
      });
      map.addLayer({
        id: "inc-pulse", type: "circle", source: "inc",
        paint: { "circle-radius": 18, "circle-color": "#f8717122",
                 "circle-stroke-color": "#f87171", "circle-stroke-width": 1.2 },
      });
      map.addLayer({
        id: "inc-core", type: "circle", source: "inc",
        paint: { "circle-radius": 6, "circle-color": "#f87171" },
      });
      map.addLayer({
        id: "veh-halo", type: "circle", source: "veh",
        paint: { "circle-radius": 13, "circle-color": ["get", "riskColor"], "circle-opacity": 0.18 },
      });
      map.addLayer({
        id: "veh-icon", type: "symbol", source: "veh",
        layout: {
          "icon-image": "truck-icon", "icon-size": 0.65,
          "icon-rotate": ["get", "heading"],
          "icon-allow-overlap": true, "icon-rotation-alignment": "map",
        },
      });
      map.addLayer({
        id: "veh-label", type: "symbol", source: "veh",
        layout: { "text-field": ["get", "label"], "text-size": 9.5, "text-offset": [0, -1.7] },
        paint: { "text-color": "#c9d5e4", "text-halo-color": "#0b1018", "text-halo-width": 1.4 },
      });
      map.on("click", "veh-icon", (e: any) => {
        const vid = e.features?.[0]?.properties?.vehicle_id;
        if (vid) setSelected(vid);
      });
      map.on("click", "wh-c", (e: any) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) setSelected(id);
      });
      map.on("click", "inc-core", (e: any) => {
        const vid = e.features?.[0]?.properties?.vehicle_id;
        if (vid) { setSelected(vid);
          const v = nextRef.current.get(vid);
          if (v) map.easeTo({ center: [v.lng, v.lat], zoom: 11.5, duration: 700 }); }
      });
      for (const lyr of ["veh-icon", "wh-c", "dest-c", "inc-core"]) {
        map.on("mouseenter", lyr, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", lyr, () => (map.getCanvas().style.cursor = ""));
      }
    });
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // static geo
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded() || (!geo.warehouses.length && !geo.destinations.length)) return;
    (map.getSource("wh") as GeoJSONSource)?.setData({
      type: "FeatureCollection",
      features: geo.warehouses.map(w => ({
        type: "Feature", geometry: { type: "Point", coordinates: [w.lng, w.lat] },
        properties: { id: w.id, label: `${w.name} · ${w.available_capacity}u` },
      })),
    } as any);
    (map.getSource("dest") as GeoJSONSource)?.setData({
      type: "FeatureCollection",
      features: geo.destinations.map(d => ({
        type: "Feature", geometry: { type: "Point", coordinates: [d.lng, d.lat] },
        properties: { id: d.id, label: d.name },
      })),
    } as any);
  }, [geo, clock]);

  // rAF interpolation
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      const map = mapRef.current;
      if (map && map.isStyleLoaded() && nextRef.current.size) {
        lerpRef.current = Math.min(1, lerpRef.current + 0.03);
        const t = lerpRef.current;
        const feats: any[] = [];
        for (const [vid, nxt] of nextRef.current) {
          const prv = prevRef.current.get(vid) || nxt;
          const lat = prv.lat + (nxt.lat - prv.lat) * t;
          const lng = prv.lng + (nxt.lng - prv.lng) * t;
          feats.push({
            type: "Feature", geometry: { type: "Point", coordinates: [lng, lat] },
            properties: {
              vehicle_id: vid, heading: nxt.heading,
              riskColor: RISK_COLORS[nxt.cargo?.risk_level || "LOW"],
              label: `${vid.replace("TRUCK-", "T")} ${Math.round(nxt.speed_kmh)} ${nxt.refrigeration?.temperature}°`,
            },
          });
        }
        (map.getSource("veh") as GeoJSONSource)?.setData({ type: "FeatureCollection", features: feats } as any);
        const tfeats: any[] = [];
        for (const [vid, pts] of trailsRef.current) {
          if (pts.length < 2) continue;
          tfeats.push({ type: "Feature", geometry: { type: "LineString", coordinates: pts },
                        properties: { vehicle_id: vid } });
        }
        (map.getSource("trail") as GeoJSONSource)?.setData({ type: "FeatureCollection", features: tfeats } as any);
        if (followRef.current) {
          const nxt = nextRef.current.get(followRef.current);
          if (nxt) map.easeTo({ center: [nxt.lng, nxt.lat], duration: 320 });
        }
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  // incident pins
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const feats = fleetEvents.filter(e => e.type === "fleet.incident.created").slice(0, 10).map((e: any) => {
      const s = e.snapshot || {};
      return { type: "Feature",
               geometry: { type: "Point", coordinates: [s.lng || 77.1, s.lat || 28.58] },
               properties: { vehicle_id: e.vehicle_id, severity: e.severity, cause: e.root_cause } };
    });
    (map.getSource("inc") as GeoJSONSource)?.setData({ type: "FeatureCollection", features: feats } as any);
  }, [fleetEvents.length]);

  // selected vehicle: route + history
  useEffect(() => {
    if (!selected || !selected.startsWith("TRUCK")) { setRouteData(null); setVehicleHistory([]); return; }
    api(`/api/fleet/vehicle/${selected}`).then((d: any) => {
      setRouteData(d);
      setVehicleHistory(d.recent_events || []);
    }).catch(() => {});
  }, [selected, fleetEvents.length]);

  // split-path rendering: solid behind, dashed ahead
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const feats: any[] = [];
    if (routeData?.geometry) {
      const snap = vehicles.find(v => v.vehicle_id === selected);
      const pct = snap?.trip?.route_progress_percent ?? 50;
      const { done, todo } = splitRoute(routeData.geometry as [number, number][], pct);
      feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: done },
                   properties: { color: "#34d399", dash: [1, 0] } });
      feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: todo },
                   properties: { color: "#38bdf8", dash: [2, 1.5] } });
    }
    (map.getSource("route") as GeoJSONSource)?.setData({ type: "FeatureCollection", features: feats } as any);
  }, [routeData, vehicles, selected]);

  useEffect(() => { followRef.current = following; }, [following]);

  useEffect(() => {
    const ev = fleetEvents.find(e => e.type === "ai.route.decision");
    if (ev) setDecision(ev);
  }, [fleetEvents.length]);

  const toggleFullscreen = () => {
    const next = !fullscreen;
    setFullscreen(next);
    localStorage.setItem("lm-fullscreen", next ? "1" : "0");
  };
  const doDemo = () => post("/api/fleet/demo");
  const togglePause = async () => setPaused((await post("/api/fleet/pause")).paused);
  const selSnap = vehicles.find(v => v.vehicle_id === selected);
  const selWh = geo.warehouses.find(w => w.id === selected);

  const searchGo = () => {
    const q = search.toLowerCase();
    const v = vehicles.find(x => x.vehicle_id.toLowerCase().includes(q));
    const w = [...geo.warehouses, ...geo.destinations].find(x => x.id.toLowerCase().includes(q) || x.name.toLowerCase().includes(q));
    if (v) { setSelected(v.vehicle_id); mapRef.current?.flyTo({ center: [v.lng, v.lat], zoom: 11 }); }
    else if (w) { setSelected(w.id); mapRef.current?.flyTo({ center: [w.lng, w.lat], zoom: 11 }); }
  };

  const tableSpan = fullscreen ? "hidden" : "col-span-4";
  const mapSpan = fullscreen ? "col-span-12" : "col-span-8";

  return (
    <div className="fade-in h-[calc(100vh-88px)] flex flex-col gap-3">
      {/* top bar */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <b className="text-[15px] flex items-center gap-2"><Truck size={16} className="text-[var(--accent)]" /> LIVE FLEET</b>
        <span className="badge badge-green">{vehicles.length} vehicles</span>
        <span className={`badge ${vehicles.filter(v => v.cargo.risk_level === "CRITICAL").length ? "badge-red pulse-red" : "badge-green"}`}>
          {vehicles.filter(v => ["HIGH", "CRITICAL"].includes(v.cargo.risk_level)).length} at risk
        </span>
        <span className="badge">sim {Math.round((st as any).fleetMeta?.simMinute || 0)}m · {(st as any).fleetMeta?.weather || "…"}</span>
        <div className="flex-1" />
        <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && searchGo()}
               placeholder="search TRUCK-104 / WH-001…" className="w-52 text-[12px]" />
        <button onClick={searchGo} className="btn text-[11px]"><Search size={12} /></button>
        <button onClick={togglePause} className="btn text-[11px] flex items-center gap-1">
          {paused ? <><Play size={12} /> Resume</> : <><Pause size={12} /> Pause</>}
        </button>
        <button onClick={doDemo} className="btn btn-amber text-[11px] flex items-center gap-1">
          <Zap size={12} /> Run Autonomous Demo
        </button>
        <button onClick={toggleFullscreen} className="btn text-[11px] flex items-center gap-1">
          {fullscreen ? <><Minimize2 size={12} /> Windowed</> : <><Maximize2 size={12} /> Fullscreen</>}
        </button>
      </div>

      <div className="flex-1 grid grid-cols-12 gap-3 min-h-0">
        {/* table column (Tive windowed view) */}
        <div className={`${tableSpan} base-card p-3 min-h-0`}>
          <FleetTable vehicles={vehicles} events={fleetEvents} filter={filter} setFilter={setFilter}
                      onSelect={(vid) => { setSelected(vid);
                        const v = vehicles.find(x => x.vehicle_id === vid);
                        if (v) mapRef.current?.flyTo({ center: [v.lng, v.lat], zoom: 10.5 }); }}
                      selected={selected} />
        </div>

        {/* map + drawer column */}
        <div className={`${mapSpan} flex flex-col gap-3 min-h-0`}>
          <div className="base-card overflow-hidden relative flex-1 min-h-0">
            <div ref={containerRef} className="absolute inset-0" />
            {following && (
              <button onClick={() => setFollowing(null)} className="absolute top-3 left-3 z-10 btn btn-primary text-[11px]">
                FOLLOWING {following} — stop
              </button>
            )}
            <div className="absolute bottom-2 left-2 text-[9.5px] text-[var(--text3)] bg-[#0b1018cc] px-2 py-1 rounded flex gap-3">
              <span>━ completed</span><span className="text-[var(--cyan)]">┅ upcoming</span>
              <span>🚚 vehicle</span><span>⚠ incident</span>
              <span className="text-[var(--cyan)]">SIMULATION ONLY</span>
            </div>

            {/* floating vehicle drawer */}
            <AnimatePresence>
              {(selSnap || selWh) && (
                <motion.div key={(selSnap?.vehicle_id || selWh?.id) || "x"}
                            initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                            className="absolute top-3 right-3 z-10 w-[300px] max-h-[75%] overflow-y-auto scroll-thin base-card p-3">
                  {selSnap ? (
                    <>
                      <div className="flex items-center justify-between mb-2">
                        <b className="text-[13.5px]">{selSnap.vehicle_id}</b>
                        <span className={`badge ${selSnap.cargo.risk_level === "CRITICAL" ? "badge-red" : selSnap.cargo.risk_level === "HIGH" ? "badge-amber" : "badge-green"}`}>
                          {selSnap.cargo.risk_level} RISK
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-[var(--text2)]">
                        <Stat l="Speed" v={`${selSnap.speed_kmh} km/h`} />
                        <Stat l="Inside" v={`${selSnap.refrigeration.temperature}°C`} hot={selSnap.refrigeration.compressor_status !== "ONLINE"} />
                        <Stat l="Outside" v={`${selSnap.outside_temperature}°C`} />
                        <Stat l="ETA" v={`${selSnap.trip.eta_min} min`} />
                        <Stat l="Remaining" v={`${selSnap.trip.distance_remaining_km} km`} />
                        <Stat l="Progress" v={`${selSnap.trip.route_progress_percent}%`} />
                        <Stat l="Cargo" v={`${selSnap.cargo.cargo_type.replace("_", " ")} ${selSnap.cargo.load_percent}%`} />
                        <Stat l="Health" v={`${selSnap.cargo.cargo_health}%`} />
                        <Stat l="Compressor" v={selSnap.refrigeration.compressor_status} hot={selSnap.refrigeration.compressor_status !== "ONLINE"} />
                        <Stat l="Energy" v={selSnap.energy_type === "ELECTRIC" ? `🔋 ${selSnap.vehicle.battery_percent}%` : `⛽ ${selSnap.vehicle.fuel_percent}%`} />
                        <Stat l="Driver" v={`${selSnap.driver.name} (${selSnap.driver.driving_score})`} />
                        <Stat l="Route" v={`${selSnap.trip.origin_id} → ${selSnap.trip.destination_id}`} />
                        {selSnap.cargo.time_to_critical_min != null &&
                          <Stat l="Time to critical" v={`${selSnap.cargo.time_to_critical_min} min`} hot />}
                      </div>
                      <div className="flex gap-1.5 mt-3 flex-wrap">
                        <button onClick={() => setFollowing(following === selSnap.vehicle_id ? null : selSnap.vehicle_id)}
                                className="btn text-[10.5px]">{following === selSnap.vehicle_id ? "Unfollow" : "Track Vehicle"}</button>
                        <button onClick={() => post(`/api/fleet/vehicle/${selSnap.vehicle_id}/inject`, { failure: "compressor_failure" })}
                                className="btn btn-red text-[10.5px]">Inject Failure</button>
                        <button onClick={async () => {
                          const rc = await api(`/api/fleet/route-compare/${selSnap.vehicle_id}`);
                          setDecision({ ...rc, vehicle_id: selSnap.vehicle_id, manual: true });
                        }} className="btn btn-primary text-[10.5px]">AI Analysis</button>
                      </div>
                    </>
                  ) : selWh && (
                    <>
                      <b className="text-[13px]">{selWh.name}</b>
                      <div className="grid grid-cols-2 gap-1 mt-2 text-[11px] text-[var(--text2)]">
                        <Stat l="Status" v={selWh.status} />
                        <Stat l="Free" v={`${selWh.available_capacity}/${selWh.capacity}u`} />
                        <Stat l="Queue" v={`${selWh.queue_min} min`} />
                        <Stat l="Docks" v={`${selWh.docks - selWh.busy_docks}/${selWh.docks}`} />
                        <Stat l="Cargo" v={selWh.cargo_types.join(", ")} />
                        <Stat l="Processing" v={`${selWh.proc_min} min`} />
                      </div>
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* timeline / events drawer */}
          <div className="base-card p-3 shrink-0" style={{ height: showTimeline ? 132 : 40 }}>
            <div className="flex items-center gap-2 mb-1.5">
              <button onClick={() => setShowTimeline(s => !s)} className="chip text-[10px]">
                {showTimeline ? "▾" : "▸"} {showTimeline ? "hide" : "show"}
              </button>
              <div className="flex gap-1">
                <button onClick={() => setTimelineTab("events")} className={`chip text-[10px] ${timelineTab === "events" ? "on" : ""}`}>Live events</button>
                <button onClick={() => setTimelineTab("timeline")} className={`chip text-[10px] ${timelineTab === "timeline" ? "on" : ""}`}>
                  {selected ? `${selected} timeline` : "vehicle timeline"}
                </button>
              </div>
            </div>
            {showTimeline && (
              <div className="h-[84px] overflow-y-auto scroll-thin space-y-0.5">
                {(timelineTab === "events"
                  ? fleetEvents.slice(0, 30)
                  : [...vehicleHistory].reverse().map((e: any) => ({
                      type: "vehicle.event", payload: e.payload,
                      ts: e.ts, vehicle_id: e.payload?.vehicle_id,
                    }))
                ).map((e: any, i: number) => (
                  <div key={i} className="text-[10.5px] flex gap-2 leading-snug">
                    <span className="text-[var(--text3)] shrink-0">
                      {e.ts ? new Date(e.ts * (e.ts > 1e12 ? 1 : 1000)).toLocaleTimeString() : ""}
                    </span>
                    <span className="text-[var(--text2)]">
                      {e.type === "vehicle.event" && (e.payload?.text || "")}
                      {e.type === "fleet.incident.created" && `⚠ INCIDENT ${e.vehicle_id}: ${e.root_cause} (${e.severity})`}
                      {e.type === "ai.route.decision" && `🤖 AI ${e.decision} → ${e.target} (conf ${e.confidence})`}
                      {e.type === "vehicle.route.changed" && `🔀 ${e.vehicle_id} rerouted → ${e.new_target} · ETA ${e.eta_min}m`}
                      {e.type === "cargo.transferred" && `📦 ${e.vehicle_id} delivered ${e.units}u to ${e.facility_id}`}
                      {e.type === "geofence.entered" && `📍 ${e.vehicle_id} entered ${e.type === "geofence.entered" ? e.fence : ""}`}
                      {e.type === "vehicle.failure.injected" && `⚡ ${e.vehicle_id}: ${e.failure} injected`}
                      {e.type === "weather.changed" && `🌦 weather → ${e.weather} (ambient ${e.ambient_c}°C)`}
                      {e.type === "traffic.changed" && `🚦 traffic ${e.segment} → ${e.level}`}
                    </span>
                  </div>
                ))}
                {timelineTab === "timeline" && !vehicleHistory.length &&
                  <div className="text-[11px] text-[var(--text3)]">select a vehicle to see its history</div>}
                {timelineTab === "events" && !fleetEvents.length &&
                  <div className="text-[11px] text-[var(--text3)]">waiting for events…</div>}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* AI decision card — floats bottom-left over everything */}
      <AnimatePresence>
        {decision && (
          <motion.div key={(decision.decision || "") + (decision.target || "") + (decision.vehicle_id || "")}
                      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className="fixed bottom-16 left-16 z-40 w-[340px] base-card p-3 border-[var(--cyan)]/40">
            <div className="flex items-center gap-1.5 text-[12px] font-semibold text-[var(--cyan)] mb-1.5">
              <Bot size={13} /> AI FLEET COORDINATOR {decision.manual && <span className="badge badge-cyan text-[9px]">manual query</span>}
            </div>
            <div className="text-[11px] text-[var(--text2)] mb-1">
              <b>{decision.vehicle_id}</b> — <b className={decision.decision === "DIVERT" ? "text-[var(--amber)]" : "text-[var(--green)]"}>{decision.decision}</b>
              {decision.target ? ` → ${decision.target}` : ""}
            </div>
            <div className="text-[10.5px] text-[var(--text3)] leading-relaxed">{decision.reason}</div>
            {(decision.candidates || []).filter((c: any) => c.compatible).slice(0, 3).map((c: any) => (
              <div key={c.id} className="flex justify-between text-[10px] text-[var(--text2)] mt-1 border-t border-[var(--border)] pt-1">
                <span>{c.name}</span>
                <span>ETA {c.eta_total_min}m · {c.distance_km}km · score {c.score}</span>
              </div>
            ))}
            <button onClick={() => setDecision(null)} className="btn text-[10px] mt-2">close</button>
          </motion.div>
        )}
      </AnimatePresence>
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

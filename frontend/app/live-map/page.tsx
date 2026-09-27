"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useStore } from "@/lib/store";
import { api, post } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Maximize2, Minimize2, Pause, Play, Radio, RotateCcw, Search, Truck, Zap } from "lucide-react";
import { FleetTable } from "@/components/live-map/FleetTable";
import { FloatingVehicleInspector } from "@/components/live-map/FloatingVehicleInspector";
import { DeepTelemetryDrawer } from "@/components/live-map/DeepTelemetryDrawer";
import { BorderBeam } from "@/components/ui/border-beam";
import { NumberTicker } from "@/components/ui/number-ticker";
import { StatusBeacon } from "@/components/ui/status-beacon";
import { ShimmerText } from "@/components/ui/shimmer-text";
import { WeatherOverlay } from "@/components/ui/weather-overlay";
import { MapMarkers, type MapPoint } from "@/components/ui/map-markers";
import { MapOverlay, type IncidentPin, type LL, type RouteGeom } from "@/components/ui/map-overlay";

const RISK_COLORS: Record<string, string> = {
  LOW: "#34d399", MEDIUM: "#fbbf24", HIGH: "#f97316", CRITICAL: "#f87171",
};

interface VSnap {
  vehicle_id: string; lat: number; lng: number; heading: number; speed_kmh: number;
  status: string; energy_type: string; type: string;
  trip: { route_id: string; eta_min: number; distance_remaining_km: number; destination_id: string; origin_id: string; route_progress_percent: number };
  refrigeration: { temperature: number; compressor_status: string; door_open: boolean };
  cargo: { cargo_type: string; load_percent: number; cargo_health: number; risk_level: string; risk_score: number; time_to_critical_min: number | null };
  driver: { name: string; driving_score: number };
  vehicle: { fuel_percent: number; battery_percent: number; vehicle_health: number };
  outside_temperature: number;
  alerts?: number;
}

/** Accepts epoch seconds, epoch millis, or an ISO string; never renders "Invalid Date". */
function formatEventTime(ts: unknown): string {
  if (ts === null || ts === undefined || ts === "") return "";
  let d: Date;
  if (typeof ts === "number") {
    d = new Date(ts > 1e12 ? ts : ts * 1000);
  } else if (typeof ts === "string" && /^\d+$/.test(ts)) {
    const n = Number(ts);
    d = new Date(n > 1e12 ? n : n * 1000);
  } else {
    d = new Date(ts as string);
  }
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatSimClock(simMinute: unknown): string {
  const m = typeof simMinute === "number" && Number.isFinite(simMinute) ? simMinute : 0;
  const total = Math.floor(m);
  const h = Math.floor(total / 60);
  const mm = total % 60;
  return `${h}h ${String(mm).padStart(2, "0")}m`;
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
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  const vehicles = (st.fleetVehicles || []) as VSnap[];
  const fleetEvents = (st.fleetEvents || []) as any[];

  // v.geom is not part of the vehicle snapshot, so it is fetched per vehicle and
  // re-fetched whenever trip.route_id changes (rebuild, divert, respawn).
  const [routeGeom, setRouteGeom] = useState<Map<string, { coords: LL[]; routeId: string }>>(new Map());
  const [staleGeom, setStaleGeom] = useState<Map<string, LL[]>>(new Map());
  const geomBusy = useRef<Set<string>>(new Set());

  const kpis = useMemo(() => {
    const atRisk = vehicles.filter(v => ["HIGH", "CRITICAL"].includes(v.cargo?.risk_level || "")).length;
    const excursions = vehicles.filter(v => typeof v.refrigeration?.temperature === "number" && (v.refrigeration.temperature as number) > 8).length;
    const tally = (t: string) => fleetEvents.filter((e: any) => e.type === t).length;
    return {
      activeTrucks: vehicles.length,
      inTransit: vehicles.filter(v => v.status === "IN_TRANSIT").length,
      atRisk,
      activeIncidents: vehicles.filter(v => (v.alerts || 0) > 0).length,
      excursions,
      reroutes: tally("vehicle.route.changed") + tally("ai.route.decision"),
      transfers: tally("cargo.transferred"),
      deliveries: fleetEvents.filter((e: any) => String(e.text || "").includes("delivered")).length,
    };
  }, [vehicles, fleetEvents]);

  /* Telemetry rail state — the signature device. Derived from the same
     counts the KPI bar shows, so the spine can never contradict a number.
     Precedence: temperature excursion (physical spoilage risk) beats risk
     score (predictive), which beats an open incident. */
  const { railState, railLabel } = useMemo(() => {
    const excursions = vehicles.filter(
      (v) => typeof v.refrigeration?.temperature === "number" &&
             (v.refrigeration.temperature as number) > 8
    ).length;
    const atRisk = vehicles.filter(
      (v) => ["HIGH", "CRITICAL"].includes(v.cargo?.risk_level || "")
    ).length;
    const alerting = vehicles.filter((v) => (v.alerts || 0) > 0).length;

    if (excursions > 0) {
      return {
        railState: "critical" as const,
        railLabel: `Fleet status: critical — ${excursions} vehicle${
          excursions === 1 ? "" : "s"
        } above the 8 degree Celsius cold-chain limit.`,
      };
    }
    if (atRisk > 0) {
      return {
        railState: "warning" as const,
        railLabel: `Fleet status: warning — ${atRisk} vehicle${
          atRisk === 1 ? "" : "s"
        } flagged at elevated cargo risk.`,
      };
    }
    if (alerting > 0) {
      return {
        railState: "warning" as const,
        railLabel: `Fleet status: warning — ${alerting} vehicle${
          alerting === 1 ? "" : "s"
        } carrying open alerts.`,
      };
    }
    return {
      railState: "nominal" as const,
      railLabel: "Fleet status: nominal — all vehicles within the cold-chain corridor.",
    };
  }, [vehicles]);

  const [simSpeed, setSimSpeed] = useState(1);
  const setSpeed = async (n: number) => {
    setSimSpeed(n);
    await post("/api/fleet/speed", { speed: n }).catch(() => {});
  };

  const mapPoints = useMemo<MapPoint[]>(() => {    const wh: MapPoint[] = (geo?.warehouses || []).map((w: any) => ({
      id: `wh-${w.id}`,
      lng: Number(w.lng),
      lat: Number(w.lat),
      tone: "selected" as const,
      label: w.id,
      sublabel: w.name,
      kind: "warehouse" as const,
    }));
    const fleet: MapPoint[] = vehicles.map((v: any) => {
      const temp = v.refrigeration?.temperature;
      const isSel = v.vehicle_id === selected;
      const tone: MapPoint["tone"] = isSel
        ? "selected"
        : typeof temp === "number" && temp > 8
        ? "critical"
        : v.cargo?.risk_level === "HIGH" || v.cargo?.risk_level === "MEDIUM"
        ? "warning"
        : "nominal";
      return {
        id: v.vehicle_id,
        lng: Number(v.lng),
        lat: Number(v.lat),
        tone,
        label: isSel ? v.vehicle_id : undefined,
        sublabel: typeof temp === "number" ? `${temp.toFixed(1)}°C core` : undefined,
        heading: Number(v.heading) || 0,
        kind: (v.type === "SERVICE_TRUCK" ? "service" : "vehicle") as "vehicle" | "service",
      };
    });
    return [...wh, ...fleet];
  }, [geo?.warehouses, vehicles, selected]);

  const overlayRoutes = useMemo<Map<string, RouteGeom>>(() => {
    const out = new Map<string, RouteGeom>();
    for (const v of vehicles) {
      if (!v.vehicle_id.startsWith("TRUCK")) continue;
      const stale = staleGeom.get(v.vehicle_id);
      if (stale && stale.length > 1) {
        out.set(`${v.vehicle_id}::stale`, { done: stale, todo: [], tone: "stale" });
      }
      const g = routeGeom.get(v.vehicle_id);
      if (!g || g.coords.length < 2) continue;
      const pct = v.trip?.route_progress_percent ?? 0;
      const { done, todo } = splitRoute(g.coords, pct);
      const risk = v.cargo?.risk_level || "LOW";
      const tone: RouteGeom["tone"] = stale
        ? "reroute"
        : risk === "CRITICAL" ? "critical"
        : risk === "HIGH" || risk === "MEDIUM" ? "warning"
        : "normal";
      out.set(v.vehicle_id, { done, todo, tone });
    }
    return out;
  }, [vehicles, routeGeom, staleGeom]);

  const overlayTrails = useMemo<Map<string, LL[]>>(() => {
    const out = new Map<string, LL[]>();
    for (const [id, pts] of trailsRef.current) if (pts.length > 1) out.set(id, pts);
    return out;
  }, [clock]);

  const overlayIncidents = useMemo<IncidentPin[]>(() => {
    const risky = new Set(vehicles.filter(v => ["HIGH", "CRITICAL"].includes(v.cargo?.risk_level || "")).map(v => v.vehicle_id));
    return fleetEvents
      .filter((e: any) => e.type === "fleet.incident.created")
      .slice(-5)
      .map((e: any) => {
        const s = e.snapshot || {};
        const resolved = !risky.has(e.vehicle_id);
        return {
          id: `inc-${e.incident_id ?? e.vehicle_id}`,
          lng: Number(s.lng) || 0,
          lat: Number(s.lat) || 0,
          severity: resolved ? "RESOLVED" : String(e.severity || "MEDIUM").toUpperCase(),
          vehicle_id: e.vehicle_id,
          cause: e.root_cause,
        } satisfies IncidentPin;
      })
      .filter(p => p.lng !== 0 && p.lat !== 0);
  }, [fleetEvents.length, vehicles]);

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

  // ---------- route geometry (real backend data) ----------
  const lastRouteChange = useMemo(() => {
    const evs = fleetEvents.filter((e: any) => e.type === "vehicle.route.changed");
    return evs.length ? (evs[evs.length - 1] as any) : null;
  }, [fleetEvents]);

  useEffect(() => {
    const c = lastRouteChange;
    if (!c?.vehicle_id || !Array.isArray(c.geometry) || c.geometry.length < 2) return;
    const vid: string = c.vehicle_id;
    const prevEntry = routeGeom.get(vid);
    if (prevEntry) {
      setStaleGeom(s => { const n = new Map(s); n.set(vid, prevEntry.coords); return n; });
      window.setTimeout(() => {
        setStaleGeom(s => { const n = new Map(s); n.delete(vid); return n; });
      }, 15000);
    }
    setRouteGeom(prev => {
      const n = new Map(prev);
      n.set(vid, { coords: c.geometry as LL[], routeId: String(c.new_target ?? "") });
      return n;
    });
  }, [lastRouteChange]);

  useEffect(() => {
    const want: Array<{ id: string; routeId: string }> = [];
    for (const v of vehicles) {
      if (!v.vehicle_id.startsWith("TRUCK")) continue;
      const rid = String(v.trip?.route_id ?? "");
      const have = routeGeom.get(v.vehicle_id);
      if (!have || (rid && have.routeId !== rid)) want.push({ id: v.vehicle_id, routeId: rid });
    }
    if (!want.length) return;
    const fresh = want.filter(w => !geomBusy.current.has(w.id));
    if (!fresh.length) return;
    for (const w of fresh) geomBusy.current.add(w.id);
    let alive = true;
    Promise.all(fresh.map(w =>
      api(`/api/fleet/vehicle/${w.id}`)
        .then((d: any) => {
          if (!alive || !Array.isArray(d?.geometry) || d.geometry.length < 2) return;
          setRouteGeom(prev => {
            const n = new Map(prev);
            if (!n.has(w.id)) n.set(w.id, { coords: d.geometry as LL[], routeId: w.routeId });
            return n;
          });
        })
        .catch(() => {})
        .finally(() => geomBusy.current.delete(w.id))
    ));
    return () => { alive = false; };
  }, [vehicles, routeGeom]);

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
          esriBase: {
            type: "raster",
            tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
            tileSize: 256,
            attribution: "© Esri, HERE, Garmin, © OpenStreetMap contributors",
          },
          esriLabels: {
            type: "raster",
            tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"],
            tileSize: 256,
          },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#080A0F" } },
          { id: "esri-base", type: "raster", source: "esriBase" },
          { id: "esri-labels", type: "raster", source: "esriLabels" },
        ],
      } as any,
      attributionControl: false,
    });
    mapRef.current = map;
    setMapReady(false);
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(containerRef.current);
    map.on("load", () => {
      setMapReady(true);
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
    return () => { ro.disconnect(); setMapReady(false); map.remove(); mapRef.current = null; };
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
          if (nxt) map.easeTo({ center: [nxt.lng, nxt.lat], duration: 80 });
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
      {/* Page header — h1 gives the document an outline; the rail is the
          always-visible fleet-health spine described in design-system/motion.md */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1
          className="telemetry-rail t-hero flex items-baseline gap-2.5 m-0"
          data-state={railState}
        >
          <Truck size={18} className="text-[var(--accent)] translate-y-0.5" aria-hidden />
          <span>Live Fleet</span>
          <span className="t-label text-[var(--text-dim)] font-normal tracking-[0.14em] uppercase">
            Delhi NCR Corridor
          </span>
          <span className="sr-only">{railLabel}</span>
        </h1>
        <span className="badge badge-green flex items-center gap-1.5">
          <StatusBeacon status="online" size="sm" />
          <NumberTicker value={vehicles.length} className="text-emerald-400 font-bold" />
          <span>vehicles</span>
        </span>
        <span className={`badge flex items-center gap-1.5 ${vehicles.filter(v => v.cargo?.risk_level === "CRITICAL").length ? "badge-red pulse-red" : "badge-green"}`}>
          <StatusBeacon status={vehicles.filter(v => v.cargo?.risk_level === "CRITICAL").length ? "critical" : "warning"} size="sm" />
          <NumberTicker value={vehicles.filter(v => ["HIGH", "CRITICAL"].includes(v.cargo?.risk_level || "")).length} className={vehicles.filter(v => v.cargo?.risk_level === "CRITICAL").length ? "text-rose-400 font-bold" : "text-emerald-400 font-bold"} />
          <span>at risk</span>
        </span>
        <span className="badge" title={`Simulation minute ${Math.round((st as any).fleetMeta?.simMinute || 0)}`}>
          T+{formatSimClock((st as any).fleetMeta?.simMinute)}
          {" · "}
          {String((st as any).fleetMeta?.weather?.weather ?? "—").toUpperCase()}
          {typeof (st as any).fleetMeta?.ambient === "number" ? ` ${(st as any).fleetMeta.ambient.toFixed(1)}°C` : ""}
        </span>
        <div className="flex-1" />
        <div className="flex items-center gap-1.5 flex-wrap">
          {([["ACTIVE", kpis.activeTrucks, ""], ["TRANSIT", kpis.inTransit, ""],
             ["AT RISK", kpis.atRisk, kpis.atRisk ? "text-amber-400 font-bold" : "text-emerald-400 font-bold"],
             ["INCID", kpis.activeIncidents, kpis.activeIncidents ? "text-amber-400 font-bold" : "text-emerald-400 font-bold"],
             ["EXCURSION", kpis.excursions, kpis.excursions ? "text-rose-400 font-bold" : "text-emerald-400 font-bold"],
             ["REROUTE", kpis.reroutes, ""], ["XFER", kpis.transfers, ""],
             ["DELIV", kpis.deliveries, ""]] as Array<[string, number, string]>).map(([l, n, cls]) => (
            <span key={l} className="badge" title={l}>
              <span className="font-mono t-label text-slate-400">{l}</span>
              <span className={`font-mono t-body-sm ${cls || "text-slate-200 font-bold"}`}>{n}</span>
            </span>
          ))}
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-1">
          {[1, 2, 5, 10].map(n => (
            <button key={n} onClick={() => setSpeed(n)} title={`Set simulation speed to ${n}x`}
                    className={`chip t-micro font-mono ${simSpeed === n ? "on" : ""}`}>{n}x</button>
          ))}
          <select defaultValue="NORMAL" title="Weather scenario"
                  onChange={e => post("/api/fleet/weather", { weather: e.target.value })}
                  className="chip t-micro">
            {["NORMAL", "HEATWAVE", "RAIN", "FOG"].map(w => <option key={w} value={w}>{w}</option>)}
          </select>
          <button onClick={() => post("/api/fleet/inject-random")} title="Inject a random incident"
                  className="btn btn-amber t-label"><Zap size={12} /> Incident</button>
          <button onClick={() => post("/api/fleet/rebuild", { fleet_size: 12 })} title="Rebuild the fleet world"
                  className="btn t-label"><RotateCcw size={12} /></button>
        </div>
        <input value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && searchGo()}
               placeholder="Search vehicle / warehouse" aria-label="Search vehicle or warehouse" className="w-44 t-body-sm" />
        <button onClick={searchGo} className="btn t-label"><Search size={12} /></button>
        <button onClick={togglePause} className="btn t-label flex items-center gap-1">
          {paused ? <><Play size={12} /> Resume</> : <><Pause size={12} /> Pause</>}
        </button>
        <button onClick={doDemo} className="btn btn-amber t-label flex items-center gap-1">
          <Zap size={12} /> Run Autonomous Demo
        </button>
        <button onClick={toggleFullscreen} className="btn t-label flex items-center gap-1">
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
        <div className={`${mapSpan} relative flex flex-col gap-3 min-h-0`}>
          <div className="base-card overflow-hidden relative flex-1 min-h-0">
            <div ref={containerRef} className="h-full w-full" />
            <MapOverlay
              map={mapReady ? mapRef.current : null}
              routes={overlayRoutes}
              trails={overlayTrails}
              incidents={overlayIncidents}
              selected={selected}
              onIncidentClick={(p) => {
                if (!p.vehicle_id) return;
                setSelected(p.vehicle_id);
                const v = vehicles.find((x) => x.vehicle_id === p.vehicle_id);
                if (v) mapRef.current?.flyTo({ center: [v.lng, v.lat], zoom: 11 });
              }}
            />
            <MapMarkers map={mapReady ? mapRef.current : null} points={mapPoints} onSelect={(id) => { if (!id.startsWith("wh-")) { setSelected(id); const v = vehicles.find((x) => x.vehicle_id === id); if (v) mapRef.current?.flyTo({ center: [v.lng, v.lat], zoom: 10.5 }); } }} />
            {/* Simulated Weather Effect on Map */}
            <WeatherOverlay condition="heatwave" intensity={0.25} className="z-10 rounded-xl" />
            <AnimatePresence>
              {following && (
                <motion.div
                  initial={{ opacity: 0, y: -20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-3.5 py-1.5 rounded-full bg-[#0E121A]/95 backdrop-blur border border-cyan-500/40 shadow-xl flex items-center gap-3 t-body-sm font-mono">
                  <span className="flex items-center gap-1.5 text-cyan-300 font-bold">
                    <Radio size={12} className="text-cyan-400 breathe" />
                    FOLLOWING {following}
                  </span>
                  <button
                    onClick={() => setFollowing(null)}
                    className="t-micro uppercase font-bold text-slate-400 hover:text-white px-2 py-0.5 rounded bg-[#141B26] border border-[#1E2638] transition-colors">
                    Stop Following
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
            <div className="absolute bottom-2 left-2 t-micro text-[var(--text3)] bg-[#0b1018cc] px-2 py-1 rounded flex gap-3">
              <span>━ completed</span><span className="text-[var(--cyan)]">┅ upcoming</span>
              <span>🚚 vehicle</span><span>⚠ incident</span>
              <span className="text-[var(--cyan)]">SIMULATION ONLY</span>
            </div>

            {/* Progressive Disclosure: Level 1 Floating Inspector & Level 2 Deep Drawer */}
            <AnimatePresence>
              {selSnap && !drawerOpen && (
                <FloatingVehicleInspector
                  vehicle={selSnap}
                  onClose={() => setSelected(null)}
                  onOpenDrawer={() => setDrawerOpen(true)}
                  onTrack={() => setFollowing(following === selSnap.vehicle_id ? null : selSnap.vehicle_id)}
                  isTracking={following === selSnap.vehicle_id}
                  onInject={() => post(`/api/fleet/vehicle/${selSnap.vehicle_id}/inject`, { failure: "compressor_failure" })}
                />
              )}

              {selSnap && drawerOpen && (
                <DeepTelemetryDrawer
                  vehicle={selSnap}
                  onClose={() => setDrawerOpen(false)}
                  onApproveDiversion={async (vid, fac) => {
                    await post(`/api/fleet/vehicle/${vid}/action`, { action: "reroute_warehouse_beta" });
                    setFollowing(vid);
                    setDrawerOpen(false);
                  }}
                  onInjectFailure={() => post(`/api/fleet/vehicle/${selSnap.vehicle_id}/inject`, { failure: "compressor_failure" })}
                />
              )}

              {selWh && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute top-4 right-4 z-30 w-72 bg-[#0E121A]/95 backdrop-blur-md border border-[#1E2638] rounded-xl p-4 shadow-2xl text-slate-100 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-[#1E2638] pb-2">
                    <b className="t-body font-mono text-white">{selWh.name}</b>
                    <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-white t-body-sm">✕</button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 t-body-sm font-mono text-slate-300">
                    <Stat l="Status" v={selWh.status} />
                    <Stat l="Capacity" v={`${selWh.available_capacity}/${selWh.capacity}u`} />
                    <Stat l="Queue" v={`${selWh.queue_min} min`} />
                    <Stat l="Docks" v={`${selWh.docks - selWh.busy_docks}/${selWh.docks}`} />
                    <Stat l="Processing" v={`${selWh.proc_min} min`} />
                    <Stat l="Dock Temp" v="3.8°C" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* timeline / events drawer */}
          <div className="base-card p-3 shrink-0 relative overflow-hidden" style={{ height: showTimeline ? 132 : 40 }}>
            {showTimeline && <div className="scan-line opacity-20 pointer-events-none" />}
            <div className="flex items-center gap-2 mb-1.5">
              <button onClick={() => setShowTimeline(s => !s)} className="chip t-micro">
                {showTimeline ? "▾" : "▸"} {showTimeline ? "hide" : "show"}
              </button>
              <div className="flex gap-1">
                <button onClick={() => setTimelineTab("events")} className={`chip t-micro ${timelineTab === "events" ? "on" : ""}`}>Live events</button>
                <button onClick={() => setTimelineTab("timeline")} className={`chip t-micro ${timelineTab === "timeline" ? "on" : ""}`}>
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
                  <div key={i} className="t-micro flex gap-2 leading-snug">
                    <span className="text-[var(--text3)] shrink-0 tabular-nums">
                      {formatEventTime(e.ts)}
                    </span>
                    <span className="text-[var(--text2)]">
                      {e.type === "vehicle.event" && (e.payload?.text || "")}
                      {e.type === "fleet.incident.created" && `⚠ INCIDENT ${e.vehicle_id}: ${e.root_cause} (${e.severity})`}
                      {e.type === "ai.route.decision" && `🤖 AI ${e.decision} → ${e.target} (conf ${e.confidence})`}
                      {e.type === "vehicle.route.changed" && `🔀 ${e.vehicle_id} rerouted → ${e.new_target} · ETA ${e.eta_min}m`}
                      {e.type === "cargo.transferred" && `📦 ${e.vehicle_id} delivered ${e.units}u to ${e.facility_id}`}
                      {e.type === "geofence.entered" && `📍 ${e.vehicle_id} entered ${e.type === "geofence.entered" ? e.fence : ""}`}
                      {e.type === "vehicle.failure.injected" && `⚡ ${e.vehicle_id}: ${e.failure} injected`}
                      {e.type === "weather.changed" && `🌦 weather → ${e.weather?.weather ?? e.weather} (ambient ${e.weather?.ambient_c ?? e.ambient_c}°C)`}
                      {e.type === "traffic.changed" && `🚦 traffic ${e.segment} → ${e.level}`}
                    </span>
                  </div>
                ))}
                {timelineTab === "timeline" && !vehicleHistory.length &&
                  <div className="t-label text-[var(--text3)]">select a vehicle to see its history</div>}
                {timelineTab === "events" && !fleetEvents.length &&
                  <div className="t-label text-[var(--text3)]">waiting for events…</div>}
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
                      className="fixed bottom-16 left-16 z-40 w-[340px] base-card p-3 border-[var(--cyan)]/40 relative overflow-hidden">
            <BorderBeam
              size={90}
              duration={4}
              colorFrom={decision.decision === "DIVERT" ? "#f59e0b" : "#38bdf8"}
              colorTo={decision.decision === "DIVERT" ? "#06b6d4" : "#10b981"}
              borderWidth={1.5}
            />
            <div className="relative z-10">
              <div className="flex items-center gap-1.5 t-body-sm font-semibold text-[var(--cyan)] mb-1.5">
                <Bot size={13} />
                <ShimmerText className="t-body font-bold tracking-wide">
                  AI EMERGENCY REROUTE
                </ShimmerText>
                {decision.manual && <span className="badge badge-cyan t-micro">manual query</span>}
              </div>
              <div className="t-label text-[var(--text2)] mb-1">
                <b>{decision.vehicle_id}</b> — <b className={decision.decision === "DIVERT" ? "text-[var(--amber)]" : "text-[var(--green)]"}>{decision.decision}</b>
                {decision.target ? ` → ${decision.target}` : ""}
              </div>
              <div className="t-micro text-[var(--text3)] leading-relaxed">{decision.reason}</div>
              {(decision.candidates || []).filter((c: any) => c.compatible).slice(0, 3).map((c: any) => (
                <div key={c.id} className="flex justify-between t-micro text-[var(--text2)] mt-1 border-t border-[var(--border)] pt-1">
                  <span>{c.name}</span>
                  <span>ETA {c.eta_total_min}m · {c.distance_km}km · score {c.score}</span>
                </div>
              ))}
              <button onClick={() => setDecision(null)} className="btn t-micro mt-2 cursor-pointer">close</button>
            </div>
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

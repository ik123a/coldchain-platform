"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useStore } from "@/lib/store";
import { api, post } from "@/lib/api";
import { 
  Activity, Bot, Maximize2, Play, Radio, Thermometer 
} from "lucide-react";
import { FloatingVehicleInspector } from "@/components/live-map/FloatingVehicleInspector";
import { DeepTelemetryDrawer } from "@/components/live-map/DeepTelemetryDrawer";
import { Marquee } from "@/components/ui/marquee";
import { BorderBeam } from "@/components/ui/border-beam";
import { NumberTicker } from "@/components/ui/number-ticker";
import { ParticleField } from "@/components/ui/particle-field";
import { WeatherOverlay } from "@/components/ui/weather-overlay";
import { DataStream } from "@/components/ui/data-stream";
import { StatusBeacon } from "@/components/ui/status-beacon";
import { AnimatedGauge } from "@/components/ui/animated-gauge";
import { MapMarkers, type MapPoint } from "@/components/ui/map-markers";


export default function DashboardPage() {
  const { st } = useStore();
  const router = useRouter();
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const lastPushRef = useRef(0);
  const vehiclesRef = useRef<any[]>([]);
  const selectedIdRef = useRef<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>("TRUCK-104");
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [geoData, setGeoData] = useState<{ warehouses: any[]; destinations: any[] }>({ warehouses: [], destinations: [] });

  const vehicles = st.fleetVehicles || [];
  const selectedVehicle = vehicles.find(v => v.vehicle_id === selectedId) || vehicles[0];
  const fleetCounts = st.fleetCounts;
  const focusVehicleId = selectedVehicle?.vehicle_id ?? null;
  const coreTemp = selectedVehicle?.refrigeration?.temperature ?? null;
  const outsideTemp = selectedVehicle?.outside_temperature ?? st.fleetMeta?.ambient ?? null;
  const compressorState = selectedVehicle?.refrigeration?.compressor_status ?? "UNKNOWN";
  const cargoHealth = selectedVehicle?.cargo?.cargo_health ?? null;
  const breached = coreTemp !== null && coreTemp > 8;
  const coreGaugePct = coreTemp === null ? 0 : Math.min(100, (coreTemp / 15) * 100);
  const fmtTemp = (v: number | null) => (typeof v === "number" && !Number.isNaN(v) ? `${v.toFixed(1)}°C` : "—");

  const mapPoints = useMemo<MapPoint[]>(() => {
    const wh: MapPoint[] = geoData.warehouses.map((w: any) => ({
      id: `wh-${w.id}`,
      lng: Number(w.lng),
      lat: Number(w.lat),
      tone: "selected",
      label: w.id,
      sublabel: w.name,
    }));
    const fleet: MapPoint[] = vehicles.map((v: any) => {
      const temp = v.refrigeration?.temperature;
      const isSel = v.vehicle_id === focusVehicleId;
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
        sublabel: `${fmtTemp(typeof temp === "number" ? temp : null)} core`,
      };
    });
    return [...wh, ...fleet];
  }, [geoData.warehouses, vehicles, focusVehicleId]);

  // Fetch static warehouses and destinations
  useEffect(() => {
    api("/api/fleet/state").then((s: any) => {
      setGeoData({ warehouses: s.warehouses || [], destinations: s.destinations || [] });
    }).catch(() => {});
  }, []);

  // Initialize MapLibre GL Command Canvas
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      center: [77.18, 28.60],
      zoom: 10.2,
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
          // MapLibre parses paint values in a canvas context, where var() is not
          // resolved by the browser. Keep this a literal hex; it mirrors --canvas.
          { id: "bg", type: "background", paint: { "background-color": "#080a0f" } },
          {
            id: "esri-base",
            type: "raster",
            source: "esriBase",
            paint: { "raster-brightness-max": 0.5, "raster-brightness-min": 0, "raster-saturation": -0.25, "raster-contrast": 0.12 },
          },
          {
            id: "esri-labels",
            type: "raster",
            source: "esriLabels",
            paint: { "raster-brightness-max": 0.8, "raster-opacity": 0.75 },
          },
        ],
      } as any,
      attributionControl: false,
    });
    mapRef.current = map;

    map.on("load", () => {
      setMapReady(true);
    });

    return () => {
      setMapReady(false);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update Warehouses GeoJSON
  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map) return;
    const src = map.getSource("warehouses-src") as maplibregl.GeoJSONSource;
    if (src && geoData.warehouses.length) {
      src.setData({
        type: "FeatureCollection",
        features: geoData.warehouses.map(w => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [w.lng, w.lat] },
          properties: { name: w.name, id: w.id }
        }))
      });
    }
  }, [geoData.warehouses, mapReady]);

  // Smooth camera follow if tracking active
  useEffect(() => {
    const map = mapRef.current;
    if (!mapReady || !map || !trackingId) return;
    const tracked = vehicles.find((v: any) => v.vehicle_id === trackingId);
    if (tracked) {
      map.easeTo({ center: [tracked.lng, tracked.lat], duration: 900, essential: false });
    }
  }, [trackingId, vehicles, mapReady]);

  const handleLaunchSimulation = async () => {
    await post("/api/demo/launch?autopilot=true&failure=compressor_failure&after_ticks=8");
    setSelectedId("TRUCK-104");
    setTrackingId("TRUCK-104");
  };

  const handleApproveDiversion = async (vid: string, facId: string) => {
    await post(`/api/fleet/vehicle/${vid}/action`, { action: "reroute_warehouse_beta" });
  };

  const handleInjectFailure = async (vid: string) => {
    await post(`/api/fleet/vehicle/${vid}/inject`, { failure: "compressor_failure" });
  };

  return (
    <div className="relative w-full h-full flex flex-col overflow-hidden bg-[var(--canvas)] select-none font-sans">
      
      {/* 1. SECTION 9 TOP HEADER AREA */}
      <div className="h-11 shrink-0 px-4 bg-[var(--surface-subtle)] border-b border-[var(--border)] flex flex-wrap items-center justify-between gap-3 t-body-sm font-mono z-20">
        <div className="flex items-center gap-3">
          <div className="t-title m-0 font-bold text-[var(--text)] tracking-wide flex items-center gap-1.5">
            <span className="text-[var(--accent)]">ColdChain Rescue</span>
            <span className="text-[var(--text-muted)]" aria-hidden>·</span>
            <span className="flex items-center gap-1 text-[var(--nominal)] t-label font-normal">
              <span className="w-2 h-2 rounded-full bg-[var(--nominal)] animate-pulse" aria-hidden></span>
              Live Simulation
            </span>
          </div>
        </div>

        {/* Live Metrics */}
        <div className="flex items-center gap-5 text-[var(--text-secondary)]">
          <MetricChip label="Vehicles" value={fleetCounts?.vehicles ?? vehicles.length} />
          <MetricChip label="In Transit" value={fleetCounts?.vehicles ? fleetCounts.in_transit : null} />
          <MetricChip label="At Risk" value={fleetCounts?.vehicles ? fleetCounts.at_risk : null} tone="warning" />
          <MetricChip label="Critical" value={fleetCounts?.vehicles ? fleetCounts.critical : null} tone="critical" pulse />
          <span className="flex items-center gap-1.5 rounded border border-[var(--border)] bg-[var(--surface-inset)] px-2 py-0.5 t-micro font-bold text-[var(--accent)]">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--accent)]" />
            AI ONLINE
          </span>
        </div>
      </div>

      <h1 className="sr-only">Operations dashboard — live fleet overview</h1>

      {/* TACTICAL LIVE TELEMETRY MARQUEE (Awwwards Style) */}
            {/* The strip was bg-[#06080C] — a hardcoded near-black that read as a
                black slab on a light page. --surface-inset now resolves per theme. */}
            <div className="h-7 shrink-0 bg-[var(--surface-inset)] border-b border-[var(--border)] flex items-center overflow-hidden z-20">
        <div className="shrink-0 px-3 h-full bg-[var(--surface-raised)] border-r border-[var(--border)] flex items-center gap-1.5 t-micro font-mono text-[var(--accent)] font-bold uppercase tracking-wider">
          <Activity size={11} className="text-[var(--accent)] animate-pulse" />
          <span>TELEMETRY STREAM</span>
        </div>
        <Marquee pauseOnHover={true} className="flex-1 py-0 font-mono t-label text-[var(--text-secondary)]">
          {focusVehicleId ? (
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--critical)]" />
              <span className="font-bold text-[var(--critical-soft)]">{focusVehicleId}</span>
              <span className="text-[var(--text-muted)]">
                Core {fmtTemp(coreTemp)} · Outside {fmtTemp(outsideTemp)} · Compressor {compressorState}
              </span>
            </span>
          ) : (
            <span className="text-[var(--text-muted)]">Awaiting fleet telemetry…</span>
          )}
          <span className="text-[var(--text-dim)]">│</span>
          <span className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--nominal)]" />
            <span className="font-bold text-[var(--nominal-soft)]">WH-001 CENTRAL</span>
            <span className="text-[var(--text-muted)]">4 Docks Free · Pre-cooling Buffer 3.4°C</span>
          </span>
          <span className="text-[var(--text-dim)]">│</span>
          <span className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />
            <span className="font-bold text-[var(--warning-soft)]">WEATHER OVERRIDE</span>
            <span className="text-[var(--text-muted)]">HEATWAVE ACTIVE (44.0°C Ambient) · Arrhenius Degradation 2.4x</span>
          </span>
          <span className="text-[var(--text-dim)]">│</span>
          <span className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--accent)]" />
            <span className="font-bold text-[var(--accent)]">AI COORDINATOR</span>
            <span className="text-[var(--text-muted)]">Continuous Multi-Agent Re-evaluation Active (100% Deterministic Twin)</span>
          </span>
        </Marquee>
      </div>

      {/* 2. DOMINANT LIVE MAP CANVAS (SECTION 9 & 10) */}
      <div className="relative flex-1 min-h-0 w-full">
        <div ref={mapContainer} className="h-full w-full" />
        <MapMarkers map={mapReady ? mapRef.current : null} points={mapPoints} onSelect={(id) => { if (!id.startsWith("wh-")) setSelectedId(id); }} />

        {/* Ambient Particle Field */}
        <ParticleField count={30} color="var(--accent)" opacity={0.08} speed={0.15} connected className="z-10" />

        {/* Simulated Heatwave Weather Effect */}
        <WeatherOverlay condition="heatwave" intensity={0.3} className="z-10" />

        {/* Tracking Banner if Follow Mode Active */}
        <AnimatePresence>
          {trackingId && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-3.5 py-1.5 rounded-full bg-[var(--surface-raised)] backdrop-blur border border-[var(--accent)] shadow-xl flex items-center gap-3 t-body-sm font-mono">
              <span className="flex items-center gap-1.5 text-[var(--text)] font-bold">
                <Radio size={12} className="text-[var(--accent)] animate-pulse" />
                FOLLOWING {trackingId}
              </span>
              <button
                onClick={() => setTrackingId(null)}
                className="t-micro uppercase font-bold text-[var(--text-dim)] hover:text-[var(--text)] px-2 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border)] transition-colors cursor-pointer">
                Stop Following
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Floating Context HUD (Section 15) */}
        {selectedVehicle && (
          <FloatingVehicleInspector
            vehicle={selectedVehicle}
            onClose={() => setSelectedId(null)}
            onOpenDrawer={() => setDrawerOpen(true)}
            onTrack={() => setTrackingId(trackingId === selectedVehicle.vehicle_id ? null : selectedVehicle.vehicle_id)}
            isTracking={trackingId === selectedVehicle.vehicle_id}
            onInject={() => handleInjectFailure(selectedVehicle.vehicle_id)}
          />
        )}

        {/* Compact Operations Overlay Bar (Bottom Left) */}
        <div className="pointer-events-none absolute bottom-4 left-4 z-20 w-[min(52rem,calc(100%-2rem))] space-y-2">
          <div className="pointer-events-auto relative flex items-center gap-5 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-3 font-mono t-body-sm shadow-2xl backdrop-blur-md">
            <BorderBeam
              size={85}
              duration={3.5}
              colorFrom="var(--critical)"
              colorTo="var(--warning-soft)"
              borderWidth={1.5}
            />
            <div className="relative z-10 flex min-w-0 flex-1 items-center gap-2.5">
              <span className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-[var(--critical)]" />
              <div className="min-w-0">
                <div className="flex items-center gap-2 whitespace-nowrap">
                  <span className="truncate font-bold text-[var(--text)]">{focusVehicleId ?? "No vehicle selected"}</span>
                  {breached && (
                    <span className="shrink-0 rounded border border-[var(--border)] bg-[var(--surface-inset)] px-1.5 t-micro font-bold text-[var(--critical)]">
                      CRITICAL EXCURSION
                    </span>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-2 t-label text-[var(--text-muted)]">
                  <span>Core <span className="text-[var(--text)]">{fmtTemp(coreTemp)}</span></span>
                  <span aria-hidden>·</span>
                  <span>Outside <span className="text-[var(--text)]">{fmtTemp(outsideTemp)}</span></span>
                  <span aria-hidden>·</span>
                  <span>Compressor <span className="text-[var(--warning-soft)]">{compressorState}</span></span>
                </div>
              </div>
            </div>
            <div className="relative z-10 flex shrink-0 items-center gap-2">
              <AnimatedGauge value={coreGaugePct} label="CORE" unit="°C" colorFrom="var(--nominal)" colorTo="var(--accent)" warningThreshold={53} criticalThreshold={67} size={60} />
              <AnimatedGauge value={cargoHealth} label="CARGO" unit="%" colorFrom="var(--accent)" colorTo="var(--nominal)" warningThreshold={70} criticalThreshold={40} size={60} />
            </div>
            <div className="relative z-10 flex shrink-0 items-center gap-2">
              <button
                onClick={() => { setSelectedId(focusVehicleId); setTrackingId(focusVehicleId); }}
                disabled={!focusVehicleId}
                className="cursor-pointer whitespace-nowrap rounded-lg border border-[var(--border)] bg-[var(--surface-card)] px-2.5 py-1.5 t-body-sm font-semibold text-[var(--text)] transition-colors hover:bg-[var(--surface-elevated)] disabled:cursor-not-allowed disabled:opacity-50">
                Focus Map
              </button>
              <button
                onClick={() => setDrawerOpen(true)}
                disabled={!selectedVehicle}
                className="cursor-pointer whitespace-nowrap rounded-lg bg-[var(--accent)] px-3 py-1.5 t-body-sm font-semibold text-[var(--text)] shadow-sm transition-colors hover:bg-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-50">
                AI Detour
              </button>
            </div>
          </div>

          {/* Quick Simulation Launch Trigger */}
          <div className="pointer-events-auto flex items-center gap-2">
            <button
              onClick={handleLaunchSimulation}
              className="py-2 px-3.5 rounded-lg t-body-sm font-semibold bg-[var(--accent)] hover:bg-[var(--accent)] text-[var(--text)] flex items-center gap-2 shadow-lg shadow-[var(--surface-inset)] transition-colors font-mono">
              <Play size={13} fill="currentColor" /> Run Autonomous Rescue Demo
            </button>
            <Link
              href="/live-map"
              className="py-2 px-3 rounded-lg t-body-sm font-medium bg-[var(--surface-card)] hover:bg-[var(--border)] text-[var(--border-strong)] border border-[var(--border)] flex items-center gap-1.5 transition-colors font-mono">
              <Maximize2 size={12} /> Full Screen Map
            </Link>
          </div>
        </div>

        {/* Bottom Right: Live Telemetry Stream + AI Status */}
        <div className="absolute bottom-4 right-4 z-20 hidden lg:flex flex-col gap-2 w-72">
          {/* AI Status Bar */}
          <div className="flex items-center gap-2 p-2 rounded-xl glass-panel font-mono t-label">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--surface-card)]">
              <Bot size={13} className="text-[var(--accent)]" />
              <span className="text-[var(--text-dim)]">AI STATUS:</span>
              <span className="text-[var(--nominal)] font-bold">ACTIVE MONITORING</span>
            </div>
            <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--surface-card)]">
              <Thermometer size={13} className="text-[var(--warning)]" />
              <span className="text-[var(--text-dim)]">HEAT SHIELD:</span>
              <span className="text-[var(--text)] font-bold">ARRHENIUS GATED</span>
            </div>
          </div>
          {/* Live Telemetry Data Stream */}
          <div className="glass-panel rounded-xl p-3 max-h-40 overflow-hidden">
            <div className="flex items-center gap-1.5 mb-2 t-micro font-mono text-[var(--accent)] font-bold uppercase tracking-wider">
              <Activity size={10} className="animate-pulse" />
              <span>LIVE TELEMETRY FEED</span>
            </div>
            <DataStream speed={1800} maxLines={8} />
          </div>
        </div>

      </div>

      {/* 3. EXPANDABLE DEEP TELEMETRY DRAWER (SECTIONS 16-26) */}
      <AnimatePresence>
        {drawerOpen && selectedVehicle && (
          <DeepTelemetryDrawer
            vehicle={selectedVehicle}
            onClose={() => setDrawerOpen(false)}
            onApproveDiversion={handleApproveDiversion}
            onInjectFailure={handleInjectFailure}
          />
        )}
      </AnimatePresence>

    </div>
  );
}

function MetricChip({
  label,
  value,
  tone = "default",
  pulse = false,
}: {
  label: string;
  value: number | null;
  tone?: "default" | "warning" | "critical";
  pulse?: boolean;
}) {
  const valueColor =
    tone === "critical" ? "text-[var(--critical-soft)]" : tone === "warning" ? "text-[var(--warning-soft)]" : "text-[var(--text)]";
  return (
    <span className="flex items-baseline gap-1.5">
      {pulse && <span className="h-1.5 w-1.5 self-center rounded-full bg-[var(--critical)] animate-ping" />}
      {value === null ? (
        <span className="text-[var(--text-dim)]">—</span>
      ) : (
        <NumberTicker value={value} className={`font-bold ${valueColor}`} />
      )}
      <span>{label}</span>
    </span>
  );
}

"use client";
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useStore } from "@/lib/store";
import { api, post } from "@/lib/api";
import { 
  Activity, AlertTriangle, ArrowRight, Bot, Compass, ExternalLink, 
  Maximize2, Navigation, Play, Radio, ShieldAlert, ShieldCheck, 
  Siren, Thermometer, Truck, Warehouse, Zap 
} from "lucide-react";
import { FloatingVehicleInspector } from "@/components/live-map/FloatingVehicleInspector";
import { DeepTelemetryDrawer } from "@/components/live-map/DeepTelemetryDrawer";

export default function DashboardPage() {
  const { st } = useStore();
  const router = useRouter();
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>("TRUCK-104");
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [geoData, setGeoData] = useState<{ warehouses: any[]; destinations: any[] }>({ warehouses: [], destinations: [] });

  const vehicles = st.fleetVehicles || [];
  const selectedVehicle = vehicles.find(v => v.vehicle_id === selectedId) || vehicles[0];

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
          carto: {
            type: "raster",
            tiles: [
              "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
              "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"
            ],
            tileSize: 256,
            attribution: "© CARTO, © OpenStreetMap"
          },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#080A0F" } },
          { id: "carto-tiles", type: "raster", source: "carto", paint: { "raster-opacity": 0.95 } },
        ],
      } as any,
      attributionControl: false,
    });
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("fleet-vehicles", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addSource("warehouses-src", { type: "geojson", data: { type: "FeatureCollection", features: [] } });

      // Warehouses
      map.addLayer({
        id: "wh-dots", type: "circle", source: "warehouses-src",
        paint: { "circle-radius": 8, "circle-color": "#0284c7", "circle-stroke-color": "#38bdf8", "circle-stroke-width": 1.5 }
      });
      map.addLayer({
        id: "wh-labels", type: "symbol", source: "warehouses-src",
        layout: { "text-field": ["get", "name"], "text-size": 10, "text-offset": [0, 1.3] },
        paint: { "text-color": "#7dd3fc", "text-halo-color": "#080A0F", "text-halo-width": 1.2 }
      });

      // Vehicles
      map.addLayer({
        id: "veh-glow", type: "circle", source: "fleet-vehicles",
        paint: { "circle-radius": 14, "circle-color": ["get", "color"], "circle-opacity": 0.25 }
      });
      map.addLayer({
        id: "veh-dots", type: "circle", source: "fleet-vehicles",
        paint: { "circle-radius": 6, "circle-color": ["get", "color"], "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5 }
      });
      map.addLayer({
        id: "veh-labels", type: "symbol", source: "fleet-vehicles",
        layout: { "text-field": ["get", "id"], "text-size": 9.5, "text-offset": [0, -1.4] },
        paint: { "text-color": "#e2e8f0", "text-halo-color": "#080A0F", "text-halo-width": 1.5 }
      });

      // Click vehicle
      map.on("click", "veh-dots", (e) => {
        const feat = e.features?.[0];
        if (feat?.properties?.id) {
          setSelectedId(feat.properties.id);
        }
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update Warehouses GeoJSON
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
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
  }, [geoData.warehouses]);

  // Update Fleet GeoJSON on backend ticks
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const src = map.getSource("fleet-vehicles") as maplibregl.GeoJSONSource;
    if (src && vehicles.length) {
      src.setData({
        type: "FeatureCollection",
        features: vehicles.map((v: any) => {
          const isBreached = (v.refrigeration?.temperature ?? 4.8) > 8.0;
          const isSelected = v.vehicle_id === selectedId;
          return {
            type: "Feature",
            geometry: { type: "Point", coordinates: [v.lng, v.lat] },
            properties: {
              id: v.vehicle_id,
              heading: v.heading || 0,
              color: isBreached ? "#f43f5e" : isSelected ? "#38bdf8" : "#10b981",
              speed: v.speed_kmh || 0
            }
          };
        })
      });

      // Smooth camera follow if tracking active
      if (trackingId) {
        const tracked = vehicles.find(v => v.vehicle_id === trackingId);
        if (tracked) {
          map.easeTo({ center: [tracked.lng, tracked.lat], duration: 900, essential: false });
        }
      }
    }
  }, [vehicles, selectedId, trackingId]);

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
    <div className="relative w-full h-full flex flex-col overflow-hidden bg-[#080A0F] select-none font-sans">
      
      {/* 1. SECTION 9 TOP HEADER AREA */}
      <div className="h-11 shrink-0 px-4 bg-[#0A0D14] border-b border-[#1E2638] flex flex-wrap items-center justify-between gap-3 text-xs font-mono z-20">
        <div className="flex items-center gap-3">
          <div className="font-bold text-white tracking-wide flex items-center gap-1.5">
            <span className="text-cyan-400">COLDCHAIN RESCUE</span>
            <span className="text-slate-600">·</span>
            <span className="flex items-center gap-1 text-emerald-400 text-[11px]">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              LIVE SIMULATION
            </span>
          </div>
        </div>

        {/* 42 Vehicles · 87 Shipments · 5 At Risk · 1 Critical · AI ONLINE */}
        <div className="flex items-center gap-4 text-slate-300">
          <span className="hidden sm:inline"><b className="text-white font-bold">42</b> Vehicles</span>
          <span className="hidden sm:inline"><b className="text-white font-bold">87</b> Shipments</span>
          <span className="text-amber-400"><b className="text-amber-300 font-bold">5</b> At Risk</span>
          <span className="text-rose-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
            <b className="text-rose-300 font-bold">1</b> Critical
          </span>
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800/60">
            AI ONLINE
          </span>
        </div>
      </div>

      {/* 2. DOMINANT LIVE MAP CANVAS (SECTION 9 & 10) */}
      <div className="relative flex-1 min-h-0 w-full">
        <div ref={mapContainer} className="w-full h-full" />

        {/* Tracking Banner if Follow Mode Active */}
        <AnimatePresence>
          {trackingId && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="absolute top-3 left-1/2 -translate-x-1/2 z-30 px-3.5 py-1.5 rounded-full bg-[#0E121A]/95 backdrop-blur border border-cyan-500/40 shadow-xl flex items-center gap-3 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-cyan-300 font-bold">
                <Radio size={12} className="text-cyan-400 animate-pulse" />
                FOLLOWING {trackingId}
              </span>
              <button
                onClick={() => setTrackingId(null)}
                className="text-[10px] uppercase font-bold text-slate-400 hover:text-white px-2 py-0.5 rounded bg-[#141B26] border border-[#1E2638] transition-colors">
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
        <div className="absolute bottom-4 left-4 z-20 max-w-lg space-y-2 pointer-events-none">
          {/* Distressed Reefer Ticker */}
          <div className="pointer-events-auto bg-[#0E121A]/95 backdrop-blur-md border border-[#1E2638] rounded-xl p-3 shadow-2xl flex items-center justify-between gap-4 font-mono text-xs">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse shrink-0"></span>
              <div>
                <div className="text-white font-bold flex items-center gap-2">
                  <span>TRUCK-104</span>
                  <span className="text-[10px] px-1.5 rounded bg-rose-950 text-rose-400 border border-rose-800 font-bold">CRITICAL EXCURSION</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Core: 10.4°C · Outside: 41.8°C · Compressor: DEGRADED
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => { setSelectedId("TRUCK-104"); setTrackingId("TRUCK-104"); }}
                className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-[#141B26] hover:bg-[#1E2638] text-cyan-300 border border-[#1E2638] transition-colors whitespace-nowrap">
                Focus Map
              </button>
              <button
                onClick={() => setDrawerOpen(true)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-colors whitespace-nowrap shadow-sm">
                AI Detour
              </button>
            </div>
          </div>

          {/* Quick Simulation Launch Trigger */}
          <div className="pointer-events-auto flex items-center gap-2">
            <button
              onClick={handleLaunchSimulation}
              className="py-2 px-3.5 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-2 shadow-lg shadow-cyan-950/40 transition-colors font-mono">
              <Play size={13} fill="currentColor" /> Run Autonomous Rescue Demo
            </button>
            <Link
              href="/live-map"
              className="py-2 px-3 rounded-lg text-xs font-medium bg-[#141B26]/90 hover:bg-[#1E2638] text-slate-300 border border-[#1E2638] flex items-center gap-1.5 transition-colors font-mono">
              <Maximize2 size={12} /> Full Screen Map
            </Link>
          </div>
        </div>

        {/* Bottom Right AI Multi-Agent Status Strip */}
        <div className="absolute bottom-4 right-4 z-20 hidden lg:flex items-center gap-2 p-2 rounded-xl bg-[#0E121A]/95 backdrop-blur border border-[#1E2638] font-mono text-[11px]">
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#141B26]">
            <Bot size={13} className="text-cyan-400" />
            <span className="text-slate-400">AI STATUS:</span>
            <span className="text-emerald-400 font-bold">ACTIVE MONITORING</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#141B26]">
            <Thermometer size={13} className="text-amber-400" />
            <span className="text-slate-400">HEAT SHIELD:</span>
            <span className="text-white font-bold">ARRHENIUS GATED</span>
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

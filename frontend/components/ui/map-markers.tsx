"use client";
import { useEffect, useRef, useState } from "react";
import type { Map as MLMap } from "maplibre-gl";

export type MapPoint = {
  id: string;
  lng: number;
  lat: number;
  tone: "nominal" | "warning" | "critical" | "selected";
  label?: string;
  sublabel?: string;
  heading?: number;
  kind?: "vehicle" | "warehouse" | "service";
};

const TONE: Record<MapPoint["tone"], { dot: string; ring: string }> = {
  nominal: { dot: "var(--nominal)", ring: "rgba(16,185,129,0.28)" },
  warning: { dot: "var(--warning)", ring: "rgba(245,158,11,0.28)" },
  critical: { dot: "var(--critical)", ring: "rgba(244,63,94,0.32)" },
  selected: { dot: "var(--accent)", ring: "rgba(56,189,248,0.32)" },
};

/** Top-down reefer truck pointing north, so CSS rotation equals compass heading. */
function TruckGlyph({ fill, dim }: { fill: string; dim: boolean }) {
  return (
    <svg width="100%" height="100%" viewBox="0 0 24 24" style={{ display: "block" }}>
      <rect x="4.6" y="10.4" width="2.2" height="4.4" rx="1" fill="#05070c" />
      <rect x="17.2" y="10.4" width="2.2" height="4.4" rx="1" fill="#05070c" />
      <rect x="6.4" y="9.2" width="11.2" height="12.4" rx="1.6" fill={fill} stroke="#05070c" strokeWidth="1.1" />
      <path d="M7.6 2.6 h8.8 a1.4 1.4 0 0 1 1.4 1.4 v5.2 h-11.6 v-5.2 a1.4 1.4 0 0 1 1.4 -1.4 z" fill={fill} stroke="#05070c" strokeWidth="1.1" />
      <rect x="9.2" y="4.4" width="5.6" height="2" rx="0.7" fill="#05070c" opacity={dim ? 0.35 : 0.62} />
      {dim && <rect x="8.6" y="12.4" width="6.8" height="5.4" rx="0.8" fill="#05070c" opacity="0.25" />}
    </svg>
  );
}

/**
 * Renders point markers as a DOM overlay synced to the map camera.
 * MapLibre's GeoJSON circle/symbol layers depend on its web worker, which does
 * not load in this app's Next build, and symbol layers additionally need a style
 * `glyphs` endpoint that this basemap-only style does not provide. A projected
 * DOM overlay sidesteps both and keeps markers legible against the dark tiles.
 */
export function MapMarkers({
  map,
  points,
  onSelect,
}: {
  map: MLMap | null;
  points: MapPoint[];
  onSelect?: (id: string) => void;
}) {
  const [projected, setProjected] = useState<Array<MapPoint & { x: number; y: number }>>([]);
  const [zscale, setZscale] = useState(1);
  const rafRef = useRef(0);

  useEffect(() => {
    if (!map) return;
    let frame = 0;
    const compute = () => {
      frame = 0;
      const canvas = map.getCanvas();
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const next: Array<MapPoint & { x: number; y: number }> = [];
      for (const p of points) {
        if (!Number.isFinite(p.lng) || !Number.isFinite(p.lat)) continue;
        const pt = map.project([p.lng, p.lat]);
        if (pt.x < -80 || pt.y < -80 || pt.x > w + 80 || pt.y > h + 80) continue;
        next.push({ ...p, x: pt.x, y: pt.y });
      }
      setProjected(next);
      const z = map.getZoom();
      setZscale(prev => {
        const next2 = Math.max(0.85, Math.min(2, 0.8 + (z - 9) * 0.22));
        return Math.abs(next2 - prev) < 0.04 ? prev : next2;
      });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(compute);
    };

    schedule();
    map.on("move", schedule);
    map.on("resize", schedule);
    map.on("zoom", schedule);
    const ro = new ResizeObserver(schedule);
    ro.observe(map.getCanvas());
    return () => {
      map.off("move", schedule);
      map.off("resize", schedule);
      map.off("zoom", schedule);
      ro.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [map, points]);

  return (
    <div className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      {projected.map((p) => {
        const tone = TONE[p.tone];
        const halo = p.tone === "selected" ? 22 : 18;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onSelect?.(p.id)}
            title={p.sublabel ? `${p.label ?? p.id} — ${p.sublabel}` : p.label ?? p.id}
            className="pointer-events-auto absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center
                       before:absolute before:left-1/2 before:top-1/2 before:h-6 before:w-6
                       before:-translate-x-1/2 before:-translate-y-1/2 before:content-['']"
            style={{ left: p.x, top: p.y }}
          >
            <span
              className="block rounded-full"
              style={{ width: halo, height: halo, background: tone.ring }}
            />
            {p.kind === "vehicle" ? (
              <>
                {(p.tone === "critical" || p.tone === "warning") && (
                  <span
                    className="absolute top-1/2 left-1/2 block -translate-x-1/2 -translate-y-1/2 rounded-full"
                    style={{
                      width: p.tone === "critical" ? 30 : 26,
                      height: p.tone === "critical" ? 30 : 26,
                      border: `1.5px solid ${tone.dot}`,
                      animation: "pulse-ring 1.8s ease-out infinite",
                    }}
                  />
                )}
                <span
                  className="absolute top-1/2 left-1/2 block"
                  style={{
                    width: 19 * zscale,
                    height: 19 * zscale,
                    transform: `translate(-50%,-50%) rotate(${Number.isFinite(p.heading) ? p.heading! : 0}deg)`,
                    filter: p.tone === "selected" ? "drop-shadow(0 0 5px var(--accent))" : undefined,
                  }}
                >
                  <TruckGlyph fill={tone.dot} dim={p.tone === "critical" || p.tone === "warning"} />
                </span>
              </>
            ) : (
              <span
                className="absolute top-1/2 left-1/2 block -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white"
                style={{
                  width: p.tone === "selected" ? 11 : 9,
                  height: p.tone === "selected" ? 11 : 9,
                  background: tone.dot,
                }}
              />
            )}
            {p.label && (
              <span
                className="absolute left-1/2 mt-4 -translate-x-1/2 whitespace-nowrap rounded bg-[var(--canvas)]/85 px-1.5 py-0.5 font-mono t-micro font-bold tracking-tight"
                style={{ color: tone.dot, textShadow: "0 1px 2px #000" }}
              >
                {p.label}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

"use client";
import { useEffect, useRef } from "react";
import type { Map as MLMap } from "maplibre-gl";

export type LL = [number, number];
export type RouteGeom = { done: LL[]; todo: LL[]; tone: "normal" | "warning" | "critical" | "reroute" | "stale" };
export type IncidentPin = { id: string; lng: number; lat: number; severity: string; vehicle_id?: string; cause?: string };

const ROUTE_TONE: Record<RouteGeom["tone"], { done: string; todo: string; width: number }> = {
  normal: { done: "var(--nominal-soft)", todo: "var(--accent)", width: 2.2 },
  warning: { done: "var(--warning-soft)", todo: "var(--warning-soft)", width: 2.6 },
  critical: { done: "var(--critical-soft)", todo: "var(--critical-soft)", width: 2.8 },
  reroute: { done: "#a78bfa", todo: "#a78bfa", width: 3 },
  stale: { done: "var(--text-muted)", todo: "var(--text-muted)", width: 1.6 },
};

const SEV_COLOR: Record<string, string> = {
  CRITICAL: "var(--critical-soft)", HIGH: "#fb923c", MEDIUM: "var(--warning-soft)", LOW: "var(--accent)", INFO: "#7dd3fc",
};

function project(map: MLMap, path: LL[]): string {
  const out: string[] = [];
  for (const p of path) {
    if (!Number.isFinite(p[0]) || !Number.isFinite(p[1])) continue;
    const s = map.project(p);
    out.push(`${s.x.toFixed(1)},${s.y.toFixed(1)}`);
  }
  return out.join(" ");
}

/**
 * Screen-space SVG overlay for route geometry, travelled trails and incident pins.
 *
 * MapLibre's GeoJSON worker does not load in this Next build, so every GeoJSON
 * source on this map stays permanently empty. Markers already work around that
 * with a DOM overlay (see map-markers.tsx); this applies the same projection
 * technique to line work, which cannot be recovered without a worker.
 *
 * Children are created once per identity change and mutated per frame, so a
 * telemetry tick mutates attributes instead of rebuilding the tree.
 */
export function MapOverlay({
  map,
  routes,
  trails,
  incidents,
  selected,
  onIncidentClick,
}: {
  map: MLMap | null;
  routes: Map<string, RouteGeom>;
  trails: Map<string, LL[]>;
  incidents: IncidentPin[];
  selected?: string | null;
  onIncidentClick?: (pin: IncidentPin) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const doneRef = useRef<Map<string, SVGPolylineElement>>(new Map());
  const todoRef = useRef<Map<string, SVGPolylineElement>>(new Map());
  const trailRef = useRef<Map<string, SVGPolylineElement>>(new Map());
  const incRef = useRef<Map<string, SVGGElement>>(new Map());

  const live = useRef({ routes, trails, incidents, selected, onIncidentClick });
  live.current = { routes, trails, incidents, selected, onIncidentClick };

  useEffect(() => {
    if (!map || !svgRef.current) return;
    const svg = svgRef.current;
    const nd = "http://www.w3.org/2000/svg";
    let raf = 0;

    const mk = <K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string>) => {
      const el = document.createElementNS(nd, tag);
      for (const k in attrs) el.setAttribute(k, attrs[k]);
      return el;
    };

    const sync = <T extends SVGElement>(reg: Map<string, T>, parent: SVGElement, ids: string[], make: (id: string) => T) => {
      for (const [id, el] of reg) if (!ids.includes(id)) { el.remove(); reg.delete(id); }
      for (const id of ids) if (!reg.has(id)) { const el = make(id); reg.set(id, el); parent.appendChild(el); }
    };

    const loop = () => {
      raf = requestAnimationFrame(loop);
      const { routes: R, trails: T, incidents: I, selected: sel } = live.current;
      const w = map.getCanvas().clientWidth;
      const h = map.getCanvas().clientHeight;

      const routeIds = [...R.keys()];
      sync(doneRef.current, svg, routeIds, () =>
        mk("polyline", { fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" }));
      sync(todoRef.current, svg, routeIds, () =>
        mk("polyline", { fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round", "stroke-dasharray": "7 5" }));
      sync(trailRef.current, svg, [...T.keys()], () =>
        mk("polyline", { fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" }));

      for (const [id, g] of R) {
        const tone = ROUTE_TONE[g.tone] ?? ROUTE_TONE.normal;
        const isSel = id === sel;
        const d = doneRef.current.get(id);
        const t = todoRef.current.get(id);
        if (d) {
          d.setAttribute("points", project(map, g.done));
          d.setAttribute("stroke", tone.done);
          d.setAttribute("stroke-width", String(isSel ? tone.width + 1.4 : tone.width));
          d.setAttribute("opacity", g.tone === "stale" ? "0.3" : isSel ? "0.95" : "0.6");
        }
        if (t) {
          t.setAttribute("points", project(map, g.todo));
          t.setAttribute("stroke", tone.todo);
          t.setAttribute("stroke-width", String(isSel ? tone.width + 1 : tone.width * 0.85));
          t.setAttribute("opacity", g.tone === "stale" ? "0.22" : isSel ? "0.95" : "0.5");
        }
      }

      for (const [id, pts] of T) {
        const el = trailRef.current.get(id);
        if (!el) continue;
        el.setAttribute("points", project(map, pts));
        el.setAttribute("stroke", id === sel ? "#e2e8f0" : "#7dd3fc");
        el.setAttribute("stroke-width", id === sel ? "2.6" : "1.5");
        el.setAttribute("opacity", id === sel ? "0.85" : "0.34");
      }

      const incIds = I.map((p) => p.id);
      sync(incRef.current, svg, incIds, (id) => {
        const g = mk("g", { style: "cursor:pointer" });
        g.appendChild(mk("circle", { r: "16", fill: "none", "stroke-width": "1.3" }));
        g.appendChild(mk("circle", { r: "6.5", "stroke-width": "1.8", fill: "#0b1018" }));
        const tx = mk("text", {
          "text-anchor": "middle", "dominant-baseline": "central",
          "font-size": "8.5", "font-family": "ui-monospace,monospace", "font-weight": "700",
        });
        g.appendChild(tx);
        g.addEventListener("click", () => {
          const pin = live.current.incidents.find((p) => p.id === id);
          if (pin) live.current.onIncidentClick?.(pin);
        });
        return g;
      });

      for (const pin of I) {
        const g = incRef.current.get(pin.id);
        if (!g) continue;
        const s = map.project([pin.lng, pin.lat]);
        g.setAttribute("transform", `translate(${s.x.toFixed(1)},${s.y.toFixed(1)})`);
        const col = SEV_COLOR[pin.severity] ?? SEV_COLOR.MEDIUM;
        const kids = Array.from(g.children) as SVGElement[];
        kids[0].setAttribute("stroke", col);
        kids[0].setAttribute("opacity", "0.5");
        kids[1].setAttribute("stroke", col);
        kids[2].setAttribute("fill", col);
        kids[2].textContent = pin.vehicle_id ? pin.vehicle_id.replace("TRUCK-", "T") : pin.severity;
        if (s.x < -60 || s.y < -60 || s.x > w + 60 || s.y > h + 60) g.setAttribute("display", "none");
        else g.removeAttribute("display");
      }
    };

    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      doneRef.current.clear();
      todoRef.current.clear();
      trailRef.current.clear();
      incRef.current.clear();
    };
  }, [map]);

  if (!map) return null;
  return (
    <svg
      ref={svgRef}
      className="pointer-events-none absolute inset-0 z-[5] h-full w-full overflow-visible"
      aria-hidden
    />
  );
}

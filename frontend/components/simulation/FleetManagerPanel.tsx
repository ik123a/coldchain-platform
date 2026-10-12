"use client";
import { useCallback, useEffect, useState } from "react";
import { Minus, Plus, Truck } from "lucide-react";
import { api } from "@/lib/api";
import DispatchBuilder from "@/components/simulation/DispatchBuilder";

/**
 * Floating, collapsible host for the truck-management panel.
 *
 * The dashboard and the live map are full-bleed map layouts — there is no
 * sidebar to drop <DispatchBuilder /> into, so this wrapper floats it over
 * the canvas. Collapsed it is a compact toggle with the live fleet count;
 * expanded it is the same DispatchBuilder used on /simulation (identical
 * add / configure / start / remove behaviour, one source of truth), with a
 * collapse chip pinned to its corner.
 *
 * The count comes from GET /api/fleet/dispatch (operator trucks, not the
 * demo fleet) and is re-fetched whenever the panel closes, so the badge
 * stays honest even when trucks were managed on another page.
 */
export default function FleetManagerPanel({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [max, setMax] = useState<number | null>(null);

  const refresh = useCallback(() => {
    api<{ count: number; max: number }>("/api/fleet/dispatch")
      .then((d) => { setCount(d.count); setMax(d.max); })
      .catch(() => {});
  }, []);

  useEffect(refresh, [refresh]);
  // Re-sync the badge when collapsing — trucks may have been added or
  // removed from /simulation or the other map page while the panel was shut.
  useEffect(() => {
    if (!open) refresh();
  }, [open, refresh]);

  if (!open) {
    return (
      <div className={`z-40 ${className}`}>
        <button
          onClick={() => setOpen(true)}
          title="Add, configure, start or remove trucks"
          className="flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-raised)] backdrop-blur-md px-3 py-2 t-body-sm font-semibold text-[var(--text)] shadow-xl hover:bg-[var(--surface-elevated)] transition-colors cursor-pointer"
        >
          <Truck size={13} className="text-[var(--accent)]" aria-hidden />
          <Plus size={11} aria-hidden /> Truck fleet
          {count != null && (
            <span className="t-micro font-mono text-[var(--text3)]">
              {count}/{max ?? "—"}
            </span>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className={`z-40 ${className}`}>
      <div className="relative w-[min(23rem,calc(100vw-2rem))] max-h-[min(72vh,40rem)] flex flex-col">
        <button
          onClick={() => setOpen(false)}
          title="Collapse the truck panel"
          aria-label="Collapse truck panel"
          className="absolute -top-2 -right-2 z-20 flex items-center justify-center h-6 w-6 rounded-full border border-[var(--border)] bg-[var(--surface-raised)] text-[var(--text3)] hover:text-[var(--text)] shadow-lg cursor-pointer"
        >
          <Minus size={12} aria-hidden />
        </button>
        <div className="min-h-0 overflow-y-auto scroll-thin rounded-xl shadow-2xl">
          <DispatchBuilder />
        </div>
      </div>
    </div>
  );
}

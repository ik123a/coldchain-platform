"use client";
import { useCallback, useEffect, useState } from "react";
import { Play, Plus, Trash2, Truck } from "lucide-react";
import { api, post, patch, del } from "@/lib/api";

/**
 * Dynamic truck management: the operator controls which trucks exist.
 *
 * + Add Truck creates one immediately (server-assigned unique id, draft
 * state, nothing started); each truck is configured (product, destination,
 * load), started, and removed individually. The fleet size is whatever the
 * operator creates — up to the backend's declared max, which is surfaced
 * from GET /api/fleet/dispatch rather than hardcoded here.
 *
 * The backend is the source of truth: every mutation returns the updated
 * truck(s) and the list is rebuilt from those responses, so the UI never
 * drifts from the simulation and no page refresh is ever needed. Server
 * 400 details (unknown product, duplicate destination, incompatible pair,
 * fleet full) are surfaced verbatim — the reason IS the useful message.
 */

type Truck = {
  id: string;
  name: string;
  cargo_type: string;
  destination_id: string;
  load_units: number;
  vehicle_id?: string | null;
  status: string;
  running?: boolean;
};
type Dest = {
  id: string;
  name: string;
  kind: string;
  cargo_types: string[];
  available_capacity: number;
};
type Catalog = { products: string[]; destinations: Dest[] };

const PRODUCT_LABEL: Record<string, string> = {
  fresh_produce: "Fresh produce",
  dairy: "Fresh dairy",
  frozen_goods: "Frozen goods",
  pharma: "Pharmaceutical",
};

const STATUS_LABEL: Record<string, string> = {
  NOT_STARTED: "Not Started",
  IN_TRANSIT: "Running",
  ARRIVED: "Arrived",
};

export default function DispatchBuilder({ onStarted }: { onStarted?: () => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [max, setMax] = useState<number | null>(null);
  const [trucks, setTrucks] = useState<Truck[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [anyRunning, setAnyRunning] = useState(false);

  const load = useCallback(() => {
    api<{ trucks: Truck[]; max: number; catalog: Catalog }>("/api/fleet/dispatch")
      .then((d) => {
        setCatalog(d.catalog);
        setMax(d.max);
        setTrucks(d.trucks);
        setAnyRunning(d.trucks.some((t) => t.running));
      })
      .catch(() => setError("Could not load the truck fleet — is the backend running?"));
  }, []);

  useEffect(load, [load]);

  const setTruckError = (id: string, msg: string | null) =>
    setErrors((prev) => {
      const next = { ...prev };
      if (msg) next[id] = msg;
      else delete next[id];
      return next;
    });

  /** + Add Truck: a draft truck appears immediately, nothing else changes. */
  const addTruck = async () => {
    setAdding(true);
    setError(null);
    try {
      const r = await post<{ truck: Truck }>("/api/fleet/dispatch/trucks", {});
      setTrucks((prev) => [...prev, r.truck]);
    } catch (e: any) {
      setError(String(e?.message ?? e).replace(/^\d+\s+[A-Za-z ]+—\s*/, ""));
    } finally {
      setAdding(false);
    }
  };

  /** Configure one truck. Edits save immediately — no separate Save step to forget. */
  const configure = async (t: Truck, p: Partial<Truck>) => {
    setTrucks((prev) => prev.map((x) => (x.id === t.id ? { ...x, ...p } : x)));
    setTruckError(t.id, null);
    setError(null);
    try {
      const r = await patch<{ truck: Truck }>(`/api/fleet/dispatch/trucks/${t.id}`, p);
      setTrucks((prev) => prev.map((x) => (x.id === t.id ? r.truck : x)));
    } catch (e: any) {
      setTruckError(t.id, String(e?.message ?? e).replace(/^\d+\s+[A-Za-z ]+—\s*/, ""));
      load(); // revert to the server's version of the failed edit
    }
  };

  /** Start THIS truck only: product + destination must be chosen first. */
  const startTruck = async (t: Truck) => {
    setBusyId(t.id);
    setTruckError(t.id, null);
    setError(null);
    try {
      const r = await post<{ trucks: Truck[] }>(`/api/fleet/dispatch/trucks/${t.id}/start`);
      setTrucks(r.trucks);
      setAnyRunning(r.trucks.some((x) => x.running));
      onStarted?.();
    } catch (e: any) {
      setTruckError(t.id, String(e?.message ?? e).replace(/^\d+\s+[A-Za-z ]+—\s*/, ""));
    } finally {
      setBusyId(null);
    }
  };

  /** Remove THIS truck only. Running trucks ask first; others go immediately. */
  const removeTruck = async (t: Truck) => {
    if (t.running &&
        !window.confirm(`${t.name} is currently in delivery. Remove this truck?`)) {
      return;
    }
    setBusyId(t.id);
    setTruckError(t.id, null);
    setError(null);
    try {
      const r = await del<{ trucks: Truck[] }>(`/api/fleet/dispatch/trucks/${t.id}`);
      setTrucks(r.trucks);
      setAnyRunning(r.trucks.some((x) => x.running));
    } catch (e: any) {
      setTruckError(t.id, String(e?.message ?? e).replace(/^\d+\s+[A-Za-z ]+—\s*/, ""));
    } finally {
      setBusyId(null);
    }
  };

  /** Start every configured, not-yet-running truck (demo convenience). */
  const startAll = async () => {
    for (const t of trucks.filter((x) => x.cargo_type && x.destination_id && !x.running)) {
      await startTruck(t);
    }
  };

  /** Destinations that actually accept the chosen product. */
  const optionsFor = (cargo: string) =>
    (catalog?.destinations ?? []).filter((d) => !cargo || d.cargo_types.includes(cargo));

  const fleetFull = max != null && trucks.length >= max;

  return (
    <section className="base-card p-4 space-y-3" aria-labelledby="dispatch-h">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h2 id="dispatch-h" className="t-body font-semibold flex items-center gap-2">
            <Truck size={14} className="text-[var(--accent)]" aria-hidden />
            Truck management
            {max != null && (
              <span className="t-micro font-mono text-[var(--text3)]">
                {trucks.length}/{max}
              </span>
            )}
          </h2>
          <p className="t-body-sm text-[var(--text3)] mt-0.5">
            You add, configure, start and remove each truck. Nothing is assigned automatically.
          </p>
        </div>
      </div>

      <button
        onClick={addTruck}
        disabled={adding || fleetFull}
        title={fleetFull ? `Fleet limit: ${max} trucks` : "Add a new truck"}
        className="btn btn-primary w-full flex items-center justify-center gap-2"
      >
        <Plus size={13} aria-hidden /> Add Truck
      </button>
      {fleetFull && (
        <p className="t-micro text-[var(--amber)]">
          Fleet limit reached ({max} trucks). Remove one to add another.
        </p>
      )}

      <div className="space-y-2">
        {trucks.map((t) => {
          const opts = optionsFor(t.cargo_type);
          const configured = Boolean(t.cargo_type && t.destination_id);
          const statusLabel = STATUS_LABEL[t.status] ?? t.status;
          return (
            <div
              key={t.id}
              className="rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-raised)] p-2.5 space-y-2"
            >
              <div className="flex items-center gap-2">
                <span className="ops-label" title={`Truck ID ${t.id}`}>{t.id}</span>
                <input
                  className="flex-1"
                  defaultValue={t.name}
                  onBlur={(e) => {
                    const v = e.target.value.trim();
                    if (v && v !== t.name) configure(t, { name: v });
                  }}
                  placeholder="Truck name"
                  aria-label={`${t.name} name`}
                />
                <span
                  className={`badge ${t.running
                    ? (t.status === "ARRIVED" ? "badge-green" : "badge-amber")
                    : ""}`}
                  title="Delivery status"
                >
                  {statusLabel}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-start">
                <label className="t-label text-[var(--text3)]">
                  Product
                  <select
                    className="mt-1 w-full"
                    value={t.cargo_type}
                    onChange={(e) => configure(t, { cargo_type: e.target.value, destination_id: "" })}
                    disabled={t.running}
                  >
                    <option value="">— choose product —</option>
                    {(catalog?.products ?? []).map((p) => (
                      <option key={p} value={p}>{PRODUCT_LABEL[p] ?? p}</option>
                    ))}
                  </select>
                </label>

                <label className="t-label text-[var(--text3)]">
                  {/* whitespace-nowrap: the longest label wrapped to two lines
                      and pushed this dropdown below the other two fields. */}
                  <span className="whitespace-nowrap">Destination</span>
                  <select
                    className="mt-1 w-full"
                    value={t.destination_id}
                    onChange={(e) => configure(t, { destination_id: e.target.value })}
                    disabled={t.running}
                  >
                    <option value="">— choose —</option>
                    {opts.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.id} · {d.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="t-label text-[var(--text3)]">
                  Load
                  <input
                    className="mt-1 w-full"
                    type="number"
                    min={1}
                    max={1000}
                    defaultValue={t.load_units}
                    onBlur={(e) => {
                      const v = Number(e.target.value);
                      if (v && v !== t.load_units) configure(t, { load_units: v });
                    }}
                    disabled={t.running}
                  />
                </label>
              </div>

              {t.cargo_type && opts.length === 0 && (
                <p className="t-body-sm text-[var(--critical)]">
                  No facility accepts {PRODUCT_LABEL[t.cargo_type] ?? t.cargo_type}.
                </p>
              )}
              {errors[t.id] && (
                <p role="alert" className="t-body-sm text-[var(--critical)] border-l-2 border-[var(--critical)] pl-2">
                  {errors[t.id]}
                </p>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => startTruck(t)}
                  disabled={!configured || t.running || busyId === t.id}
                  className="btn btn-green flex items-center gap-1.5 flex-1"
                  title={configured ? "Start this truck's delivery" : "Choose a product and destination first"}
                >
                  <Play size={11} aria-hidden /> Start
                </button>
                <button
                  onClick={() => removeTruck(t)}
                  disabled={busyId === t.id}
                  className="btn btn-red flex items-center gap-1.5"
                  title="Remove this truck"
                >
                  <Trash2 size={11} aria-hidden /> Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <p role="alert" className="t-body-sm text-[var(--critical)] border-l-2 border-[var(--critical)] pl-2">
          {error}
        </p>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={startAll}
          disabled={!trucks.some((t) => t.cargo_type && t.destination_id && !t.running)}
          className="btn btn-primary flex-1 flex items-center justify-center gap-2"
        >
          <Play size={13} aria-hidden /> Start all configured
        </button>
      </div>
      {anyRunning && (
        <p className="t-body-sm text-[var(--nominal)]">
          Deliveries running — live on the Live Map. Removing a truck cleans up its
          simulation state; the others are unaffected.
        </p>
      )}
    </section>
  );
}

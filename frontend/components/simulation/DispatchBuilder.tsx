"use client";
import { useCallback, useEffect, useState } from "react";
import { Play, Plus, Trash2, Truck } from "lucide-react";
import { api, post } from "@/lib/api";

/**
 * Operator-defined dispatch: 2-3 trucks, each with an explicitly chosen product
 * and destination warehouse.
 *
 * Placed on the existing /simulation page rather than a new route, so the demo
 * flow stays on one screen. The catalogue (products + candidate destinations)
 * is fetched from GET /api/fleet/dispatch, so nothing here hardcodes an option
 * list that could drift from the simulation.
 *
 * The backend REFUSES an invalid configuration with 400 and a readable reason
 * (unknown product, duplicate destination, incompatible pair). Those messages
 * are surfaced verbatim rather than replaced with a generic error, because the
 * reason is the useful part when configuring.
 */

type Dest = {
  id: string;
  name: string;
  kind: string;
  cargo_types: string[];
  available_capacity: number;
};
type Catalog = { products: string[]; destinations: Dest[] };
type Spec = { name: string; cargo_type: string; destination_id: string; load_units: number };

const PRODUCT_LABEL: Record<string, string> = {
  fresh_produce: "Fresh produce",
  dairy: "Fresh dairy",
  frozen_goods: "Frozen goods",
  pharma: "Pharmaceutical",
};

const blank = (i: number): Spec => ({
  name: `Truck ${String(i + 1).padStart(2, "0")}`,
  cargo_type: "",
  destination_id: "",
  load_units: 400,
});

export default function DispatchBuilder({ onStarted }: { onStarted?: () => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [specs, setSpecs] = useState<Spec[]>([blank(0), blank(1)]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState<{ started: string[] } | null>(null);

  const load = useCallback(() => {
    api<{ catalog: Catalog }>("/api/fleet/dispatch")
      .then((d) => {
        setCatalog(d.catalog);
        // Prefill the product with the first choice so a half-filled row is not
        // the default state; the destination stays empty on purpose, because
        // choosing it is the decision the operator must make.
        setSpecs((prev) =>
          prev.map((s) => (s.cargo_type ? s : { ...s, cargo_type: d.catalog.products[0] ?? "" })),
        );
      })
      .catch(() => setError("Could not load the dispatch catalogue — is the backend running?"));
  }, []);

  useEffect(load, [load]);

  const set = (i: number, patch: Partial<Spec>) =>
    setSpecs((prev) => prev.map((s, n) => (n === i ? { ...s, ...patch } : s)));

  /** Destinations that actually accept the chosen product. */
  const optionsFor = (cargo: string) =>
    (catalog?.destinations ?? []).filter((d) => !cargo || d.cargo_types.includes(cargo));

  const submit = async (thenStart: boolean) => {
    setBusy(true);
    setError(null);
    setRunning(null);
    try {
      const body = {
        trucks: specs.map((s) => ({
          name: s.name,
          cargo_type: s.cargo_type,
          destination_id: s.destination_id,
          load_units: Number(s.load_units) || 400,
        })),
      };
      await post("/api/fleet/dispatch", body);
      if (thenStart) {
        const r = await post<{ started: string[] }>("/api/fleet/dispatch/start");
        setRunning(r);
        onStarted?.();
      }
    } catch (e: any) {
      // The backend's 400 detail is the useful message; fall back only if the
      // failure was not an application-level rejection.
      setError(String(e?.message ?? e).replace(/^\d+\s+[A-Za-z ]+—\s*/, ""));
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    await post("/api/fleet/dispatch/clear").catch(() => {});
    setSpecs([blank(0), blank(1)]);
    setRunning(null);
    setError(null);
    load();
  };

  return (
    <section className="base-card p-4 space-y-3" aria-labelledby="dispatch-h">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <h2 id="dispatch-h" className="t-body font-semibold flex items-center gap-2">
            <Truck size={14} className="text-[var(--accent)]" aria-hidden />
            Plan a delivery — 2 to 3 trucks
          </h2>
          <p className="t-body-sm text-[var(--text3)] mt-0.5">
            You choose the product and the destination. Nothing is assigned automatically.
          </p>
        </div>
        <button onClick={clear} className="chip">Clear</button>
      </div>

      <div className="space-y-2">
        {specs.map((s, i) => {
          const opts = optionsFor(s.cargo_type);
          return (
            <div key={i} className="rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-raised)] p-2.5 space-y-2">
              <div className="flex items-center gap-2">
                <span className="ops-label">{String(i + 1).padStart(2, "0")}</span>
                <input
                  className="flex-1"
                  value={s.name}
                  onChange={(e) => set(i, { name: e.target.value })}
                  placeholder="Truck name"
                  aria-label={`Truck ${i + 1} name`}
                />
                {specs.length > 1 && (
                  <button
                    onClick={() => setSpecs((p) => p.filter((_, n) => n !== i))}
                    className="chip"
                    aria-label={`Remove truck ${i + 1}`}
                    title="Remove this truck"
                  >
                    <Trash2 size={11} aria-hidden />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 items-start">
                <label className="t-label text-[var(--text3)]">
                  Product
                  <select
                    className="mt-1 w-full"
                    value={s.cargo_type}
                    onChange={(e) => set(i, { cargo_type: e.target.value, destination_id: "" })}
                  >
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
                    value={s.destination_id}
                    onChange={(e) => set(i, { destination_id: e.target.value })}
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
                    value={s.load_units}
                    onChange={(e) => set(i, { load_units: Number(e.target.value) })}
                  />
                </label>
              </div>

              {s.cargo_type && opts.length === 0 && (
                <p className="t-body-sm text-[var(--critical)]">
                  No facility accepts {PRODUCT_LABEL[s.cargo_type] ?? s.cargo_type}.
                </p>
              )}
            </div>
          );
        })}
      </div>

      {specs.length < 3 && (
        <button onClick={() => setSpecs((p) => [...p, blank(p.length)])} className="chip flex items-center gap-1.5">
          <Plus size={11} aria-hidden /> Add truck
        </button>
      )}

      {error && (
        <p role="alert" className="t-body-sm text-[var(--critical)] border-l-2 border-[var(--critical)] pl-2">
          {error}
        </p>
      )}
      {running && (
        <p className="t-body-sm text-[var(--nominal)]">
          Running: {running.started.join(", ")} — live on the Live Map.
        </p>
      )}

      <div className="flex gap-2 pt-1">
        <button onClick={() => submit(true)} disabled={busy} className="btn btn-primary flex items-center gap-2">
          <Play size={13} aria-hidden /> Start delivery
        </button>
        <button onClick={() => submit(false)} disabled={busy} className="btn">
          Save plan only
        </button>
      </div>
    </section>
  );
}

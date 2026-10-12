"use client";
// The driver's view. A driver is bound to exactly one truck: if their account
// has no vehicle_id yet they pick one here; after that this page shows only
// their own truck's live telemetry and the predictive verdict for it. This is
// the point of the driver role — an operator sees the fleet, a driver sees the
// one box they are responsible for.
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth, claimTruck, availableTrucks, fetchMe, setSession, getToken } from "@/lib/auth";
import { Loader2, Truck, ThermometerSnowflake, Gauge, Route, CheckCircle2, AlertTriangle } from "lucide-react";

type TruckRow = { vehicle_id: string; driver_name: string; cargo_type: string; taken?: boolean };

export default function DriverPage() {
  const { user, refresh } = useAuth();
  const vehicleId = user?.vehicle_id || null;

  return (
    <div className="mx-auto max-w-3xl p-4 md:p-6">
      <div className="mb-5 flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-[10px] border border-[var(--border-accent)] bg-gradient-to-br from-[#1E3A5F] to-[#0D1623]">
          <Truck size={16} className="text-[var(--accent)]" />
        </span>
        <div className="leading-tight">
          <p className="t-body font-bold tracking-tight text-[var(--text)]">DRIVER CONSOLE</p>
          <p className="t-micro tracking-wider text-[var(--text-muted)]">
            {user?.name ? user.name.toUpperCase() : "ASSIGNED VEHICLE"}
          </p>
        </div>
      </div>

      {vehicleId ? (
        <OwnTruck vehicleId={vehicleId} onUnassign={refresh} />
      ) : (
        <PickTruck onPicked={refresh} />
      )}
    </div>
  );
}

function PickTruck({ onPicked }: { onPicked: () => void }) {
  const [trucks, setTrucks] = useState<TruckRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    availableTrucks().then(setTrucks).catch(() => setTrucks([]));
  }, []);

  const pick = async (vid: string) => {
    setBusy(vid); setErr(null);
    try {
      await claimTruck(vid);
      await onPicked();
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-[var(--r-lg)] border border-[var(--border)] bg-[var(--surface-card)] p-5">
      <p className="t-body font-semibold text-[var(--text)]">Which truck do you drive?</p>
      <p className="mt-1 t-body-sm text-[var(--text-muted)]">
        Pick your vehicle once — this console will then show only that truck.
      </p>
      {err && (
        <div className="mt-3 flex items-start gap-2 rounded-[var(--r-md)] border border-[var(--critical)] px-3 py-2">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--critical)]" />
          <p className="t-body-sm text-[var(--critical)]">{err}</p>
        </div>
      )}
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {trucks === null ? (
          <div className="col-span-full flex items-center gap-2 py-6 text-[var(--text-muted)]">
            <Loader2 size={15} className="animate-spin" /> <span className="t-body-sm">Loading fleet…</span>
          </div>
        ) : trucks.length === 0 ? (
          <p className="col-span-full py-6 t-body-sm text-[var(--text-muted)]">
            No trucks in the fleet yet. Ask an operator to start a dispatch.
          </p>
        ) : (
          trucks.map((t) => (
            <button
              key={t.vehicle_id}
              disabled={busy !== null || t.taken}
              onClick={() => pick(t.vehicle_id)}
              className="flex items-center justify-between gap-2 rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-inset)] px-3 py-2.5 text-left transition-colors hover:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-45"
            >
              <span className="min-w-0">
                <span className="block truncate ops-num text-[var(--t-micro)] font-bold text-[var(--text)]">
                  {t.vehicle_id}
                </span>
                <span className="block truncate t-micro text-[var(--text-muted)]">
                  {t.cargo_type || "—"}
                </span>
              </span>
              {busy === t.vehicle_id ? (
                <Loader2 size={14} className="animate-spin text-[var(--accent)]" />
              ) : (
                <span className="shrink-0 t-micro text-[var(--text-secondary)]">
                  {t.taken ? "taken" : "assign"}
                </span>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function OwnTruck({ vehicleId, onUnassign }: { vehicleId: string; onUnassign: () => void }) {
  const [veh, setVeh] = useState<any | null>(null);
  const [pred, setPred] = useState<any | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const st = await api<any>("/api/fleet/state");
      const v = (st.vehicles || []).find((x: any) => x.vehicle_id === vehicleId);
      setVeh(v || null);
      const pr = await api<any>("/api/fleet/predictions");
      setPred((pr.predictions || []).find((x: any) => x.vehicle_id === vehicleId) || null);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    } finally {
      setLoaded(true);
    }
  }, [vehicleId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  const release = async () => {
    const token = getToken();
    await fetch("/api/auth/unassign-truck", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }).catch(() => {});
    onUnassign();
  };

  if (err) {
    return (
      <div className="flex items-start gap-2 rounded-[var(--r-md)] border border-[var(--critical)] px-3 py-2">
        <AlertTriangle size={14} className="mt-0.5 shrink-0 text-[var(--critical)]" />
        <p className="t-body-sm text-[var(--critical)]">{err}</p>
      </div>
    );
  }
  // Bound to a truck that is no longer in the fleet (dispatch was cleared) —
  // don't spin forever, offer the escape hatch.
  if (loaded && !veh) {
    return (
      <div className="rounded-[var(--r-lg)] border border-[var(--border)] bg-[var(--surface-card)] p-5">
        <p className="t-body-sm font-semibold text-[var(--text)]">
          Your truck ({vehicleId}) is not in the current fleet.
        </p>
        <p className="mt-1 t-body-sm text-[var(--text-muted)]">
          The dispatch may have been reset. Pick another truck to continue.
        </p>
        <button
          onClick={release}
          className="mt-3 rounded-[var(--r-md)] border border-[var(--accent)] bg-[var(--accent)] px-3 py-2 t-body-sm font-bold text-[var(--accent-on)]"
        >
          Pick a different truck
        </button>
      </div>
    );
  }
  if (!veh) {
    return (
      <div className="flex items-center gap-2 py-6 text-[var(--text-muted)]">
        <Loader2 size={15} className="animate-spin" /> <span className="t-body-sm">Loading your truck…</span>
      </div>
    );
  }

  const ref = veh.refrigeration || {};
  const cargo = veh.cargo || {};
  const trip = veh.trip || {};
  const warming = pred?.warming;
  const margin = pred?.safe_margin_c;

  return (
    <div className="space-y-4">
      <div className="rounded-[var(--r-lg)] border border-[var(--border)] bg-[var(--surface-card)] p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="ops-num t-body font-bold text-[var(--text)]">{veh.vehicle_id}</p>
            <p className="t-micro text-[var(--text-muted)]">
              {cargo.cargo_type || "—"} · {veh.driver?.name || "—"}
            </p>
          </div>
          <button
            onClick={release}
            className="t-micro text-[var(--text-muted)] underline hover:text-[var(--text)]"
          >
            change truck
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric icon={<Gauge size={13} />} label="Speed" value={`${(veh.speed_kmh ?? 0).toFixed(0)}`} unit="km/h" />
          <Metric icon={<ThermometerSnowflake size={13} />} label="Cargo temp"
            value={cargo.true_temperature != null ? cargo.true_temperature.toFixed(1) : "—"} unit="°C"
            tone={warming ? "warn" : "ok"} />
          <Metric icon={<Route size={13} />} label="ETA" value={`${(trip.eta_min ?? 0).toFixed(0)}`} unit="min" />
          <Metric icon={<ThermometerSnowflake size={13} />} label="Safe band"
            value={`${cargo.mn ?? "—"}–${cargo.mx ?? "—"}`} unit="°C" />
        </div>
      </div>

      {pred && (
        <div className="rounded-[var(--r-lg)] border border-[var(--border)] bg-[var(--surface-card)] p-5">
          <div className="flex items-center gap-2">
            {warming ? (
              <AlertTriangle size={15} className="text-[var(--warning)]" />
            ) : (
              <CheckCircle2 size={15} className="text-[var(--nominal)]" />
            )}
            <p className="t-body-sm font-bold text-[var(--text)]">{pred.verdict}</p>
          </div>
          <p className="mt-2 t-body-sm text-[var(--text-secondary)]">{pred.remedy}</p>

          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="Trend" value={`${pred.trend_c_per_min >= 0 ? "+" : ""}${pred.trend_c_per_min.toFixed(3)}`} unit="°C/min"
              tone={pred.trend_c_per_min > 0 ? "warn" : "ok"} />
            <Metric label="Margin to limit" value={margin != null ? margin.toFixed(2) : "—"} unit="°C"
              tone={margin != null && margin < 1.5 ? "warn" : "ok"} />
            <Metric label="Confidence" value={pred.projection_confidence?.split(" ")[0] || "—"} unit="" />
          </div>

          {/* The honesty contract travels with the number — this is a linear
              trend projection, NOT a kinetics model; never imply otherwise. */}
          <p className="mt-3 border-t border-[var(--border)] pt-3 t-micro leading-relaxed text-[var(--text-dim)]">
            {pred.model?.replace(/_/g, " ")} · {pred.assumption}
          </p>
        </div>
      )}
    </div>
  );
}

function Metric({
  label, value, unit, icon, tone = "ok",
}: {
  label: string; value: string; unit?: string; icon?: React.ReactNode; tone?: "ok" | "warn";
}) {
  return (
    <div className="rounded-[var(--r-md)] border border-[var(--border)] bg-[var(--surface-inset)] px-3 py-2">
      <p className="flex items-center gap-1.5 ops-label">
        {icon}
        {label}
      </p>
      <p
        className="mt-1 ops-num text-[var(--t-h3)] font-bold leading-none"
        style={{ color: tone === "warn" ? "var(--warning)" : "var(--text)" }}
      >
        {value}
        {unit && <span className="ml-1 t-micro font-normal text-[var(--text-muted)]">{unit}</span>}
      </p>
    </div>
  );
}

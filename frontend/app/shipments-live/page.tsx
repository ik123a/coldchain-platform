"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { FleetTable } from "@/components/live-map/FleetTable";
import { Container, Truck } from "lucide-react";

/** Tive-style shipment list (full-width windowed view) with a Drivers tab. */
export default function ShipmentsLive() {
  const { st } = useStore();
  const router = useRouter();
  const [tab, setTab] = useState<"shipments" | "drivers">("shipments");
  const [filter, setFilter] = useState("ALL");
  const vehicles = (st.fleetVehicles || []) as any[];
  const fleetEvents = (st.fleetEvents || []) as any[];

  const drivers = vehicles
    .filter(v => v.type !== "SERVICE_TRUCK")
    .map(v => ({
      name: v.driver.name, vehicle_id: v.vehicle_id,
      driving_score: v.driver.driving_score,
      safety: Math.max(40, 100 - v.driver.harsh_braking * 3 - v.driver.harsh_accel * 2),
      efficiency: Math.max(40, 100 - v.driver.speeding_events * 2),
      on_time: v.trip?.eta?.arrival_after_critical === false,
      route_adherence: v.route_adherence,
    }))
    .sort((a, b) => b.driving_score - a.driving_score);

  return (
    <div className="fade-in space-y-4 h-[calc(100vh-120px)] flex flex-col">
      <div className="flex items-center gap-3">
        <h2 className="t-metric font-bold headline flex items-center gap-2 flex-1">
          <Truck size={18} className="text-[var(--accent)]" /> Fleet Shipments
        </h2>
        <div className="flex gap-1">
          <button onClick={() => setTab("shipments")} className={`chip t-label ${tab === "shipments" ? "on" : ""}`}>Shipments</button>
          <button onClick={() => setTab("drivers")} className={`chip t-label ${tab === "drivers" ? "on" : ""}`}>Driver Leaderboard</button>
        </div>
      </div>

      <div className="base-card p-3 flex-1 min-h-0">
        {tab === "shipments" ? (
          <FleetTable vehicles={vehicles} events={fleetEvents} filter={filter} setFilter={setFilter}
                      variant="wide"
                      onSelect={(vid) => router.push(`/live-map?focus=${vid}`)}
                      selected={null} />
        ) : (
          <table className="tbl w-full">
            <thead>
              <tr className="t-micro text-[var(--text3)] uppercase">
                <th>#</th><th>Driver</th><th>Vehicle</th><th>Driving Score</th><th>Safety</th><th>Efficiency</th><th>On-Time Safe</th><th>Adherence</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((d, i) => (
                <tr key={d.vehicle_id} className="cursor-pointer"
                    onClick={() => router.push(`/live-map?focus=${d.vehicle_id}`)}>
                  <td className="text-[var(--text3)]">{i + 1}</td>
                  <td><b className="t-label">{d.name}</b></td>
                  <td className="t-label">{d.vehicle_id}</td>
                  <td><span className={`badge ${d.driving_score >= 90 ? "badge-green" : d.driving_score >= 70 ? "badge-amber" : "badge-red"} kpi-num`}>{d.driving_score}</span></td>
                  <td className="t-label kpi-num">{d.safety}</td>
                  <td className="t-label kpi-num">{d.efficiency}</td>
                  <td><span className={`badge ${d.on_time ? "badge-green" : "badge-amber"} t-micro`}>{d.on_time ? "YES" : "AT RISK"}</span></td>
                  <td className="t-label kpi-num">{d.route_adherence}%</td>
                </tr>
              ))}
              {!drivers.length && (
                <tr><td colSpan={8} className="text-center text-[var(--text3)] py-8">
                  waiting for fleet telemetry — open Live Map first
                </td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";

export default function Shipments() {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<any>(null);

  useEffect(() => {
    api(status ? `/api/shipments?status=${status}` : "/api/shipments").then(setRows).catch(() => {});
  }, [status]);

  const filtered = rows.filter(r => !q || r.name.toLowerCase().includes(q.toLowerCase()) || r.cargo_type.includes(q));
  const sev = (r: any) => (open?.id === r.id ? "on" : "");

  return (
    <div className="fade-in space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="t-hero font-bold headline flex-1">Shipments</h1>
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="search shipments / cargo…" className="w-64" />
        <select value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">any status</option>
          <option>IN TRANSIT</option><option>PREPARING</option><option>DELIVERED</option>
        </select>
      </div>

      <div className="base-card overflow-hidden">
        <table className="tbl">
          <thead><tr><th>Shipment</th><th>Cargo</th><th>Origin</th><th>Destination</th><th>Value</th><th>Status</th></tr></thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} onClick={() => setOpen(r)} className="cursor-pointer">
                <td><b>{r.name}</b></td>
                <td>{r.cargo_type.replace("_", " ")}</td>
                <td>{r.origin}</td>
                <td>{r.destination}</td>
                <td className="kpi-num">₹{(r.cargo_value / 1000).toFixed(0)}k</td>
                <td><span className={`badge ${r.status === "IN TRANSIT" ? "badge-green" : "badge-cyan"}`}>{r.status}</span></td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={6} className="text-center text-[var(--text3)] py-8">no shipments match — seed via /api/demo/base</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="base-card p-5 fade-in">
          <div className="flex items-center justify-between">
            <h3 className="t-section font-bold">{open.name} <span className="badge badge-cyan ml-2">{open.cargo_type.replace("_", " ")}</span></h3>
            <button onClick={() => setOpen(null)} className="chip">close ✕</button>
          </div>
          <div className="grid grid-cols-5 gap-3 mt-4 t-body-sm">
            <KV k="Quantity" v={open.quantity + " units"} />
            <KV k="Route" v={`${open.origin} → ${open.destination}`} />
            <KV k="Declared value" v={"₹" + open.cargo_value.toLocaleString()} />
            <KV k="Status" v={open.status} />
            <KV k="Accepted temp" v={"per zone profile"} />
          </div>
          <div className="mt-5 t-body font-semibold mb-2">Journey timeline</div>
          <div className="flex gap-0">
            {["preparing", "loading", "storage", "transport", "incident", "recovery", "arrival"].map((s, i) => (
              <div key={s} className="flex-1 text-center">
                <div className={`h-1.5 ${i === 0 ? "rounded-l-full" : ""} ${i === 6 ? "rounded-r-full" : ""} ${open.status === "IN TRANSIT" && i <= 3 ? "bg-[var(--accent)]" : "bg-[#1d2a3a]"}`} />
                <div className="t-micro text-[var(--text3)] mt-1.5">{s}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return <div><div className="t-micro text-[var(--text3)] uppercase">{k}</div><div className="mt-0.5 font-semibold">{v}</div></div>;
}

"use client";

/**
 * FleetRiskBanner — the worst-offender prediction, always visible.
 *
 * WHY A BANNER
 * ------------
 * PredictiveSafeTime lives inside the telemetry drawer, which means an operator
 * has to click a specific truck to discover that a load is about to spoil. That
 * is the wrong default for a warning: the whole value of P7 is that it fires
 * BEFORE anything looks wrong. A banner driven by the worst current verdict
 * makes the warning unmissable without adding a control to learn.
 *
 * DATA SOURCE
 * -----------
 * GET /api/fleet/predictions is already sorted worst-first by the backend, so
 * this takes the first entry with a non-stable verdict and ignores the rest. If
 * every load is stable the banner renders nothing at all — a permanent "all
 * clear" panel is noise, and the drawer still shows per-truck detail.
 */

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface PredictionRow {
  vehicle_id: string;
  cargo_type: string;
  cargo_temp_c?: number;
  safe_floor_c?: number;
  safe_ceiling_c?: number;
  time_to_critical_min?: number | null;
  margin_vs_eta_min?: number | null;
  verdict?: string;
  remedy?: string;
  projection_confidence?: string;
}

const CALM = new Set([
  "STABLE",
  "SAFE — cargo survives the remaining route",
  "WATCH",
  "RECOVERING",
]);

export function FleetRiskBanner() {
  const [row, setRow] = useState<PredictionRow | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const d = await api<{ predictions?: PredictionRow[]; count?: number }>(
          "/api/fleet/predictions",
        );
        if (!alive) return;
        setTotal(d.count ?? null);
        const worst = (d.predictions ?? []).find((r) => !CALM.has(r.verdict ?? ""));
        setRow(worst ?? null);
      } catch {
        // A failed poll must not blank the banner; the last good row stays.
      }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!row) return null;

  const slack = row.margin_vs_eta_min;
  const critical =
    row.verdict === "ALREADY PAST CRITICAL CEILING" ||
    row.verdict === "ALREADY BELOW SAFE FLOOR" ||
    row.verdict === "WILL SPOIL BEFORE ARRIVAL";

  return (
    <div
      style={{
        border: `1px solid ${critical ? "var(--critical, #ef4444)" : "#f97316"}`,
        background: critical
          ? "rgba(239,68,68,0.10)"
          : "rgba(249,115,22,0.10)",
        borderRadius: 12,
        padding: "12px 14px",
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 12,
      }}
    >
      <div style={{ minWidth: 190 }}>
        <div
          style={{
            fontSize: 10,
            letterSpacing: "0.07em",
            textTransform: "uppercase",
            color: "var(--text3)",
          }}
        >
          Predictive warning
        </div>
        <div
          style={{
            fontSize: 14,
            fontWeight: 700,
            color: critical ? "var(--critical, #ef4444)" : "#f97316",
          }}
        >
          {row.verdict}
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontVariantNumeric: "tabular-nums" }}>
        <div>
          <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase" }}>Vehicle</div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{row.vehicle_id}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase" }}>Cargo</div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{String(row.cargo_type).replace(/_/g, " ")}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase" }}>Temp</div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>
            {row.cargo_temp_c ?? "—"}°C
            <span style={{ color: "var(--text3)", fontWeight: 400 }}>
              {" "}
              ({row.safe_floor_c}–{row.safe_ceiling_c})
            </span>
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase" }}>Safe for</div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>
            {row.time_to_critical_min == null
              ? "—"
              : row.time_to_critical_min <= 0
              ? "now"
              : `${row.time_to_critical_min} min`}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase" }}>Slack</div>
          <div style={{ fontSize: 13, fontWeight: 600, color: slack != null && slack < 0 ? "var(--critical, #ef4444)" : undefined }}>
            {slack == null ? "—" : `${slack > 0 ? "+" : ""}${slack} min`}
          </div>
        </div>
      </div>

      {row.remedy && (
        <div style={{ flex: "1 1 260px", fontSize: 12.5, lineHeight: 1.5, color: "var(--text3)" }}>
          {row.remedy}
        </div>
      )}

      {total != null && (
        <div style={{ fontSize: 11, color: "var(--text3)", marginLeft: "auto" }}>
          worst of {total} loads
        </div>
      )}
    </div>
  );
}

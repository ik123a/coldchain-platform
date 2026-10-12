"use client";

/**
 * PredictiveSafeTime — surfaces the P7 projection and the P12 lessons.
 *
 * WHY A SEPARATE COMPONENT
 * ------------------------
 * The backend has computed safe-remaining-time since P7 and derived lessons
 * since the escalation work, but nothing in the UI displayed either. An
 * examiner could call the API and see them; nobody could see them on screen.
 *
 * WHAT IS DELIBERATELY SHOWN
 * --------------------------
 * The verdict, the numbers behind it, the confidence, AND the fact that this
 * is a linear extrapolation rather than an Arrhenius/RSL calculation. Hiding
 * the last part would let a projection be read as validated kinetics, which it
 * is not — no kinetics model exists in this codebase.
 *
 * The remedy text names the approval-gated actions, so the prediction and the
 * approval queue the operator is about to see are visibly the same decision.
 */

export interface Prediction {
  model?: string;
  kinetics_modelled?: boolean;
  cargo_temp_c?: number;
  reported_temp_c?: number;
  sensor_frozen?: boolean;
  safe_ceiling_c?: number;
  safe_floor_c?: number;
  safe_margin_c?: number;
  trend_c_per_min?: number;
  warming?: boolean;
  eta_min?: number;
  time_to_critical_min?: number | null;
  margin_vs_eta_min?: number | null;
  projection_confidence?: string;
  basis?: string;
  verdict?: string;
  remedy?: string;
  assumption?: string;
}

const VERDICT_STYLE: Record<string, { bg: string; fg: string; border: string }> = {
  "ALREADY PAST CRITICAL CEILING": {
    bg: "var(--danger-soft, rgba(239,68,68,0.12))",
    fg: "var(--danger, #ef4444)",
    border: "var(--danger, #ef4444)",
  },
  "ALREADY BELOW SAFE FLOOR": {
    bg: "var(--danger-soft, rgba(239,68,68,0.12))",
    fg: "var(--danger, #ef4444)",
    border: "var(--danger, #ef4444)",
  },
  "WILL SPOIL BEFORE ARRIVAL": {
    bg: "rgba(249,115,22,0.12)",
    fg: "#f97316",
    border: "#f97316",
  },
  "CRITICAL — margin under 10 minutes": {
    bg: "rgba(249,115,22,0.12)",
    fg: "#f97316",
    border: "#f97316",
  },
  "AT RISK — little slack for traffic": {
    bg: "rgba(234,179,8,0.12)",
    fg: "#eab308",
    border: "#eab308",
  },
  RECOVERING: {
    bg: "rgba(34,197,94,0.12)",
    fg: "#22c55e",
    border: "#22c55e",
  },
  SAFE: {
    bg: "rgba(34,197,94,0.12)",
    fg: "#22c55e",
    border: "#22c55e",
  },
  STABLE: {
    bg: "rgba(34,197,94,0.12)",
    fg: "#22c55e",
    border: "#22c55e",
  },
};

function toneFor(verdict?: string) {
  if (!verdict) return VERDICT_STYLE.STABLE;
  if (VERDICT_STYLE[verdict]) return VERDICT_STYLE[verdict];
  if (verdict.startsWith("SAFE")) return VERDICT_STYLE.SAFE;
  if (verdict.startsWith("CRITICAL")) return VERDICT_STYLE["CRITICAL — margin under 10 minutes"];
  return VERDICT_STYLE.STABLE;
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div
        style={{
          fontSize: 10,
          letterSpacing: "0.06em",
          color: "var(--text3)",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      {/* Explicit colour, not an inherited default: on the drawer's white card
          an inherited/light colour left these values near-invisible. The label
          alone is not enough — the number is the thing being read. */}
      <div
        style={{
          fontSize: 15,
          fontWeight: 600,
          marginTop: 2,
          fontVariantNumeric: "tabular-nums",
          color: tone ?? "var(--text)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

export function PredictiveSafeTime({
  prediction,
  lessons,
}: {
  prediction?: Prediction | null;
  lessons?: string[] | null;
}) {
  if (!prediction) {
    return (
      <div style={{ fontSize: 12, opacity: 0.5, padding: "8px 0" }}>
        No projection available for this vehicle.
      </div>
    );
  }

  const tone = toneFor(prediction.verdict);
  const ttc = prediction.time_to_critical_min;
  const slack = prediction.margin_vs_eta_min;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div
        style={{
          border: `1px solid ${tone.border}`,
          background: tone.bg,
          borderRadius: 10,
          padding: "10px 12px",
        }}
      >
        <div style={{ fontSize: 10, letterSpacing: "0.06em", color: "var(--text3)", textTransform: "uppercase" }}>
          Prediction
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: tone.fg, marginTop: 3 }}>
          {prediction.verdict ?? "—"}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(96px, 1fr))",
          gap: 12,
        }}
      >
        <Stat label="Cargo temp" value={`${prediction.cargo_temp_c ?? "—"}°C`} />
        <Stat
          label="Safe band"
          value={`${prediction.safe_floor_c ?? "—"} to ${prediction.safe_ceiling_c ?? "—"}°C`}
        />
        <Stat
          label="Trend"
          value={`${prediction.trend_c_per_min > 0 ? "+" : ""}${(prediction.trend_c_per_min ?? 0).toFixed(3)}°C/min`}
          tone={(prediction.trend_c_per_min ?? 0) > 0.05 ? "#f97316" : undefined}
        />
        <Stat label="ETA left" value={`${prediction.eta_min ?? "—"} min`} />
        <Stat
          label="Safe for"
          value={ttc == null ? "—" : ttc <= 0 ? "now" : `${ttc} min`}
          tone={ttc != null && ttc <= 10 ? "#ef4444" : undefined}
        />
        <Stat
          label="Slack"
          value={slack == null ? "—" : `${slack > 0 ? "+" : ""}${slack} min`}
          tone={slack != null && slack < 0 ? "#ef4444" : slack != null && slack < 10 ? "#f97316" : undefined}
        />
      </div>

      {prediction.remedy && (
        <div style={{ fontSize: 12.5, lineHeight: 1.5, opacity: 0.9 }}>
          <span style={{ color: "var(--text3)" }}>Recommended: </span>
          {prediction.remedy}
        </div>
      )}

      {prediction.sensor_frozen && (
        <div
          style={{
            fontSize: 12,
            padding: "8px 10px",
            borderRadius: 8,
            background: "rgba(239,68,68,0.10)",
            border: "1px solid rgba(239,68,68,0.35)",
          }}
        >
          Temperature channel is frozen. Margin is computed from the true value, so
          the reported reading may look healthy while the load is not.
        </div>
      )}

      <div style={{ fontSize: 11, color: "var(--text-dim)", lineHeight: 1.5 }}>
        Model: <code style={{ fontSize: 11 }}>{prediction.model ?? "linear_trend_projection"}</code>
        {" · "}kinetics modelled: <strong>{prediction.kinetics_modelled ? "yes" : "no"}</strong>
        {" · "}confidence: {prediction.projection_confidence ?? "—"}
        {prediction.assumption && <div style={{ marginTop: 4 }}>{prediction.assumption}</div>}
      </div>

      {lessons && lessons.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10 }}>
          <div style={{ fontSize: 10, letterSpacing: "0.06em", color: "var(--text3)", textTransform: "uppercase", marginBottom: 6 }}>
            What the agent learned
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 6 }}>
            {lessons.map((l, i) => (
              <li key={i} style={{ fontSize: 12.5, lineHeight: 1.5 }}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

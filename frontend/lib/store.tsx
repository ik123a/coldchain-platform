"use client";
import { createContext, useContext, useMemo, useReducer, useEffect, ReactNode } from "react";
import { api, post } from "./api";
import { WS_URL } from "./api";

export interface Reading {
  tick: number; temperature: number; true_temperature: number; humidity: number;
  ambient_temperature: number; door_open: boolean; compressor_on: boolean;
  backup_cooling: boolean; power_ok: boolean; battery_level: number; cargo_health: number;
  risk_score: number; risk_level: string; exposure_ticks: number; peak_temperature: number;
  scenario: string; zone: { mn: number; mx: number; hum_min?: number; hum_max?: number };
  cargo_type: string; simulation_id: number; status?: string; speed?: number;
}
export interface AgentEvent {
  ts: string; agent: string | null; kind: string; detail?: string;
  root_cause?: string; confidence?: number; actions?: any[];
  score?: number; level?: string; components?: any[];
  signal?: number; verified?: boolean; evidence?: string[];
}
export interface IncidentSummary {
  id: number; simulation_id: number; type: string; severity: string; status: string;
  detected_at: string; resolved_at: string | null; detected_tick: number; resolved_tick: number | null;
  root_cause: string | null; description: string; peak_temperature: number;
  root_cause_confidence: number | null;
}

interface State {
  status: any | null;
  dashboard: any | null;
  sim: Reading | null;
  history: Reading[];
  events: AgentEvent[];
  incidents: IncidentSummary[];
  agentsStatus: Record<string, { status: string; note?: string }>;
  connected: boolean;
  theme: "dark" | "light" | "system";
  selectedIncident?: number | null;
  toasts: { id: number; text: string; sev: string }[];
  fleetVehicles?: any[];
  fleetEvents?: any[];
  fleetMeta?: { simMinute?: number; weather?: string };
}

const defaultAgents = {
  monitoring: { status: "ACTIVE", note: "" },
  diagnosis: { status: "STANDBY", note: "" },
  risk_analyst: { status: "STANDBY", note: "" },
  response_planner: { status: "STANDBY", note: "" },
  recovery_verifier: { status: "STANDBY", note: "" },
  reporter: { status: "STANDBY", note: "" },
};

const initial: State = {
  status: null, dashboard: null, sim: null, history: [], events: [], incidents: [],
  agentsStatus: defaultAgents, connected: false, theme: "dark", selectedIncident: null, toasts: [],
  fleetVehicles: [], fleetEvents: [], fleetMeta: {},
};

type Action = { type: string; payload?: any };
function reducer(st: State, a: Action): State {
  switch (a.type) {
    case "status": return { ...st, status: a.payload };
    case "dashboard": return { ...st, dashboard: a.payload };
    case "reading": {
      const r = a.payload as Reading;
      const history = [...st.history, r].slice(-400);
      return { ...st, sim: r, history };
    }
    case "event": {
      const ev = a.payload as AgentEvent;
      const agentsStatus = { ...st.agentsStatus };
      if (ev.agent) {
        const busy = ({ diagnosis: "diagnosis_complete", risk: "risk_assessed", planner: "plan_ready" } as any)[ev.agent]
        agentsStatus[ev.agent] = { status: "ANALYZING", note: ev.kind };
        // map some events into agent status changes
        if (ev.kind === "diagnosis_complete") agentsStatus["diagnosis"] = { status: "COMPLETE", note: ev.root_cause };
        if (ev.kind === "risk_assessed") agentsStatus["risk_analyst"] = { status: "COMPLETE", note: ev.level };
        if (ev.kind === "plan_ready") agentsStatus["response_planner"] = { status: "COMPLETE", note: `${ev.actions?.length || 0} actions` };
        if (ev.kind === "verification") agentsStatus["recovery_verifier"] = { status: ev.verified ? "VERIFIED" : "ANALYZING", note: (ev.evidence || [])[0] };
        if (ev.kind === "report_ready") agentsStatus["reporter"] = { status: "COMPLETE", note: `score ${ev.score}` };
        if (ev.kind === "incident_detected") { Object.keys(agentsStatus).forEach(k => { if (k !== "monitoring") agentsStatus[k] = { status: "STANDBY", note: "" } }); }
      }
      const toasts = [...st.toasts, { id: Date.now() + Math.random(), text: ev.detail || ev.kind, sev: ev.kind.includes("detected") ? "CRITICAL" : ev.kind.includes("resolved") || ev.kind.includes("verified") ? "OK" : "INFO" }].slice(-5);
      return { ...st, events: [ev, ...st.events].slice(0, 90), agentsStatus, selectedIncident: ev.simulation_id ? st.selectedIncident ?? st.incidents[0]?.id : st.selectedIncident, toasts };
    }
    case "fleet": {
      const p = a.payload as any;
      return { ...st, fleetVehicles: p.vehicles || [],
               fleetMeta: { simMinute: p.sim_minute, weather: p.weather, ambient: p.ambient_c,
                            segments: p.weather?.segments } };
    }
    case "fleet_event": {
      const ev = a.payload as any;
      const t = ev.type as string;
      const toasts = [...st.toasts];
      if (["fleet.incident.created", "ai.route.decision", "vehicle.route.changed", "cargo.transferred"].includes(t)) {
        toasts.push({ id: Date.now() + Math.random(),
                      text: t === "ai.route.decision"
                        ? `AI: ${ev.decision} -> ${ev.target} (${ev.vehicle_id})`
                        : t === "fleet.incident.created"
                        ? `INCIDENT ${ev.vehicle_id}: ${ev.root_cause}`
                        : t === "vehicle.route.changed"
                        ? `${ev.vehicle_id} rerouted -> ${ev.new_target}`
                        : `${ev.vehicle_id} transferred ${ev.units}u`,
                      sev: t === "fleet.incident.created" ? "CRITICAL" : t === "ai.route.decision" ? "INFO" : "OK" });
      }
      return { ...st, fleetEvents: [ev, ...st.fleetEvents].slice(0, 90),
               fleetMeta: { simMinute: ev.sim_minute ?? st.fleetMeta?.simMinute, weather: ev.weather ?? st.fleetMeta?.weather },
               toasts: toasts.slice(-5) };
    }
    case "incidents": return { ...st, incidents: a.payload };
    case "select_incident": return { ...st, selectedIncident: a.payload };
    case "connected": return { ...st, connected: a.payload };
    case "theme": return { ...st, theme: a.payload };
    case "dismiss_toast": return { ...st, toasts: st.toasts.filter(t => t.id !== a.payload) };
    case "sim_status": return { ...st, sim: st.sim ? { ...st.sim, status: a.payload } : st.sim };
    default: return st;
  }
}

const Ctx = createContext<{ st: State; dispatch: (a: Action) => void }>({ st: initial, dispatch: () => {} });
export const useStore = () => useContext(Ctx);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [st, dispatch] = useReducer(reducer, initial);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: any;
    const connect = () => {
      try {
        ws = new WebSocket(WS_URL);
        ws.onopen = () => dispatch({ type: "connected", payload: true });
        ws.onmessage = (e) => {
          try {
            const m = JSON.parse(e.data);
            if (m.type === "sensor_update") dispatch({ type: "reading", payload: m as Reading });
            else if (m.type === "vehicle.position.updated")
              dispatch({ type: "fleet", payload: { vehicles: m.vehicles, sim_minute: m.sim_minute,
                                                  weather: m.weather, ambient_c: m.ambient_c } });
            else if (["hello"].includes(m.type)) { /* greeting */ }
            else if (["agent_event", "alert"].includes(m.type)) dispatch({ type: "event", payload: m });
            else dispatch({ type: "fleet_event", payload: m });
            if (m.type === "incident_detected" || m.type === "fleet.incident.created") loadIncidents();
          } catch {}
        };
        ws.onclose = () => { dispatch({ type: "connected", payload: false }); timer = setTimeout(connect, 1500); };
        ws.onerror = () => ws.close();
      } catch { timer = setTimeout(connect, 2000); }
    };
    connect();
    const poll = async () => {
      try { dispatch({ type: "status", payload: await api("/api/status") }); } catch {}
      try { dispatch({ type: "dashboard", payload: await api("/api/dashboard") }); } catch {}
      loadIncidents();
    };
    poll();
    const pi = setInterval(poll, 4000);
    return () => { clearTimeout(timer); ws?.close(); clearInterval(pi); };
  }, []);

  async function loadIncidents() {
    try { dispatch({ type: "incidents", payload: await api("/api/incidents") }); } catch {}
  }

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", st.theme);
  }, [st.theme]);

  const value = useMemo(() => ({ st, dispatch }), [st]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

"use client";
import { createContext, useContext, useMemo, useReducer, useEffect, useRef, useState, ReactNode } from "react";
import { api } from "./api";
import { WS_URL, fetchWsTicket } from "./api";
import { useAuth } from "./auth";

// Bounded reconnect: after this many consecutive failures stop retrying and let
// the 4s REST poll keep the views fresh, rather than hammering the mint endpoint.
const MAX_WS_RETRIES = 6;
import { resolveTheme, THEME_KEY, type Theme } from "./theme";

export interface Notice {
  id: number;
  text: string;
  sev: "CRITICAL" | "INFO" | "OK";
  source: string;
  at: string;
  read: boolean;
}

// The activity centre keeps a full history rather than the 5-item window the
// old toast stack used. These notices no longer expire on a timer, so a bounded
// buffer would silently discard the record an examiner might scroll back to.
const NOTICE_MAX = 100;

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
  simulation_id?: number;
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
  theme: Theme;
  selectedIncident?: number | null;
  notices: Notice[];
  fleetVehicles?: any[];
  fleetEvents?: any[];
  fleetWarehouses?: any[];
  fleetDestinations?: any[];
  fleetCounts?: Record<string, number>;
  fleetRegion?: { name?: string; center?: [number, number]; zoom?: number } | null;
  fleetPaused?: boolean;
  fleetSpeed?: number;
  fleetMeta?: { simMinute?: number; weather?: any; ambient?: number; segments?: any };
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
  // Read the stored preference during initialisation rather than defaulting to
  // "dark" and correcting in an effect. On the server there is no
  // localStorage, so this returns "system" — which is also the correct
  // server-side answer, and matches what the boot script resolves to.
  // The point is that "system" and an unreadable store are the same case:
  // defer to the OS. The previous hardcoded "dark" meant the settings chips
  // showed dark as selected on every load until someone clicked Light.
  theme: (typeof window !== "undefined"
    ? ((localStorage.getItem(THEME_KEY) as Theme | null) ?? "system")
    : "system"),
  connected: false, selectedIncident: null, notices: [],
  agentsStatus: defaultAgents,
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
        agentsStatus[ev.agent] = { status: "ANALYZING", note: ev.kind };
        // map some events into agent status changes
        if (ev.kind === "diagnosis_complete") agentsStatus["diagnosis"] = { status: "COMPLETE", note: ev.root_cause };
        if (ev.kind === "risk_assessed") agentsStatus["risk_analyst"] = { status: "COMPLETE", note: ev.level };
        if (ev.kind === "plan_ready") agentsStatus["response_planner"] = { status: "COMPLETE", note: `${ev.actions?.length || 0} actions` };
        if (ev.kind === "verification") agentsStatus["recovery_verifier"] = { status: ev.verified ? "VERIFIED" : "ANALYZING", note: (ev.evidence || [])[0] };
        if (ev.kind === "report_ready") agentsStatus["reporter"] = { status: "COMPLETE", note: `score ${ev.score}` };
        if (ev.kind === "incident_detected") { Object.keys(agentsStatus).forEach(k => { if (k !== "monitoring") agentsStatus[k] = { status: "STANDBY", note: "" } }); }
      }
      const notice: Notice = {
        id: Date.now() + Math.random(),
        text: ev.detail || ev.kind,
        sev: ev.kind.includes("detected") ? "CRITICAL" : ev.kind.includes("resolved") || ev.kind.includes("verified") ? "OK" : "INFO",
        source: ev.agent || "agent",
        at: new Date().toISOString(),
        read: false,
      };
      return {
        ...st,
        events: [ev, ...st.events].slice(0, 90),
        agentsStatus,
        selectedIncident: ev.simulation_id ? st.selectedIncident ?? st.incidents[0]?.id : st.selectedIncident,
        notices: [notice, ...st.notices].slice(0, NOTICE_MAX),
      };
    }
    case "fleet": {
      const p = a.payload as any;
      return { ...st,
               fleetVehicles: p.vehicles || [],
               fleetWarehouses: p.warehouses ?? st.fleetWarehouses,
               fleetDestinations: p.destinations ?? st.fleetDestinations,
               fleetCounts: p.counts ?? st.fleetCounts,
               fleetRegion: p.region ?? st.fleetRegion,
               fleetPaused: p.paused ?? st.fleetPaused,
               fleetSpeed: p.speed ?? st.fleetSpeed,
               fleetMeta: { ...st.fleetMeta,
                            simMinute: p.sim_minute ?? st.fleetMeta?.simMinute,
                            weather: p.weather ?? st.fleetMeta?.weather,
                            ambient: p.ambient_c ?? p.weather?.ambient_c ?? st.fleetMeta?.ambient,
                            segments: p.weather?.segments ?? st.fleetMeta?.segments } };
    }
    case "fleet_event": {
      const ev = a.payload as any;
      const t = ev.type as string;
      // A truck removed by the operator disappears from the dashboard the
      // moment the event arrives — not up to 4s later when the REST poll
      // happens to overwrite the list.
      if (t === "vehicle.removed") {
        return { ...st,
                 fleetVehicles: (st.fleetVehicles ?? []).filter(
                   (v: any) => v.vehicle_id !== ev.vehicle_id),
                 fleetEvents: [ev, ...st.fleetEvents].slice(0, 90),
                 notices: [{ id: Date.now() + Math.random(),
                             text: `${ev.vehicle_id} removed from the fleet`,
                             sev: "INFO" as const, source: t,
                             at: new Date().toISOString(), read: false },
                           ...st.notices].slice(0, NOTICE_MAX) };
      }
      let notices = st.notices;
      const LABELS: Record<string, [string, "CRITICAL" | "INFO" | "OK"]> = {
        "fleet.incident.created": [`INCIDENT ${ev.vehicle_id}: ${ev.root_cause}`, "CRITICAL"],
        "ai.route.decision": [`AI recommends ${ev.decision} to ${ev.target} (${ev.vehicle_id})`, "INFO"],
        "ai.approval.requested": [`Approval needed: ${ev.vehicle_name ?? ev.vehicle_id} to ${ev.target}`, "CRITICAL"],
        "ai.approval.resolved": [
          `Operator ${ev.approved ? "APPROVED" : "REJECTED"} ${ev.vehicle_id} to ${ev.target}`, "OK"],
        "vehicle.route.changed": [`${ev.vehicle_id} rerouted to ${ev.new_target}`, "OK"],
        "cargo.transferred": [`${ev.vehicle_id} transferred ${ev.units}u`, "OK"],
        "weather.changed": [`Weather: ${ev.weather}`, "INFO"],
        "vehicle.failure.injected": [`Failure injected on ${ev.vehicle_id}: ${ev.failure}`, "CRITICAL"],
      };
      const hit = LABELS[t];
      if (hit) {
        notices = [{ id: Date.now() + Math.random(), text: hit[0], sev: hit[1], source: t, at: new Date().toISOString(), read: false }, ...notices].slice(0, NOTICE_MAX);
      }
      return { ...st, fleetEvents: [ev, ...st.fleetEvents].slice(0, 90),
               fleetMeta: { simMinute: ev.sim_minute ?? st.fleetMeta?.simMinute, weather: ev.weather ?? st.fleetMeta?.weather },
               notices };
    }
    case "incidents": return { ...st, incidents: a.payload };
    case "select_incident": return { ...st, selectedIncident: a.payload };
    case "connected": return { ...st, connected: a.payload };
    case "theme": return { ...st, theme: a.payload };
    case "ack_notice":
      return {
        ...st,
        notices: st.notices.map((n) =>
          a.payload === "all" ? { ...n, read: true }
          : n.id === a.payload ? { ...n, read: true } : n),
      };
    case "clear_notices": return { ...st, notices: st.notices.filter((n) => !n.read) };
    case "sim_status": return { ...st, sim: st.sim ? { ...st.sim, status: a.payload } : st.sim };
    default: return st;
  }
}

const Ctx = createContext<{ st: State; dispatch: (a: Action) => void }>({ st: initial, dispatch: () => {} });
export const useStore = () => useContext(Ctx);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [st, dispatch] = useReducer(reducer, initial);
  // Session state drives the socket. `user` (from the auth context that wraps
  // this provider) is a RELIABLE change signal on login/logout; reading
  // localStorage alone would not re-render this component reliably, so the
  // socket could miss a login or survive a logout.
  const { user } = useAuth();
  const activeSocket = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<any>(null);
  const attempts = useRef(0);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    let pi: any;
    const poll = async () => {
      try { dispatch({ type: "status", payload: await api("/api/status") }); } catch {}
      try { dispatch({ type: "dashboard", payload: await api("/api/dashboard") }); } catch {}
      try { dispatch({ type: "fleet", payload: await api("/api/fleet/state") }); } catch {}
      loadIncidents();
    };
    poll();
    pi = setInterval(poll, 4000);
    return () => {
      clearInterval(pi);
    };
  }, []);

  // Connect only while a session exists; tear the socket down when it ends.
  //
  // Every attempt mints a FRESH ticket: tickets are single-use, so reusing the
  // previous value would be rejected as a replay and the socket would never
  // recover. Retries are bounded with exponential backoff — a tight loop against
  // the mint endpoint is exactly the abuse the rate limiter exists to stop.
  useEffect(() => {
    if (!user) {
      // No session: nothing to authorize, and any existing socket must go.
      activeSocket.current?.close();
      activeSocket.current = null;
      return;
    }
    let cancelled = false;
    let sock: WebSocket | null = null;

    function scheduleRetry() {
      if (cancelled || attempts.current >= MAX_WS_RETRIES) return;
      const delay = Math.min(1500 * 2 ** attempts.current, 30000);
      attempts.current += 1;
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = setTimeout(() => setRetryTick((n) => n + 1), delay);
    }

    (async () => {
      try {
        const t = await fetchWsTicket();
        if (cancelled) return;
        if (!t) { scheduleRetry(); return; }
        // One owner at a time: a lingering socket (StrictMode double-invoke or a
        // fast re-login) must not keep dispatching into the store alongside this.
        activeSocket.current?.close();
        sock = new WebSocket(WS_URL, [`cc-ticket.${t.ticket}`]);
        activeSocket.current = sock;
        sock.onopen = () => { attempts.current = 0; dispatch({ type: "connected", payload: true }); };
        sock.onmessage = (e) => {
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
        sock.onclose = () => {
          dispatch({ type: "connected", payload: false });
          scheduleRetry();
        };
        sock.onerror = () => sock?.close();
      } catch {
        scheduleRetry();
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer.current);
      sock?.close();
      if (activeSocket.current === sock) activeSocket.current = null;
    };
  }, [user, retryTick]);

  async function loadIncidents() {
    try { dispatch({ type: "incidents", payload: await api("/api/incidents") }); } catch {}
  }

  useEffect(() => {
    const apply = () => {
      document.documentElement.setAttribute("data-theme", resolveTheme(st.theme));
      try { localStorage.setItem(THEME_KEY, st.theme); } catch {}
    };
    apply();
    if (st.theme !== "system") return;
    // Only listen while the preference actually defers to the OS —
    // a leaked listener under a fixed choice would flip the page
    // mid-session whenever the machine crossed dusk.
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [st.theme]);

  const value = useMemo(() => ({ st, dispatch }), [st]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

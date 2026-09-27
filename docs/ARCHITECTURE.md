# System Architecture & Design

**Course:** CBCA301 Capstone Project · **Rubric item:** Milestone-2 →
*System / Technical Design (5 marks)*

Descriptor for the top band: *"Novel Architecture, More than 5 modules
designed, good technical decisions and coherence."* This project has **26
backend/simulation modules** (11 API route groups + 15 simulation modules),
**15 database tables**, and 14 frontend routes.

*Counts verified against the source on 27 Sep 2026; see §2.*

---

## 1. Architecture at a glance

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION — Next.js 15 App Router · React 19 · Tailwind 4        │
│                                                                       │
│  /  /dashboard  /live-map  /incidents  /analytics  /simulation       │
│  /twin  /copilot  /reports  /settings  /shipments  /shipments-live    │
│  /design-references  /design-reference-board                          │
│                                                                       │
│  Live telemetry: WebSocket (store.tsx) + REST fallback               │
│  Map: MapLibre GL, GeoJSON sources `veh` (points) + `trail` (lines)  │
└───────────────┬──────────────────────────────────────────────────────┘
                │  HTTP / WS
┌───────────────▼──────────────────────────────────────────────────────┐
│  API LAYER — FastAPI · 11 route modules                               │
│                                                                       │
│  analytics  auth  demo  facilities  fleet  gemini  incidents          │
│  reports  shipments  simulations  status                              │
│                                                                       │
│  Cross-cutting: CORS policy · status reconciliation · DTO schemas    │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  SIMULATION LAYER — 15 modules, deterministic, no LLM                 │
│                                                                       │
│  engine ── clock ── runner ── geo_data ── traffic                     │
│     │                                                                 │
│     ├── agents_d (6 operational agents)                               │
│     ├── fleet_agents · fleet_ops · fleet_orchestrator                 │
│     ├── anomaly · risk · routing · analytics · events                 │
│                                                                       │
│  RUNNERS registry: authoritative source of "what is actually live"   │
└───────────────┬──────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────┐
│  PERSISTENCE — SQLAlchemy · SQLite · 15 tables                        │
│                                                                       │
│  users  facilities  zones  shipments  simulations  sensor_readings    │
│  incidents  ai_analyses  recommended_actions  alerts                  │
│  fleet_vehicles  fleet_routes  fleet_vehicle_events                   │
│  fleet_route_decisions  fleet_cargo_transfers                         │
└──────────────────────────────────────────────────────────────────────┘
```

**Design decision — the simulation is authoritative, the database is a record.**
The `RUNNERS` registry in `runner.py` is the source of truth for "is this
simulation actually running". A database row marked `RUNNING` is not evidence
of a live process. This distinction was found by measurement: nine seed rows
reported `RUNNING` with no runner behind them. Status now reconciles the two
and reports `simulations_orphaned` separately.

## 2. Module inventory (26)

### API (11)
| Module | Responsibility |
|---|---|
| `analytics.py` | KPI aggregation, incident analytics |
| `auth.py` | Login, token issue/verify |
| `demo.py` | Demo-mode helpers |
| `facilities.py` | Facilities, zones, docks |
| `fleet.py` | Fleet vehicles, routes, live positions |
| `gemini.py` | Design-reference asset generation (**not** operational) |
| `incidents.py` | Incident lifecycle, replay |
| `reports.py` | Report generation |
| `shipments.py` | Shipment records |
| `simulations.py` | Run control: start, pause, resume |
| `status.py` | Health, reconciliation, system status |

### Simulation (15)
| Module | Responsibility |
|---|---|
| `engine.py` | Tick loop, world state |
| `clock.py` | Deterministic time source |
| `runner.py` | Run lifecycle, `RUNNERS` registry |
| `agents_d.py` | Six operational agents (rule-based) |
| `fleet_agents.py` | Deterministic fleet agents |
| `fleet_ops.py` | Service, repair, cargo transfer |
| `fleet_orchestrator.py` | Fleet incident stream (separate ID space) |
| `anomaly.py` | Excursion detection |
| `risk.py` | Risk classification |
| `routing.py` | Reroute computation |
| `analytics.py` | Run analytics |
| `events.py` | World events: heatwave, rain, fog |
| `geo_data.py` | Geographic data |
| `traffic.py` | Traffic simulation |
| `fleet.py` | Fleet state, per-counter alert deltas |

## 3. The six operational agents

| Agent | Decision responsibility |
|---|---|
| Sensor/Compressor agent | Detects equipment failure (compressor, door, power) |
| Thermal agent | Evaluates cargo temperature against the cargo class's own band |
| Traffic agent | Models congestion effect on transit time |
| Route agent | Computes reroute candidates |
| Risk agent | Aggregates signals into a risk classification |
| Recovery agent | Chooses service / transfer / reroute and drives it |

**Every agent is rule-based Python.** Verified: the operational path contains
zero LLM imports. Gemini/OpenAI keys are confined to
`app/services/gemini/`, which generates *design reference images* only.

This is a deliberate rubric-driven choice. *Performance and Results* scores
"reproducible results"; an LLM in the decision loop would forfeit that. The UI
therefore reports `ai_mode = DETERMINISTIC-AGENTS` and the header is gated on
that exact string, so the product cannot imply an LLM it does not use.

## 4. Data design

**15 tables** across two model modules:

| Model file | Tables |
|---|---|
| `models/entities.py` | `users`, `facilities`, `zones`, `shipments`, `simulations`, `sensor_readings`, `incidents`, `ai_analyses`, `recommended_actions`, `alerts` |
| `models/fleet.py` | `fleet_vehicles`, `fleet_routes`, `fleet_vehicle_events`, `fleet_route_decisions`, `fleet_cargo_transfers` |

**Core relationships**

```
facilities 1───* zones 1───* sensor_readings
shipments  *───1 facilities
fleet_vehicles *───1 shipments
fleet_routes   *───1 facilities (origin → destination)
fleet_vehicle_events  *───1 fleet_vehicles     (append-only event log)
fleet_route_decisions *───1 fleet_vehicles     (reroute audit trail)
fleet_cargo_transfers *───1 fleet_vehicles     (truck-to-truck transfer)
simulations 1───* sensor_readings
simulations 1───* incidents
incidents   *───* recommended_actions
```

**Two incident ID spaces — and why it matters**

| Space | Owner | Lifecycle |
|---|---|---|
| `incidents.simulation_id = 0` | `fleet_orchestrator.py` | Fleet-stream incidents, independent lifecycle |
| `incidents.simulation_id = N` | `runner.py` | Per-simulation, ends in `RESOLVED` via `RecoveryVerifier` |

An earlier analysis wrongly reported 32 open incidents as a monotonic leak. On
inspection, 27 belonged to the fleet-orchestrator space and 5 of the 10
per-simulation incidents had already reached `RESOLVED`. Treating them as one
counter would have been a false diagnosis and a wrong fix.

**Sensor readings** are append-only time series keyed by vehicle and tick —
which is what makes the deterministic replay and the `twin` reconstruction
possible.

## 5. Key technical decisions

| # | Decision | Rationale | Alternative rejected |
|---|---|---|---|
| D1 | Rule-based agents, not LLM | Reproducibility is a scored criterion; identical seed → identical output | LLM decision layer — more impressive, non-reproducible |
| D2 | `RUNNERS` registry authoritative over DB rows | A `RUNNING` row is not a live process; this surfaced 9 phantom runs | Trusting the DB — reports things that aren't happening |
| D3 | Cargo-specific temperature bands | A single 8 °C threshold false-flagged frozen cargo at a correct −18 °C | Global threshold — simpler, wrong |
| D4 | Per-counter alert deltas | Differencing a *sum* of cumulative counters produced phantom alerts (154–224) on healthy vehicles | Sum-based diff — numerically wrong |
| D5 | Interpolate only the vehicle GeoJSON source | Calling `setData` on both sources per frame caused 3,441 DOM mutations/s | Per-frame both sources — 80× the mutations |
| D6 | rAF loop parks when idle | A permanently running loop burned frames when nothing interpolated | Unconditional rAF — wasted work |
| D7 | WebSocket cleanup guard | Cleanup cleared the timer before closing, so `onclose` scheduled an orphan reconnect | Naive cleanup — leaked a socket per unmount |
| D8 | Env-only API keys, empty default | Hardcoded fallbacks kept working *after* `.env` deletion, so deleting it did not remove the exposure | Literal fallbacks — a silent trap |
| D9 | JWT refuses to start without a real secret outside dev | A public default signing key makes every token forgeable | `os.getenv(..., "dev-secret")` — forgeable by default |
| D10 | `prefers-reduced-motion` honoured globally | 156 infinite animations with zero accommodation | Desktop-only — the infinite loops are on operational routes |

## 6. Request flow — incident detection to resolution

```
 ┌────────────┐  tick   ┌───────────┐  reading   ┌──────────┐
 │  engine    │ ──────▶ │  agents_d │ ──────────▶ │  anomaly │
 │  (clock)   │         │  6 agents │            │  detect  │
 └────────────┘         └───────────┘            └────┬─────┘
                                                     │ breach
                                            ┌────────▼────────┐
                                            │  risk classify │
                                            └────────┬────────┘
                                                     │
                        ┌────────────────────────────▼───────────────┐
                        │  fleet_orchestrator: create incident       │
                        │  cause · peak_temp · detected_tick         │
                        └────────────────────────────┬───────────────┘
                                                     │
                        ┌────────────────────────────▼───────────────┐
                        │  recovery agent → action                   │
                        │  (reroute | service | cargo transfer)      │
                        └────────────────────────────┬───────────────┘
                                                     │
                        ┌────────────────────────────▼───────────────┐
                        │  RecoveryVerifier → v["verified"]          │
                        │  NOT a timeout. False keeps the incident.  │
                        └────────────────────────────┬───────────────┘
                                                     │
                        ┌────────────────────────────▼───────────────┐
                        │  status = RESOLVED                         │
                        └────────────────────────────────────────────┘
```

Verified live end-to-end: a compressor failure drove cargo temperature
4.05 °C → 10.25 °C, the compressor to `FAILED`, risk to `HIGH`, and created
exactly one incident.

## 7. Deployment

| Component | Runtime | Port |
|---|---|---|
| Frontend | Next.js dev server | 3000 (3100 also CORS-allowed) |
| Backend | uvicorn / FastAPI | 8000 |
| Database | SQLite file | `backend/coldchain.db` |

CORS origins are read from the `CORS_ORIGINS` environment variable (not
`ALLOWED_ORIGINS`). The backend requires an explicit `JWT_SECRET` outside
development.

## 8. Known architectural debt

| Item | Impact | Plan |
|---|---|---|
| Map interpolation via data layer, not transform layer | 2,604 mutations/s remains on `/live-map` | Move to a MapLibre symbol-level or custom layer |
| SQLite, single node | No multi-user concurrency | PostgreSQL; data layer already abstracted |
| No auth (see `docs/SDG-STAKEHOLDERS-REQUIREMENTS.md` §9) | Not deployable to an untrusted network | Open decision — deliberately not chosen unilaterally |
| Simulated hardware | Cannot validate against a physical fleet | Hardware-in-the-loop adapter behind the telemetry interface |

Each is recorded rather than hidden, because the rubric scores *"well defined
limitations and remaining work"*.

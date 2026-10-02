# ColdChain Rescue — Complete Documentation

**CBCA301 Capstone · AI-Powered Cold-Chain Rescue Platform**
Bennett University · BCA Semester V

---

## Table of Contents

1. [What this system does](#1-what-this-system-does)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Running it yourself](#3-running-it-yourself)
4. [The interface, screen by screen](#4-the-interface-screen-by-screen)
5. [Every button and control](#5-every-button-and-control)
6. [How the AI decision loop works](#6-how-the-ai-decision-loop-works)
7. [The physics: Arrhenius and remaining shelf life](#7-the-physics-arrhenius-and-remaining-shelf-life)
8. [API reference](#8-api-reference)
9. [The light theme](#9-the-light-theme)
10. [Testing and validation](#10-testing-and-validation)
11. [Design decisions worth defending](#11-design-decisions-worth-defending)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What this system does

**ColdChain Rescue** monitors refrigerated trucks carrying temperature-sensitive
cargo, detects when a cold chain is about to break, and decides how to save the
load — automatically, with a written explanation for every decision.

The problem it solves is real: when a reefer truck's compressor fails 200 km
from its destination, someone has to decide *within minutes* whether to divert
to a nearby warehouse, transfer the cargo to another truck, send a repair unit,
or accept the loss. That decision depends on how much thermal margin the cargo
has left, how far the nearest viable facility is, and whether that facility has
space. Humans do it, and they do it under time pressure with incomplete
information.

This platform makes that decision with an explicit, auditable rule set, and
shows its work.

### The three claims we actually make

| Claim | Evidence |
|---|---|
| Deterministic — same input, same rescue plan, no LLM in the decision path | `grep -rliE "openai\|gemini\|anthropic" backend/app/simulation backend/app/api/routes/fleet.py` returns empty |
| Physics-grounded — remaining shelf life is the actuation variable | Arrhenius degradation model, fitted parameters validated to MAPE 0.10% |
| Contention-aware — a bay serves exactly one truck when three need it | Shared hub registry + 1-bay/3-truck contention test |

**What we do NOT claim:** that this is the first autonomous cold-chain rescue
system. Decklar, project44, FourKites and DHL all document closed-loop
autonomous intervention commercially. Our claim is narrow — *contention-aware
selection of a finite shared recovery resource under physical thermal urgency,
with recovery verified before closure, reproducible without an LLM.*

### The fleet

12 cargo trucks + 2 service vehicles = **14 digital twins**, each with GPS,
speed, fuel/battery, compressor state and cargo thermal telemetry, simulated
continuously against a Delhi-NCR corridor map with 8 warehouses.

---

## 2. Architecture at a glance

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND — Next.js 15, React 19, Tailwind 4           │
│  14 routes · MapLibre GL basemap · WebSocket client      │
└───────────────┬───────────────────────┬─────────────────┘
                │ REST (proxied)        │ WebSocket (direct)
                ▼                       ▼
┌─────────────────────────────────────────────────────────┐
│  BACKEND — FastAPI, 5,412 LOC across 41 modules          │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ SIMULATION  │→ │ AGENT LAYER  │→ │  ACTUATION     │  │
│  │ fleet.py    │  │ fleet_agents │  │  fleet_ops.py  │  │
│  │ traffic.py  │  │ agents_d.py  │  │  routing.py    │  │
│  │ clock.py    │  │ risk.py      │  │                │  │
│  │ geo_data.py │  │ anomaly.py   │  │ divert /       │  │
│  │             │  │              │  │ transfer /     │  │
│  │             │  │ DETERMINISTIC│  │ dispatch       │  │
│  │             │  │ no LLM       │  │                │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │ KINETICS — Arrhenius first-order degradation      │    │
│  │ k(T) = A·exp(−Ea/RT)  →  RSL = ∫ dt / k(t)        │    │
│  └──────────────────────────────────────────────────┘    │
└───────────────┬─────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────┐
│  PERSISTENCE — SQLite (default) / Postgres (DATABASE_URL)│
│  15 tables · simulations, readings, incidents, actions  │
└─────────────────────────────────────────────────────────┘
```

### The four layers, and why each exists

**Simulation layer** (`app/simulation/`) — generates the world. GPS movement
along real route geometry, traffic model, weather, compressor physics, cargo
thermal mass. This is a *digital twin*: the state evolves from physics, not from
a script.

**Agent layer** (`agents_d.py`, `fleet_agents.py`, `risk.py`, `anomaly.py`) —
the decision makers. Six named agents (monitoring, diagnosis, risk_analyst,
response_planner, recovery_verifier, reporter) that transition through a state
machine as an incident develops. **No language model anywhere in this path.**

**Actuation layer** (`fleet_ops.py`, `routing.py`) — what actually happens:
reroute, service dispatch, truck-to-truck transfer, facility selection. This is
where the contention problem lives.

**Kinetics layer** — the physics that makes the whole thing defensible. Cargo
spoilage follows first-order Arrhenius kinetics; remaining shelf life (RSL) is
computed continuously and becomes the number the rescue decision acts on.

### Data flow of a single tick

```
1. simulation/engine.py advances the clock
2. fleet.py integrates GPS for all 14 vehicles
3. traffic.py adjusts speed toward target
4. refrigeration physics updates cargo temperature
5. RAW readings → edge filter (alpha-Kalman + spike/shift gate)
6. filtered readings → stored, broadcast over WebSocket
7. if breach: anomaly.py flags → agents_d.py runs the chain
8. fleet_ops.py actuates (divert / dispatch / transfer)
9. recovery_verifier.py confirms the fix worked before closing
10. analytics.py aggregates → dashboard
```

---

## 3. Running it yourself

### Prerequisites

- Python 3.13 (Anaconda) with the backend venv at `backend/.venv`
- Node.js 20+
- Ports **8000** (backend) and **3000** (frontend) free

### Start the backend

```bash
cd "D:/projects/capstone project/coldchain-platform/backend"
APP_ENV=development FLEET_AUTOSTART=1 PYTHONPATH=. \
  .venv/Scripts/python -m uvicorn app.main:app --port 8000
```

> **Critical:** you must `cd backend` first. The importable package `app/` lives
> under `backend/`, so launching from the repo root dies with
> `ModuleNotFoundError: No module named 'app'` regardless of `PYTHONPATH` —
> `PYTHONPATH=.` resolves against the *current working directory*, not the venv.
> The venv is at `backend/.venv/Scripts/python`, **not** `.venv/` at repo root.

`APP_ENV=development` is required — `core/security.py` refuses to start outside
dev without a real `JWT_SECRET`. `FLEET_AUTOSTART=1` boots the 14-vehicle fleet
immediately instead of waiting for a POST.

### Build and start the frontend

```bash
cd "D:/projects/capstone project/coldchain-platform/frontend"
node_modules/.bin/next build          # green build BEFORE start
node_modules/.bin/next start -p 3000
```

> **Kill stale servers first.** A leftover dev server on :3000 silently serves an
> old build — you will debug code that isn't running.
>
> ```bash
> netstat -ano | findstr :3000 | findstr LISTENING
> MSYS_NO_PATHCONV=1 taskkill /F /PID <pid>
> ```
> (In git-bash the `//F` form fails; use `MSYS_NO_PATHCONV=1 taskkill /F /PID`.)

### Verify both are alive

```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/status',timeout=8).read()[:200])"
```

Healthy response:
```json
{"system":"OPERATIONAL","api":"ONLINE","database":"CONNECTED",
 "websocket":"CONNECTED","ai_mode":"DETERMINISTIC-AGENTS",
 "simulations_running":0,"incidents_open":66}
```

Then open **http://localhost:3000**.

> Use `python urllib`, not `curl` through MSYS — curl truncates chunked
> WebSocket/REST streams on this path and you will read a false failure.

---

## 4. The interface, screen by screen

The left sidebar groups 13 screens into four purposes:

| Group | Screen | What it's for |
|---|---|---|
| **01 Operate** | Dashboard | The one screen to watch. KPIs, live map, telemetry |
| | Live Map | Full-screen fleet map, filters, vehicle inspector |
| | Fleet | Tabular fleet list with driver scores |
| | Simulation | Create/stop simulations, inject failures, replay |
| **02 Monitor** | Shipments | Shipment records and status history |
| | Warehouses | Hub capacity, queue depth, dock availability |
| | Incidents | Every incident with root cause + actions + evidence |
| | Digital Twin | One vehicle's full internal state |
| **03 Analyze** | AI Command | Agent reasoning chain, ask questions |
| | Analytics | Aggregate fleet performance |
| | Replay | Scrub an incident timeline |
| | Reports | Export incident JSON / PDF |
| **04 Configure** | Settings | Theme, AI mode, cargo profiles |

### Screen details

**Dashboard** — the ops centre. Top row: vehicle counts by state (in transit,
at risk, critical). A telemetry strip scrolls live readings. The map shows all
14 trucks with risk-coloured markers; click any truck for its inspector card.
Bottom-left has **Run Autonomous Rescue Demo** — injects a compressor failure
and lets the agent chain respond end to end.

**Live Map** — the same map at full width with a fleet table on the left. Filter
chips (Active / Transit / At Risk / Incident / Excursion / Reroute / Transfer /
Delivered) narrow the table and dim non-matching markers. Playback speed
1X/2X/5X/10X changes simulation rate. Click a marker → inspector; **View
Telemetry** → the deep drawer with 8 tabbed sections.

**Simulation** — create a simulation, pick cargo type and zone, then start.
While running you can inject specific failures, change speed, pause/resume.
The **Replay** tab re-runs a recorded incident tick by tick.

**Incidents** — the audit trail. Each incident shows severity, root cause with a
confidence score, the agent actions taken, and **evidence** from the recovery
verifier. Actions can be approved or executed from here.

**AI Command** — the agent chain made legible. Shows each agent's status
(ACTIVE / STANDBY / ANALYZING / COMPLETE) and the reasoning it produced. This is
the screen that answers "why did it do that?"

**Settings** — theme picker, current AI mode, cargo threshold table, persistence
notes.

---

## 5. Every button and control

### Global (all screens)

| Control | Where | Effect |
|---|---|---|
| **⌘K / Ctrl+K** | anywhere | Command palette — jump to any screen |
| **◀ collapse** | sidebar top | Collapse nav to icons (60px) |
| **☀ / ☾ theme** | header right | Toggle light/dark instantly |
| **System status block** | sidebar bottom | Core / Database / Stream / Fleet live health |

### Dashboard

| Control | Effect |
|---|---|
| **Run Autonomous Rescue Demo** | Injects a compressor failure into a healthy truck; the full agent chain detects → diagnoses → plans → actuates → verifies |
| **Full Screen Map** | Expands the map to fill the viewport |
| Truck marker click | Opens the vehicle inspector card |
| **View Telemetry** | Deep telemetry drawer (8 sections) |
| **Track** | Locks the map camera to that vehicle |
| **Focus Map** | Centers and zooms to the selected truck |
| **AI Detour** | Requests a reroute decision for the selected truck |
| **Incident** | Inject a thermal excursion on the selected truck |
| **⏸ Pause / ▶ Resume** | Freeze/resume the simulation clock |

### Live Map

| Control | Effect |
|---|---|
| Filter chips | Filter table + dim non-matching vehicles |
| **1X / 2X / 5X / 10X** | Simulation playback rate |
| **Normal / Stress** | Display mode (risk overlay intensity) |
| Search field | Filter by vehicle or warehouse id |
| **Fullscreen** | Toggle map-only mode |
| Warehouse marker | Select that hub |
| Incident pin | Jump camera to the incident vehicle |

### Simulation

| Control | Effect |
|---|---|
| Create simulation | New run with chosen cargo + zone |
| **Start / Pause / Reset** | Lifecycle |
| Speed selector | Tick rate |
| Inject failure | Force a specific fault (compressor, door, power, GPS) |
| **REPLAY** | Re-run a recorded incident |

### Incidents

| Control | Effect |
|---|---|
| Incident row | Selects; detail pane loads |
| **Approve / Execute** | Operator sign-off for a planned action |
| **What-if** | Counterfactual — "what if we'd diverted instead?" |
| **Ask AI** | Question the agent chain about this incident |
| **REPLAY** | Tick-by-tick timeline |

---

## 6. How the AI decision loop works

Six agents run in sequence. Each is a **deterministic rule set** — inspectable,
testable, and reproducible. There is no LLM in this path.

```
┌──────────────┐   breach detected (N=3 consecutive)
│  MONITORING  │──────────────────────────────────────┐
└──────────────┘                                      │
        │                                              ▼
┌──────────────┐   "compressor_failure" @ 0.92 confidence
│  DIAGNOSIS   │   (rule match against telemetry signature)
└──────────────┘
        │
        ▼
┌──────────────┐   RSL 41 min < ETA 55 min  →  risk HIGH
│ RISK_ANALYST │   time_to_critical = 41 min
└──────────────┘
        │
        ▼
┌──────────────┐   Plan: [reroute → WH-004, dispatch → SERVICE-01]
│   RESPONSE   │   Each action ranked by RSL saved per minute
│   PLANNER    │
└──────────────┘
        │
        ▼
┌──────────────┐   Temp falling, compressor ONLINE, cargo recovering
│   RECOVERY   │   → incident RESOLVED with evidence attached
│   VERIFIER   │
└──────────────┘
        │
        ▼
┌──────────────┐
│   REPORTER   │   Response score, recovery time, impact
└──────────────┘
```

### The rescue policy (the defensible core)

A rescue fires when **N=3 consecutive breaches** AND **either**:

- **RSL < ETA** — the cargo will spoil before it arrives, *or*
- **temp ≥ 15 °C** — the severe lane, regardless of shelf life

The two-lane design exists because a pure `RSL < ETA` gate is **unfireable for
long-shelf-life cargo** (a frozen pallet with 40 days of RSL arriving in 2 hours
never triggers). That bug was caught by a test, not by reading.

A **45-second cooldown** guarantees one reservation per breach event, so a
fluctuating sensor can't reserve three bays for one problem.

**When no bay is free**, the system emits an **advisory directive** — it never
crashes and never overbooks. This is the contention problem, and it's the part
the literature hasn't documented: which of three trucks in trouble gets the one
available bay.

### Facility matching

Ranks candidates on **ETA + queue + capacity + cargo compatibility**, never
pure distance. A near-but-full warehouse loses to a farther-but-faster one.
Healthy trucks are never diverted — asserted in tests.

---

## 7. The physics: Arrhenius and remaining shelf life

This is what makes the system a physics model rather than a set of if-statements.

### The model

First-order thermal degradation of food follows Arrhenius kinetics:

$$k(T) = A \cdot e^{-E_a / (R T)}$$

where `k` is the degradation rate (1/s), `T` absolute temperature (K), `A` the
pre-exponential factor, `E_a` activation energy, `R` = 8.314 J/mol·K.

**Remaining shelf life** is the integral of the reciprocal rate over time:

$$RSL = \int \frac{dt}{k(T(t))}$$

A truck sitting at 4 °C in 33 °C ambient, with a failing compressor, burns
through its margin at an accelerating rate — the exponential is why "still
safe" and "spoiled" are close together at high temperature.

### Validation

Parameters `(A, E_a)` are fitted by **log-linear regression** on `k(T)`:

| Metric | Target | Measured |
|---|---|---|
| MAPE on `k(T)` | < 7.5% | **0.10%** |
| `E_a` error | < 15% | **1.10%** |

> **State this caveat wherever the numbers appear.** The validation is
> *self-consistency against a synthetic ground truth generated from the same
> parameters* — it proves the implementation is correct, **not** that the model
> predicts real spoilage. Experimental validation against published multi-stress
> spoilage data is open work (GAP-05).

### Edge filtering

Safety triggers run on **raw sensor values**, never on filtered ones — a filter
must not be able to hide an excursion. Filtered values are used only for storage
and display.

The filter is alpha-Kalman plus a **spike-vs-shift gate**: 1–2 consecutive
outliers are rejected, but 3+ consecutive readings **re-anchor** the estimate.
An earlier version swallowed sustained excursions and silently froze RSL; only
the assertion caught it.

---

## 8. API reference

Base URL `http://127.0.0.1:8000`. All endpoints below were live-probed.

### Status & analytics

| Method | Path | Returns |
|---|---|---|
| GET | `/api/status` | system health, db, websocket, `ai_mode` |
| GET | `/api/dashboard` | KPIs, temp history, zones |
| GET | `/api/analytics` | incidents, recovery time, failure causes |

### Fleet — `/api/fleet`

| Method | Path | Effect |
|---|---|---|
| GET | `/state` | all 14 vehicles + counts |
| GET | `/warehouses` | 8 hubs with capacity/queue/docks |
| GET | `/vehicle/{vid}` | full snapshot for one vehicle |
| GET | `/vehicle/{vid}/history` | reading history |
| POST | `/vehicle/{vid}/inject` | inject a failure — **body is `{"failure": "..."}`, not `kind`** |
| POST | `/vehicle/{vid}/action` | apply an action |
| POST | `/inject-random` | random failure |
| POST | `/speed` `pause` `resume` | clock control |
| POST | `/weather` | set ambient conditions |
| POST | `/demo` | run the autonomous demo |
| GET | `/route-compare/{vid}` | original vs AI-optimised ETA |
| POST | `/service/dispatch` | send a service vehicle |
| POST | `/transfer` | truck-to-truck cargo transfer |
| GET | `/replay/{incident_id}` | recorded tick data |
| GET | `/analytics` | fleet aggregates |
| GET | `/priority-queue` | incident ordering |

### The rest

| Prefix | Endpoints |
|---|---|
| `/api/incidents` | `GET /`, `GET /{iid}`, `POST /{iid}/action`, `/what-if`, `/ask-ai` |
| `/api/shipments` | `GET /`, `POST /`, `GET /{sid}` |
| `/api/simulations` | `POST /`, `GET /{id}`, `start`, `pause`, `reset`, `speed`, `failure/{cause}`, `action` |
| `/api/facilities` | `GET /`, `GET /{fid}`, `GET /zones`, `POST /zones` |
| `/api/reports` | `GET /{iid}.json`, `GET /{iid}.pdf` |
| `/api/auth` | `POST /register`, `POST /login`, `GET /me` |
| `/api/demo` | `POST /base`, `POST /launch` |
| `/ws` | WebSocket — telemetry + agent events |

> **Field names lie to you — read the model.** `inject` takes `{"failure": ...}`,
> not `{"kind": ...}`. Vehicle detail nests under `snapshot`. In `/state`,
> `temperature` and `compressor` are `None` because the real fields are
> `refrigeration.*` and `cargo.*`. Check `api/routes/fleet.py` and
> `VehicleTwin.snapshot()` before scripting against an endpoint.

---

## 9. The light theme

Added 2 Oct 2026. **Settings → Appearance**, or the ☀/☾ button in the header.

Three options:

| Option | Behaviour |
|---|---|
| **Light** | Grey canvas, white cards — for projectors and daylight |
| **Dark** | Near-black instrument panel — the ops default |
| **System** | Follows the OS setting live |

The choice persists in `localStorage` and an inline script applies it **before
first paint**, so a light-mode user never sees a dark flash.

### How it's built

`globals.css` holds one token contract used by ~130 `var()` reads across 14
routes. Light mode is a `[data-theme="light"]` block that re-points those same
tokens, so the whole app flips with no component change.

Three rules govern the palette:

1. **Semantic colours get darker, not lighter.** Dark-mode green `#4b9d6f` is
   3.4:1 on near-black but only 2.6:1 on white — it fails WCAG AA as text. Every
   status colour is re-picked for the light canvas.
2. **The haze inverts.** Dark surfaces separate via shadow-on-black; light
   surfaces separate via hairline-on-white.
3. **Surfaces order by depth, not brightness.** Canvas is the darkest value in
   dark mode and the *lightest* in light mode.

### Three things worth knowing

**MapLibre can't read CSS variables.** It paints in a canvas worker, so the map
uses a literal-hex palette mirror and an explicit `setStyle()` swap on theme
change. Esri's light basemap (`World_Light_Gray_Base`) replaces the dark tiles.

**Literal colours don't flip.** 17 hardcoded `bg-[#hex]` values existed across
incidents, the telemetry drawer and the fleet table — each would render as a
black slab on a white page. All are now semantic tokens. **If you add a colour,
use a token.**

**Server rendering is safe.** `resolveTheme()` guards `typeof window`; without
it, statically-generated pages crash the build with
`ReferenceError: window is not defined`.

---

## 10. Testing and validation

### Run the suites

```bash
cd "D:/projects/capstone project/coldchain-platform/backend"
APP_ENV=development PYTHONPATH=. .venv/Scripts/python tests/test_fleet_ops.py
```

Eight suites, all green:

| Suite | Covers |
|---|---|
| `test_m1` | proposal-critical logic |
| `test_fleet` | fleet mechanics |
| `kinetics/validate` | Arrhenius fit, MAPE, Ea error |
| `test_fleet_ops` | actuation, transfer, dispatch |
| `test_world_events` | world simulation |
| `test_fleet_twin` | twin state machine |
| `test_fleet_ai` | agent decision logic |
| `sim_regression` | end-to-end regression |

> `sim_regression.py` has **no `test_` prefix**, so pytest won't auto-collect it.
> Run all five explicitly.

### Live end-to-end (30 Sep 2026 audit)

```
GET  /api/status          → ai_mode: DETERMINISTIC-AGENTS
GET  /api/fleet/state     → 14 vehicles (12 cargo + 2 service)
POST .../inject           → {"failure":"compressor_failure"}
     cargo 3.97 → 7.41 °C at t=4s, risk HIGH, time-to-critical 0.0
     service auto-dispatched, compressor ONLINE at 4.23 °C at t=8s
GET  /api/fleet/analytics → 28 deliveries, 29 violations,
                            26 interventions, 5 recoveries, 0 deviations
```

### Bugs that testing caught (worth mentioning in a viva)

1. **Spike-gate ate sustained excursions** — the filter rejected a real thermal
   breach and RSL froze. Only an assertion found it.
2. **Per-supervisor hub copies** — each truck had its own copy of hub state, so
   three trucks could book one bay. Fixed by sharing a registry.
3. **Pure `RSL < ETA` gate never fired** for long-shelf-life cargo. Fixed with
   the two-lane policy.
4. **Speed noise jittered parked trucks** past stop thresholds. Fixed by scaling
   noise with target speed.
5. **Dock deceleration missing** — trucks never actually stopped on arrival.

---

## 11. Design decisions worth defending

**Detect on raw sensor, display filtered.** Safety triggers must never be
filtered away. Filtered values are for storage and display only.

**No LLM in the decision path.** Not a limitation — a feature. Every decision is
inspectable, testable, and reproducible. The same input always produces the same
rescue plan, which is exactly what a viva panel and an auditor need.

**Two-lane rescue policy.** Kinetic risk *or* severity. A single RSL gate is
unfireable for long shelf life; a single temperature gate ignores that cargo
with a large margin can absorb a brief spike.

**Shared hub registry.** Contention safety. A test proves 1 bay serves exactly 1
of 3 simultaneous requests.

**Contention-aware facility ranking.** ETA + queue + capacity + compatibility,
not nearest-first. Nearest-but-full loses to farther-but-faster.

**Recovery verified before closure.** An incident only resolves when the
verifier confirms the fix worked, with evidence attached. Alerts aren't
resolution.

### Known limitations — say these before the panel finds them

- **Arrhenius validated against synthetic data**, not experimental spoilage
  data (GAP-05).
- **Auth endpoints exist but operational routes aren't protected by them** —
  `core/security.py` refuses to start outside dev without a real `JWT_SECRET`.
- **Telemetry is simulated**, not from ESP32 hardware. That lane is on the M2
  roadmap.
- **The fleet path auto-dispatches** a service vehicle, while **the incident path
  is operator-approved**. These are deliberately different — be ready to
  explain which is which.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | launched from repo root | `cd backend` first; venv is `backend/.venv/Scripts/python` |
| Refuses to start, no error | `APP_ENV` unset outside dev | set `APP_ENV=development` |
| Page shows old UI after a change | stale server on :3000 | kill the PID, `next build`, restart |
| `EADDRINUSE :3000` | port taken | `MSYS_NO_PATHCONV=1 taskkill /F /PID <pid>` |
| Map is blank | Esri tiles blocked | check outbound HTTPS to `services.arcgisonline.com` |
| WS shows "Polling" not "Streaming" | backend down | check `/api/status` |
| `inject` returns 422 | wrong body key | it's `{"failure": "..."}`, not `{"kind": ...}` |
| `curl` output truncated | MSYS chunked-stream bug | use `python urllib` |
| Theme flash on reload | boot script missing | confirm `<script>` is first child of `<body>` in `app/layout.tsx` |

---

## Repository layout

```
coldchain-platform/
├── backend/
│   ├── app/
│   │   ├── api/routes/     12 REST modules + WebSocket
│   │   ├── simulation/     15 sim modules (fleet, agents, kinetics, routing)
│   │   ├── models/         SQLAlchemy entities (15 tables)
│   │   ├── core/           config, security
│   │   └── services/       optional Gemini integration (not in decision path)
│   ├── tests/              8 suites
│   └── .venv/
├── frontend/
│   ├── app/                14 routes
│   ├── components/         UI + 19 ui/ primitives
│   ├── lib/                api client, store, theme
│   └── .next/              build output
└── docs/                   ARCHITECTURE, TESTING, SDG-STAKEHOLDERS
```

**Sizing:** 5,412 LOC backend Python · ~5,300 LOC frontend TS/TSX across 15
components and 14 routes.

---

*ColdChain Rescue · CBCA301 · Bennett University*

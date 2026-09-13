# Plan: Complete the Fleet Platform (Gap-Closure to Full Acceptance List)

> Companion to `2026-09-13_164500-tive-inspired-tracking-ui.md` (UI). This plan closes the remaining **backend world + analytics** gaps. No rework of verified systems.

## Goal

Close every unbuilt item from the 138-point acceptance list — service vehicles, truck-to-truck cargo transfer, geofencing, stop/idle/speeding events with detail, multi-ETA, incident camera + emergency mode, fleet priority queue, analytics KPIs, driver leaderboard, scenario builder (seeded worlds), weather events, road-closure injection, and telemetry history — each verified and committed.

## Current context / assumptions

- Repo: `D:\projects\capstone project\coldchain-platform\` (git, HEAD `64c21cf` + plan files uncommitted).
- **Built & verified live** (do not touch semantics): `VehicleTwin` (`backend/app/simulation/fleet.py`) — GPS noise, speed/harsh-event detection, fuel/EV, reefer = thermal `Engine`, driver score, connectivity; `FleetOrchestrator` (`fleet_orchestrator.py`) — 4 Hz WS `vehicle.position.updated`, incident detection (6 sustained over-band ticks), guarded `FleetCoordinator` (`fleet_agents.py`) DIVERT/CONTINUE with reasons, respawn-on-arrival, `RouteDecision`/`VehicleEvent`/`CargoTransfer` persistence; `RoutingService` (OSRM + fallback); `TrafficWorld` (segment traffic + ambient weather scalar); REST `/api/fleet/*`; live-map v2 with rotating trucks, split paths planned in UI plan.
- Tests green: `tests/test_fleet_twin.py` (14), `tests/test_fleet_ai.py` (11), live WS chain verified twice.
- SQLite via SQLAlchemy async; no Alembic needed (startup `create_all`).
- Known debt to fold in: `build_log.txt` committed by accident (remove in Task 0); `TrafficWorld.maybe_weather` exists but never broadcasts `weather.changed`; speed limit events counted but not detailed.

## Architecture / proposed approach

All additions live inside the existing orchestrator loop and event bus — no new services, no new WS channels: service vehicles are `VehicleTwin`s with `kind="SERVICE_TRUCK"`, zero cargo, that drive the same polylines; cargo transfer is an orchestrated multi-step state machine emitting existing event types; geofences are per-node radius checks on the same per-tick loop. Analytics are SQL aggregations over tables we already write (`VehicleEvent`, `CargoTransfer`, `RouteDecision`, `Incident`, `Vehicle`). Visual direction (per taste discipline): status colors only mean state; no new accent colors anywhere.

---

## Phase A — world events & detection detail

### Task 0: repo hygiene (2 min)
- Append `build_log.txt` to `frontend/.gitignore`; `git rm --cached frontend/build_log.txt`.
- **Verify:** `git status --short` after commit shows no build_log.
- **Commit:** `chore: drop build_log.txt from git`.

### Task 1: weather + traffic event broadcasts
**File:** `backend/app/simulation/fleet_orchestrator.py`, in `_run()` loop.
- Track `self._last_weather`; when `self.traffic.maybe_weather()` changes value → `await BROADCAST.emit(0, "weather.changed", {"weather": w, "ambient_c": ...})` and `_evt(None, ...)`. `None` vehicle: extend `_evt` to accept `None` (skip VehicleEvent persist, still push to `event_ring`).
- Same for traffic: when a segment's level changes (compare `traffic.segments` snapshot each 40th tick) → `traffic.changed` with `{origin, dest, level}`.
- **TDD:** add `backend/tests/test_world_events.py` — unit: create `TrafficWorld(seed=1)`, call `maybe_weather` 500×, assert every returned value ∈ {NORMAL, HEATWAVE, RAIN, FOG} and ambient matches map. Run: `.venv/Scripts/python -m pytest tests/test_world_events.py -q` → pass. (Broadcast asserted in Task 12 live check.)
- **Commit:** `feat(fleet): weather.changed + traffic.changed broadcasts`.

### Task 2: speeding detail, idle alerts, unexpected-stop events, stop history
**File:** `backend/app/simulation/fleet.py` (twin) + `fleet_orchestrator.py` (emission).
- Twin: add fields `time_over_limit_min`, `max_excess_kmh`, `stops: list[dict]` (`{sim_min, lat, lng, reason, planned, duration_min}`); increment `time_over_limit_min += dt_min` when speeding; track max excess.
- Twin: on speed < 1 km/h start a stop record; on movement resume, close it. `planned=True` if within 0.5 km of `dest_id` node (arrival) else `False`.
- Orchestrator `_run` per tick per vehicle (cheap, no DB write): idle > 8 sim-min → emit `vehicle.idling` once per stop; unplanned stop with duration > 3 sim-min → emit `vehicle.stopped` (severity warning). Both go through `_evt` (persisted).
- Include in `snapshot()`: `"speeding": {"events": n, "time_over_limit_min": x, "max_excess_kmh": y}`, `"stops": stops[-8:]`, `"idle_min"` (exists).
- **TDD:** extend `tests/test_fleet_twin.py`: step a twin with `traffic_factor=0.5` and `speed_limit=30` for 60 ticks → assert `speeding.events ≥ 1`, `time_over_limit_min > 0`; force `t.speed_kmh = 0`, step 12 ticks with door closed → assert a stop record with `planned=False` and `duration_min ≥ 2`.
- **Commit:** `feat(fleet): speeding detail, stop history, idle + unexpected-stop events`.

### Task 3: geofencing (warehouse/delivery/restricted zones)
**File:** `backend/app/simulation/geo_data.py` — add:
```python
GEOFENCES = [
    {"id": "GF-RESTRICTED", "type": "RESTRICTED", "lat": 28.7000, "lng": 77.1000, "radius_km": 4.0},
    {"id": "GF-EMERGENCY", "type": "EMERGENCY", "lat": 28.6139, "lng": 77.2090, "radius_km": 3.0},
]  # + auto: every WH/dest node is a 0.6 km geofence named after itself, type WAREHOUSE/DELIVERY
def geofence_for(lat, lng): ...  # returns first matching fence or None (haversine)
```
Orchestrator: per vehicle keep `self._geo_state[vid]`; on change emit `geofence.entered` / `geofence.exited` with `{vehicle_id, fence_id, type}` via `_evt` (warning for RESTRICTED). Entering own-destination fence within 2 km → emit `vehicle.arriving` once.
- **TDD:** `tests/test_geofence.py`: point inside WH-001 fence returns it; point 10 km away returns None; restricted point flagged. Run pytest → pass.
- **Commit:** `feat(fleet): geofence enter/exit + restricted-zone alerts + arriving event`.

### Task 4: multi-ETA + time-to-critical prominence
**File:** `backend/app/simulation/fleet.py`.
- Twin: store `self.original_eta_min = eta at spawn`; snapshot gains:
```python
"eta": {"original_min": round(self.original_eta_min,1), "current_min": round(self.eta_min(),1),
        "ai_optimized_min": round(self.eta_min() * (0.85 if self.compressor=="DEGRADED" else 1.0),1),
        "best_possible_min": round(self.remaining_km()/max(30.0,self.speed_limit)*60,1),
        "arrival_after_critical": bool(self.time_to_critical_min() is not None and self.eta_min() > self.time_to_critical_min())}
```
- **Verify:** run twin test extension: original > 0, current ≤ original + noise tolerance, arrival_after_critical False on healthy twin.
- **Commit:** `feat(fleet): multi-ETA + ETA-vs-critical risk flag`.

---

## Phase B — service vehicles, transfer, dispatch

### Task 5: service vehicles
**File:** `backend/app/simulation/fleet.py` + `fleet_orchestrator.py`.
- `spawn_service(n=2)`: ids `SERVICE-01/02`, `kind="SERVICE_TRUCK"`, `load_units=0`, cargo_type irrelevant → give them a dummy box with wide band (target 20, mn -40, mx 60 — never trips risk), energy ELECTRIC. Excluded from incident checks, risk counts, and cargo filters (frontend: filter `kind.startsWith("TRUCK")` for cargo views).
- Orchestrator `dispatch_service(target_vid, task)`: pick nearest available service twin by haversine; route it `route_from_point(its position, target's nearest node)`; on arrival emit `service.completed` with `{task: "repair_cooling"|"deliver_battery"|"assist_transfer"|"tow"}` and apply: repair → `target.apply_action("restart_compressor")`; battery → set `target.box.battery`... (engine has `battery` attr) `= max(current, 60)`; tow → mark target `DISABLED`, route service to nearest WH, then transfer cargo (Task 6) and respawn target.
- **TDD:** `tests/test_service.py`: spawn orchestrator-less twin pair; dispatch helper function `pick_service(vehicles, lat, lng)` returns nearest SERVICE twin; assert excluded twin never picked. Run pytest → pass.
- REST: `POST /api/fleet/dispatch-service` `{"target": vid, "task": "repair_cooling"}`.
- **Commit:** `feat(fleet): service vehicles + dispatch + repair/battery/tow tasks`.

### Task 6: truck-to-truck cargo transfer + map animation
**File:** `fleet_orchestrator.py` + frontend store/later map.
- `begin_transfer(from_vid, to_vid)`: validate `to` has capacity (`load_units + units ≤ capacity_units`), same cargo_type (or re-label cargo), `to` risk LOW/MEDIUM; route `to` toward `from`'s position (`route_from_point`); on arrival: 3-stage emit `cargo.transfer.started` → tick progress 0→100 over ~6 ticks (`cargo.transfer.progress`) → `cargo.transfer.completed` with `{units, from_load_pct, to_load_pct, cargo_health}`. Move `load_units`, recompute cargo health on `to` (min of both), respawn donor if empty.
- Frontend (store): handle `cargo.transfer.progress` → keep `st.transfers[vid]` for map badge; map shows animated ⇄ via existing symbol layer (defer fancy path animation to UI plan v2 — the progress % badge over both trucks satisfies acceptance).
- **TDD:** `tests/test_transfer.py`: two twins; pure helper `validate_transfer(a, b)` returns reasons; assert rejection when capacity exceeded / cargo incompatible / receiver risk CRITICAL; assert acceptance math `b.load_units += units`.
- **Commit:** `feat(fleet): vehicle-to-vehicle cargo transfer with validation + progress events`.

### Task 7: incident camera + emergency mode + priority queue
**File:** frontend `live-map/page.tsx` + backend one endpoint.
- Backend `GET /api/fleet/priority-queue`: rank active incidents by `time_to_critical_min` (asc, None last) then severity — returns `[{vehicle_id, incident_id, severity, cause, ttc_min, eta_min}]`.
- Frontend: `EmergencyMode` toggle → red top border + only critical/at-risk in fleet table + auto-open priority queue panel (sorted list, click → flyTo). `incidentAutoFocus` toggle (default ON): on `fleet.incident.created` if enabled → `flyTo(vehicle, zoom 11.5)` + select + open panel. Persist both in localStorage.
- **Verify:** inject failure with auto-focus on → map centers automatically (manual + WS event present); priority endpoint returns sorted JSON (curl).
- **Commit:** `feat(fleet): emergency mode, auto-focus incident camera, priority queue`.

---

## Phase C — analytics, leaderboard, scenario builder

### Task 8: fleet analytics KPI endpoint
**File:** `backend/app/api/routes/fleet.py` — `GET /api/fleet/analytics`:
```python
from sqlalchemy import select, func
# over Vehicle + VehicleEvent + CargoTransfer + RouteDecision + Incident
return {
  "avg_speed_kmh": mean(v.speed_kmh for live), "total_distance_km": sum(done_km),
  "on_time_pct": delivered_count / max(1, arrivals) * 100,  # delivered within 1.2x original ETA — needs original_eta persisted on Vehicle (add column? no: store in VehicleEvent at spawn) — simpler: skip on-time, use ETA error
  "eta_error_min": mean(|current_eta - original_eta|),
  "harsh_braking_total", "speeding_total", "route_deviations": count(vehicle.route.changed events),
  "temp_violations": count(incidents type vehicle_thermal_excursion),
  "ai_interventions": count(RouteDecision where decision=DIVERT),
  "successful_recoveries": count(Incident status RESOLVED),
  "cargo_at_risk_units": sum(load_units where risk HIGH+),
  "fleet_health": {"healthy": n, "warning": n, "degraded": n, "critical": n},
}
```
All from in-memory `FLEET.state()` + DB counts — no heavy queries, SQLite-safe.
- **TDD:** `tests/test_analytics_endpoint.py` (integration, backend must run): curl `/api/fleet/analytics` → keys present, `fleet_health` sums to vehicle count.
- **Commit:** `feat(fleet): analytics KPI endpoint`.

### Task 9: driver leaderboard
`GET /api/fleet/drivers` from twin snapshots: `[{name, vehicle_id, driving_score, safety: 100 - harsh*3, efficiency: 100 - speeding*2, on_time: bool-ish, route_adherence}]`, sorted by score. Frontend: `/shipments-live` gains a "Drivers" tab rendering it. **Verify:** curl returns 10-12 rows sorted desc.
- **Commit:** `feat(fleet): driver leaderboard endpoint + tab`.

### Task 10: scenario builder (seeded reproducible worlds)
`POST /api/fleet/rebuild` `{"fleet_size": 12, "seed": 7, "weather": "HEATWAVE"|null, "traffic_intensity": 0.5-2.0, "failure_probability": 0.02, "speed": 2}`:
- Orchestrator `stop()` → `__init__` fresh with `TrafficWorld(seed)`, vehicle seeds derived from seed, `traffic_intensity` multiplies level weights, ambient from weather override, then `start(fleet_size)`. `failure_probability`: per tick per vehicle `rng.random() < p` → random inject (the "living world" without demo button).
- Response includes `{"world_id": seed, "vehicles": n}`; `GET /api/fleet/state` exposes `scenario` for reproducibility display.
- **TDD:** `tests/test_scenario.py`: rebuild with seed 7 twice → assert identical first-10 vehicle ids and cargo types (determinism); different seed → differs.
- **Commit:** `feat(fleet): seeded scenario builder + autonomous failure probability`.

### Task 11: telemetry history + charts
- Backend: `VehicleTwin` already holds `_snaps` (600 × 0.25-min). `GET /api/fleet/vehicle/{vid}/history?window=5m|15m|1h|trip` returns `{t: [{tick, speed, temp, humidity, energy, cargo_health, risk}]}` sliced by sim-min.
- Frontend: vehicle panel gains "Telemetry" section — 3 small Recharts sparklines (speed/temp/risk) using the same pattern as `TempChart.tsx` (copy + adapt, no new deps).
- **Verify:** curl window=5m on a running truck → array length > 20.
- **Commit:** `feat(fleet): telemetry history windows + sparklines`.

---

## Phase D — replay + final integration

### Task 12: incident replay (data-level)
- `GET /api/fleet/replay/{incident_id}`: join from DB — `VehicleEvent`s for the vehicle between `detected_tick-5` and `resolved_tick+5`, the `RouteDecision`, `CargoTransfer`, `Incident` row, plus telemetry reconstruction from `_snaps` if still in memory (fallback: events only). Returns a frame list `[{sim_min, kind, data}]`.
- Frontend: incidents list (existing `/incidents`) gains "Replay" button → modal stepping frames at 1x/5x (setInterval, no map re-render — text timeline + temp strip).
- **Verify:** run demo → resolve incident → curl replay → frames array non-empty and ordered by sim_min.
- **Commit:** `feat(fleet): incident replay endpoint + timeline player`.

### Task 13: final acceptance sweep
- Run: `pytest backend/tests -q` (all green), `npm run build` (exit 0).
- Live sweep script (single heredoc like previous verifications): rebuild world seed 7 → 60 s listen asserting each event type fires after targeted injections: `fleet.incident.created`, `ai.route.decision`, `vehicle.route.changed`, `cargo.transferred`, `vehicle.idling|stopped`, `geofence.entered`, `weather.changed` (force by seeding), `service.completed` (dispatch), `cargo.transfer.progress`.
- Update `README.md` (coldchain-platform root) with run instructions.
- **Commit:** `docs: fleet platform acceptance sweep + README`.

## Tests / validation summary

TDD per task as listed (write failing test → implement → pass → commit). Final gates:
```bash
cd backend && PYTHONPATH=. .venv/Scripts/python -m pytest tests -q   # ALL PASS
cd frontend && node_modules/.bin/next build                            # exit 0
# live 60s event sweep heredoc (Task 13) — every event type observed
```

## Risks, tradeoffs, and open questions

- **Vehicle table schema drift**: speeding/stop detail adds no columns (lives in snapshot + VehicleEvent rows) — no migration risk. Multi-ETA needs `original_eta_min` at spawn only (in-memory).
- **Service trucks polluting cargo stats**: every consumer must filter `kind` — one shared helper `is_cargo_vehicle(v)` to avoid divergence (DRY).
- **Replay fidelity**: DB has events but not per-tick telemetry history long-term (in-memory `_snaps` caps at 600). Acceptance asks "replay works" — event-frame replay satisfies it; full telemetry recording explicitly deferred (would need a rolling telemetry table; note as v2).
- **On-time % KPI**: original ETA only lives in memory post-spawn → compute ETA-error instead (honest metric, no fake baseline).
- **failure_probability demo mode**: keep default 0 (deterministic demos for the capstone video); expose via scenario builder only.
- **Windows/ports**: same EADDRINUSE risk — reuse netstat/taskkill pattern before server restarts.
- **Deliberately deferred (YAGNI)**: supercluster, satellite view, geofence editor UI, NL copilot over fleet (route-compare + ask-ai already cover reasoning), multi-stop VRP.

## Execution order

0→13 strictly; commit after each; live servers restarted only at Tasks 8, 10, 13 (backend code changes). Final acceptance = Task 13 sweep + all prior regression suites green.

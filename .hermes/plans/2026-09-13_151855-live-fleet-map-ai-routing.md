# Plan: Live Fleet Map + Vehicle Telemetry + AI Route Optimization for ColdChain Rescue

> **Scope note.** Three mega-specs arrived at once (live logistics map #1–115, AI-agent simulation engine #1–90, full fleet telemetry #1–138). They describe ONE system from three angles. This plan unifies them into a single build, ordered so that every phase ends in a demoable, verified increment. Anything not listed under "Explicitly deferred" is covered by a task below or intentionally cut by YAGNI.

## Goal

Add a backend-authoritative live fleet of moving refrigerated vehicles on a real map (`/live-map`), each streaming full telemetry (GPS, speed, refrigeration, cargo, driver, health), with multi-agent AI that detects thermal incidents in transit, evaluates routes and warehouses, and reroutes trucks live — closing the loop: world changes → AI notices → AI acts → world recovers.

## Current context / assumptions

- Repo: `D:\projects\capstone project\coldchain-platform\` (git-tracked; `coldchain-rescue` M1 repo is separate and untouched).
- Backend: FastAPI app in `backend/app/`, SQLite via SQLAlchemy async (`backend/app/database/engine.py`), event broadcast hub `BROADCAST` in `backend/app/simulation/runner.py`, deterministic agents in `backend/app/simulation/agents_d.py` (Monitoring, Diagnosis, RiskAnalyst, ResponsePlanner, RecoveryVerifier, Reporter), thermal `Engine` in `backend/app/simulation/engine.py` (tick = 1 min physics), `risk()` in `backend/app/simulation/risk.py`.
- Frontend: Next.js 15 App Router + Tailwind v4 in `frontend/` (pages: `/`, `/dashboard`, `/simulation`, `/twin`, `/shipments`, `/incidents`, `/analytics`, `/copilot`, `/reports`, `/settings`), store `frontend/lib/store.tsx` consumes WS `sensor_update`/`agent_event`/`alert` messages and REST via `lib/api.ts` (default `http://127.0.0.1:8000`).
- Backend venv: `backend/.venv` (fastapi, sqlalchemy, aiosqlite, reportlab, websockets). Node 24 + npm 12. `maplibre-gl` is NOT yet installed — Task adds it.
- AI mode: deterministic-first (LLM optional via `OPENAI_API_KEY`) — agents are plain Python classes; no LLM calls in the loop.
- Windows host: run servers as background terminals; `taskkill`-style process control is discouraged mid-run — prefer picking fresh ports when EADDRINUSE appears.

## Architecture / proposed approach

A new `FleetOrchestrator` (one asyncio task, ~5 Hz world tick inside the existing backend process) owns `Vehicle` objects that each embed the existing thermal `Engine` for their reefer box and move along polylines from a `RoutingService`. Telemetry, incidents, and AI decisions flow through the existing `BROADCAST` hub with a typed event envelope; the same `vehicle.*` events are persisted (rolling) to SQLite. The `/live-map` page (MapLibre GL + OSM raster tiles) renders markers from WS state and interpolates positions with `requestAnimationFrame`; route selection/warehouse matching/emergency diversion run through deterministic agents that reuse `risk()` and expose explainable scores. Real-world routing (OSRM public demo server) sits behind an interface with a pure-Python fallback so the demo never depends on the network.

Sim time maps ticks→minutes (vehicle moves seconds-of-sim-distance per world tick); speed multiplier scales the world tick rate, not physics constants.

---

## Phase 0 — shared vocabulary (event envelope + sim clock)

### Task 0.1: Event envelope helper
**File:** `backend/app/simulation/events.py` (new)

```python
"""Typed event envelope for the fleet + facility world."""
from __future__ import annotations
import time, uuid

_LEVELS = ("info", "warning", "critical")

def make_event(etype: str, payload: dict, source: str = "fleet") -> dict:
    assert "." in etype, f"event type must be namespaced, got {etype!r}"
    return {
        "event_id": uuid.uuid4().hex[:12],
        "type": etype,
        "ts": time.time(),
        "source": source,
        "payload": payload,
    }

def severity_of(level: str) -> str:
    return level if level in _LEVELS else "info"
```

**Verify:** `backend/.venv/Scripts/python -c "import sys; sys.path.insert(0,'backend'); from app.simulation.events import make_event; print(make_event('vehicle.position.updated', {'lat': 1})['type'])"` → prints `vehicle.position.updated`.

### Task 0.2: Sim clock with speed multiplier
**File:** `backend/app/simulation/clock.py` (new)

```python
class SimClock:
    """Wall-scheduled world ticks. speed=5 → world advances 5 sim-minutes per wall-second..."""
    def __init__(self, speed: float = 1.0, base_hz: float = 4.0):
        self.speed = max(0.25, min(100.0, speed))
        self.base_hz = base_hz          # world ticks per wall second at 1x
        self.sim_minutes_per_tick = 0.25  # physics advance per world tick
        self.sim_time = 0.0            # sim minutes elapsed

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.25, min(100.0, speed))

    async def run(self, on_tick) -> None:
        import asyncio
        while True:
            t0 = time.perf_counter()
            self.sim_time += self.sim_minutes_per_tick * self.speed
            await on_tick()
            dt = time.perf_counter() - t0
            await asyncio.sleep(max(0.0, (1.0 / self.base_hz) - dt))
```

(add `import time` at top). **Verify:** unit test in Phase 8 Task 8.1.

**Commit:** `git add -A && git commit -m "feat(fleet): event envelope + sim clock"`

---

## Phase 1 — geography + data model

### Task 1.1: Region dataset (Delhi NCR seed)
**File:** `backend/app/simulation/geo_data.py` (new). ~8 warehouses, ~8 destinations, ~14 route polyline templates (3–7 `[lng, lat]` points each) connecting them, ~10 drivers, region config:

```python
REGION = {"name": "Delhi NCR", "center": [77.10, 28.58], "zoom": 9.5}
WAREHOUSES = [
    {"id": "WH-001", "name": "Delhi Central Cold Storage", "lat": 28.6139, "lng": 77.2090,
     "capacity": 1000, "available_capacity": 430, "cargo_types": ["fresh_produce", "dairy", "frozen_goods"],
     "docks": 4, "busy_docks": 1, "queue_min": 4, "proc_min": 12, "status": "OPERATIONAL"},
    # ... WH-002 Gurugram, WH-003 Noida, WH-004 Ghaziabad, WH-005 Faridabad,
    #     WH-006 Airport, WH-007 Hospital DC, WH-008 Retail Hub  (fill plausible coords 28.3–28.8 / 76.9–77.6)
]
DESTINATIONS = [  # delivery points: hospitals/retail/etc.
    {"id": "D-101", "name": "Apollo Hospital Delhi", "lat": 28.6297, "lng": 77.2080,
     "required_cargo": ["pharma"], "priority": "CRITICAL", "capacity": 220, "temp_min": 2, "temp_max": 8},
    # ... 7 more
]
# POLYLINES: dict[(from_id, to_id)] -> list[[lng, lat], ...] with 3-7 points,
# each with a base "speed_limit_kmh" (40-80) and "traffic" (LOW..SEVERE) seed.
DRIVERS = ["R. Verma", "S. Khan", ...]  # 10 names
```

**Verify:** `backend/.venv/Scripts/python -c "import sys; sys.path.insert(0,'backend'); from app.simulation.geo_data import WAREHOUSES, DESTINATIONS, POLYLINES, DRIVERS; assert len(WAREHOUSES)>=8 and len(DESTINATIONS)>=8 and len(POLYLINES)>=14 and len(DRIVERS)>=10; print('geo OK', len(POLYLINES))"` → `geo OK 14`.

### Task 1.2: Fleet DB models
**File:** `backend/app/models/fleet.py` (new)

```python
from .entities import Base
from sqlalchemy import Float, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class Vehicle(Base):
    __tablename__ = "fleet_vehicles"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)     # TRUCK-104
    kind: Mapped[str] = mapped_column(String(24), default="REFRIGERATED_TRUCK")
    energy_type: Mapped[str] = mapped_column(String(10), default="DIESEL")  # DIESEL/ELECTRIC/HYBRID
    driver: Mapped[str] = mapped_column(String(40), default="")
    lat: Mapped[float] = mapped_column(Float); lng: Mapped[float] = mapped_column(Float)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_pct: Mapped[float] = mapped_column(Float, default=80.0)
    engine_on: Mapped[bool] = mapped_column(Boolean, default=True)
    vehicle_health: Mapped[float] = mapped_column(Float, default=95.0)
    capacity_units: Mapped[int] = mapped_column(Integer, default=1000)
    load_units: Mapped[int] = mapped_column(Integer, default=0)
    cargo_type: Mapped[str] = mapped_column(String(24), default="fresh_produce")
    shipment_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    destination_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="IN_TRANSIT")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Route(Base):
    __tablename__ = "fleet_routes"
    id: Mapped[int] = mapped_column(String(16), primary_key=True)     # R-2048
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("fleet_vehicles.id"), index=True)
    origin_id: Mapped[str] = mapped_column(String(12))
    destination_id: Mapped[str] = mapped_column(String(12))
    route_type: Mapped[str] = mapped_column(String(16), default="BASE")  # BASE/SHORTEST/FASTEST/AI
    geometry: Mapped[str] = mapped_column(Text, default="[]")         # JSON [[lng,lat],...]
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    eta_min: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class VehicleEvent(Base):
    __tablename__ = "fleet_vehicle_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(12), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    lat: Mapped[float] = mapped_column(Float); lng: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(10), default="info")
    description: Mapped[str] = mapped_column(Text, default="")
    sim_minute: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RouteDecision(Base):
    __tablename__ = "fleet_route_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(12), index=True)
    decision: Mapped[str] = mapped_column(String(16))   # CONTINUE/REROUTE/DIVERT/...
    recommended: Mapped[str] = mapped_column(Text, default="")   # JSON summary
    reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sim_minute: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Register in `backend/app/models/__init__.py` (append imports). Startup already does `Base.metadata.create_all`, so no Alembic needed for SQLite demo (note in Risks).

**Verify:** restart backend (`Ctrl-C` + rerun) or on a fresh boot: `curl -s http://127.0.0.1:8000/api/status` → 200; then `sqlite3` check is unnecessary — Task 3.4's fleet state endpoint proves tables exist.

**Commit:** `feat(fleet): geo dataset + vehicle/route/decision models`

---

## Phase 2 — routing engine (interface + OSRM + fallback)

### Task 2.1: RoutingService with pluggable providers
**File:** `backend/app/simulation/routing.py` (new)

```python
"""Routing abstraction: OSRM (public demo) with deterministic offline fallback.
All functions are sync (called from async world loop sparingly) and return
{"geometry": [[lng,lat],...], "distance_km": float, "duration_min": float}."""
from __future__ import annotations
import json, math, urllib.request
from .geo_data import WAREHOUSES, DESTINATIONS, POLYLINES

_NODES = {**{w["id"]: (w["lng"], w["lat"]) for w in WAREHOUSES},
          **{d["id"]: (d["lng"], d["lat"]) for d in DESTINATIONS}}

def haversine_km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, [a[1], a[0], b[1], b[0]])
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2 * 6371.0 * math.asin(math.sqrt(h))

def polyline_km(pts) -> float:
    return sum(haversine_km(pts[i], pts[i+1]) for i in range(len(pts)-1))

class RoutingService:
    def __init__(self, provider: str = "auto"):
        self.provider = provider  # "auto" | "osrm" | "fallback"

    def calculate_route(self, origin_id: str, dest_id: str, traffic_factor: float = 1.0) -> dict:
        if self.provider in ("auto", "osrm"):
            try:
                return self._osrm(origin_id, dest_id, traffic_factor)
            except Exception:
                if self.provider == "osrm":
                    raise
        return self._fallback(origin_id, dest_id, traffic_factor)

    def _osrm(self, origin_id, dest_id, traffic_factor) -> dict:
        o, d = _NODES[origin_id], _NODES[dest_id]
        url = (f"https://router.project-osrm.org/route/v1/driving/"
               f"{o[0]},{o[1]};{d[0]},{d[1]}?overview=full&geometries=geojson")
        with urllib.request.urlopen(url, timeout=4) as r:
            data = json.load(r)
        rt = data["routes"][0]
        pts = [[p[0], p[1]] for p in rt["geometry"]["coordinates"]]
        # simplify: keep every 2nd point beyond 200 to cap payload
        step = 2 if len(pts) > 200 else 1
        pts = pts[::step]
        return {"geometry": pts, "distance_km": rt["distance"]/1000.0,
                "duration_min": (rt["duration"]/60.0) * traffic_factor}

    def _fallback(self, origin_id, dest_id, traffic_factor) -> dict:
        key = (origin_id, dest_id)
        pts = POLYLINES.get(key) or POLYLINES.get((dest_id, origin_id))
        if pts is None:  # invent a 3-point dogleg via midpoint jitter (deterministic per pair)
            o, d = _NODES[origin_id], _NODES[dest_id]
            mid = [(o[0]+d[0])/2 + 0.01, (o[1]+d[1])/2 - 0.008]
            pts = [o, mid, d]
        dist = polyline_km(pts)
        return {"geometry": [list(p) for p in pts], "distance_km": dist,
                "duration_min": dist / 42.0 * 60.0 * traffic_factor}

    def alternatives(self, origin_id, dest_id, traffic_factor=1.0) -> list[dict]:
        """Return up to 3 candidates: base, a slower-traffic variant (factor 1.25),
        and a longer-distance variant (mid detour point added)."""
        base = self.calculate_route(origin_id, dest_id, traffic_factor)
        heavy = self.calculate_route(origin_id, dest_id, traffic_factor * 1.25)
        detour = dict(base)
        m = base["geometry"][len(base["geometry"])//2]
        detour = {**base, "geometry": [base["geometry"][0], [m[0]+0.02, m[1]-0.015], base["geometry"][-1]],
                  "distance_km": base["distance_km"] * 1.15,
                  "duration_min": base["duration_min"] * 1.08}
        return [base, heavy, detour]
```

**Verify:** `.venv/Scripts/python -c "import sys; sys.path.insert(0,'backend'); from app.simulation.routing import RoutingService; r=RoutingService('fallback'); rt=r.calculate_route('WH-001','WH-002'); assert rt['distance_km']>5 and len(rt['geometry'])>=2; print('route OK', round(rt['distance_km'],1), 'km')"` → `route OK <n> km` (n>5). If network is up, also run provider `"auto"` once and expect a plausible `duration_min` — network failure must silently fall back.

**Commit:** `feat(fleet): routing service with OSRM + offline fallback`

---

## Phase 3 — vehicle twin + fleet orchestrator

### Task 3.1: Vehicle twin (movement + thermal + driver behavior)
**File:** `backend/app/simulation/fleet.py` (new). Core class:

```python
"""Live vehicle twin. Owns: route polyline progress, kinematics with noise,
reefer box = existing thermal Engine, cargo, driver-behavior stats."""
from __future__ import annotations
import math, random
from .engine import Engine
from .risk import risk as risk_fn

COMPRESSOR_OK, COMPRESSOR_DEGRADED, COMPRESSOR_FAILED = "ONLINE", "DEGRADED", "FAILED"

class VehicleTwin:
    def __init__(self, vid, kind, energy, driver, cargo_type, load_units, capacity_units,
                 origin_id, dest_id, route: dict, seed: int):
        self.id = vid; self.kind = kind; self.energy = energy; self.driver = driver
        self.cargo_type = cargo_type; self.load_units = load_units; self.capacity_units = capacity_units
        self.origin_id, self.dest_id = origin_id, dest_id
        self.route = route
        self.geom = route["geometry"]
        self.total_km = route["distance_km"]
        self.done_km = 0.0
        self.rng = random.Random(seed)
        # kinematics
        self.lat, self.lng = self.geom[0][1], self.geom[0][0]
        self.heading = 0.0; self.speed_kmh = 0.0; self.speed_limit = 55.0
        self.accel_mps2 = 0.0; self.speeds = [self.speed_kmh]
        self.fuel_pct = 60.0 + self.rng.uniform(0, 35); self.battery_pct = 70.0 + self.rng.uniform(0, 28)
        self.vehicle_health = 88.0 + self.rng.uniform(0, 11)
        self.engine_temp_c = 88.0 + self.rng.uniform(-4, 4)
        # reefer box reuses thermal engine; 1 sim-minute per world tick step
        box_profile = {"fresh_produce": (4.0, 2.0, 8.0), "dairy": (4.0, 1.0, 5.0),
                       "frozen_goods": (-18.0, -22.0, -15.0), "pharma": (5.0, 2.0, 8.0)}[cargo_type]
        self.box = Engine(target=box_profile[0], mn=box_profile[1], mx=box_profile[2],
                          hum_min=55.0, hum_max=85.0, seed=seed)
        self.compressor = COMPRESSOR_OK; self.cooling_eff = 97.0; self.door_open = False
        self.cargo_health = 100.0
        self.status = "IN_TRANSIT"; self.idle_min = 0.0; self.stop_min = 0.0
        self.speed_events = 0; self.harsh_brakes = 0; self.harsh_accels = 0
        self.route_adherence = 100.0
        # connectivity
        self.gps_acc = self.rng.uniform(2.5, 6.0); self.signal = self.rng.uniform(70, 99)

    # ---------- per world tick ----------
    def step(self, dt_min: float, traffic_factor: float, ambient_c: float):
        """dt_min = sim minutes elapsed this world tick. Mutates everything."""
        self.box.ambient = ambient_c
        # kinematics
        target = self.speed_limit / max(traffic_factor, 0.5)
        target *= self.rng.uniform(0.85, 1.12)
        if self.door_open:
            target = min(target, 8.0)
        old = self.speed_kmh
        self.speed_kmh = max(0.0, self.speed_kmh + (target - self.speed_kmh) * 0.3 + self.rng.gauss(0, 1.4))
        self.speeds.append(self.speed_kmh); self.speeds = self.speeds[-120:]
        dv_mps = (self.speed_kmh - old) / 3.6
        self.accel_mps2 = dv_mps / (dt_min * 60.0) if dt_min > 0 else 0.0
        if self.accel_mps2 < -2.5: self.harsh_brakes += 1
        if self.accel_mps2 > 1.8:  self.harsh_accels += 1
        if self.speed_kmh > self.speed_limit + 5: self.speed_events += 1
        # advance along polyline by km travelled
        adv_km = self.speed_kmh * (dt_min / 60.0)
        self.done_km = min(self.total_km, self.done_km + adv_km)
        frac = self.done_km / max(self.total_km, 1e-6)
        self._place_on_route(frac)
        # reefer: one thermal step per world tick (dt = dt_min minutes)
        snap = None
        for _ in range(max(1, int(round(dt_min / 0.25))) if dt_min >= 0.25 else 1):
            snap = self.box.tick()
        if self.compressor == COMPRESSOR_FAILED:
            self.box.compressor_on = False
        elif self.compressor == COMPRESSOR_DEGRADED:
            self.box.cooling_efficiency = max(0.15, self.box.cooling_efficiency - 0.01)
        self.cooling_eff = round(self.box.cooling_efficiency * 100, 1)
        # cargo health from thermal exposure (reuse risk engine inputs)
        z = {"mn": self.box.mn, "mx": self.box.mx}
        r = risk_fn(snap or self.box.snapshot(), z, self._over_ticks, trend_c_per_min=self._trend())
        self.cargo_health = snap["cargo_health"] if snap else self.cargo_health
        self.risk = r
        # energy
        burn = (0.02 + self.speed_kmh / 3000.0 + (1 if self.box.compressor_on else 0.4)) * dt_min
        if self.energy == "ELECTRIC":
            self.battery_pct = max(0.0, self.battery_pct - burn * 1.2)
        else:
            self.fuel_pct = max(0.0, self.fuel_pct - burn)
        self.vehicle_health = max(40.0, self.vehicle_health - 0.0004 * dt_min)
        self.engine_temp_c = 88 + (10 if self.rng.random() < 0.01 else 0) + self.rng.gauss(0, 1)
        # connectivity flicker
        self.gps_acc = max(1.8, min(12.0, self.gps_acc + self.rng.gauss(0, 0.25)))
        self.signal = max(25.0, min(99.0, self.signal + self.rng.gauss(0, 1.2)))
        return self.snapshot()

    def _trend(self):
        hs = getattr(self.box, "_hist", [])
        return 0.0  # trend computed by orchestrator from snapshots (keep twin stateless re history)

    # ---------- helpers ----------
    def _place_on_route(self, frac: float):
        pts = self.geom
        total = len(pts) - 1
        idx_f = frac * total
        i = min(total - 1, int(idx_f)); t = idx_f - i
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        self.lng = x0 + (x1 - x0) * t; self.lat = y0 + (y1 - y0) * t
        self.heading = (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360.0) % 360.0

    def inject_failure(self, kind: str):
        if kind == "compressor_failure":
            self.compressor = COMPRESSOR_FAILED; self.box.compressor_on = False
        elif kind == "compressor_degradation":
            self.compressor = COMPRESSOR_DEGRADED; self.box.cooling_efficiency = 0.55
        elif kind == "door_open":
            self.door_open = True; self.box.inject("door_open")
        elif kind == "power_failure":
            self.box.inject("power_failure")
        elif kind == "heatwave":
            self.box.ambient_target = 46.0
        elif kind == "sensor_fault":
            self.box.inject("sensor_fault")

    def apply_action(self, action: str) -> bool:
        if action == "activate_backup_cooling":
            return self.box.activate_backup_cooling()
        if action == "close_door":
            self.door_open = False; self.box.close_door(); return True
        if action == "restart_compressor":
            if self.box.power_ok:
                self.box.compressor_on = True; self.box.cooling_efficiency = 1.0
                self.compressor = COMPRESSOR_OK; return True
            return False
        if action == "restore_power":
            self.box.restore_power(); return True
        return False

    def remaining_km(self): return max(0.0, self.total_km - self.done_km)
    def eta_min(self, traffic_factor=1.0):
        eff = max(8.0, sum(self.speeds[-10:]) / max(1, len(self.speeds[-10:])))
        return (self.remaining_km() / eff) * 60.0 * traffic_factor

    def _over_ticks(self):  # exposure ticks for risk()
        return int((self.box.temperature - self.box.mx) * 10) if self.box.temperature > self.box.mx else 0

    def snapshot(self):
        return {"vehicle_id": self.id, "lat": round(self.lat, 5), "lng": round(self.lng, 5),
                "heading": round(self.heading, 1), "speed_kmh": round(self.speed_kmh, 1),
                "accel_mps2": round(self.accel_mps2, 2), "speed_limit": self.speed_limit,
                "trip": {"route_id": self.route.get("id", "R-?"),
                         "distance_total_km": round(self.total_km, 2),
                         "distance_completed_km": round(self.done_km, 2),
                         "distance_remaining_km": round(self.remaining_km(), 2),
                         "eta_min": round(self.eta_min(), 1),
                         "progress_pct": round(100 * self.done_km / max(0.01, self.total_km), 1)},
                "vehicle": {"engine_status": "RUNNING" if self.engine_on_status() else "OFF",
                            "fuel_percent": round(self.fuel_pct, 1),
                            "battery_percent": round(self.battery_pct, 1),
                            "vehicle_health": round(self.vehicle_health, 1),
                            "engine_temperature": round(self.engine_temp_c, 1)},
                "refrigeration": {"compressor_status": self.compressor,
                                   "cooling_efficiency": self.cooling_eff,
                                   "temperature": self.box.snapshot()["temperature"],
                                   "humidity": self.box.snapshot()["humidity"],
                                   "door_open": self.door_open,
                                   "backup_cooling": self.box.backup_cooling,
                                   "power_ok": self.box.power_ok},
                "cargo": {"load_percent": round(100 * self.load_units / max(1, self.capacity_units), 1),
                          "cargo_health": round(self.cargo_health, 1),
                          "cargo_type": self.cargo_type,
                          "risk_level": self.risk["level"] if hasattr(self, "risk") else "LOW",
                          "risk_score": self.risk["score"] if hasattr(self, "risk") else 0},
                "driver": {"name": self.driver, "state": "DRIVING" if self.speed_kmh > 2 else "IDLE",
                           "safety_score": self.driver_score()},
                "connectivity": {"gps_accuracy_m": round(self.gps_acc, 1),
                                 "signal_strength": round(self.signal, 1)},
                "status": self.status}

    def engine_on_status(self): return self.box.power_ok
    def driver_score(self):
        pen = self.speed_events * 2 + self.harsh_brakes * 3 + self.harsh_accels * 2
        return int(max(40, 100 - pen))
```

**Verify:** unit test Task 8.2.

### Task 3.2: Traffic + ambient world state
**File:** `backend/app/simulation/traffic.py` (new)

```python
"""Simulated per-road traffic + ambient weather, driven by a seed and sim time."""
import random
LEVELS = ["LOW", "MODERATE", "HIGH", "SEVERE"]
FACTOR = {"LOW": 1.0, "MODERATE": 1.25, "HIGH": 1.8, "SEVERE": 2.6}

class TrafficWorld:
    def __init__(self, seed=42):
        self.rng = random.Random(seed)
        self.segments: dict[str, str] = {}   # "A>B" -> level
        self.ambient_c = 33.0
        self.weather = "NORMAL"

    def level_for(self, origin_id: str, dest_id: str, sim_minute: float) -> str:
        key = f"{origin_id}>{dest_id}"
        if key not in self.segments or self.rng.random() < 0.02:
            # occasional shift, weighted to LOW/MODERATE
            self.segments[key] = self.rng.choices(LEVELS, weights=[6, 3, 1.5, 0.5])[0]
        return self.segments[key]

    def factor_for(self, origin_id, dest_id, sim_minute):
        return FACTOR[self.level_for(origin_id, dest_id, sim_minute)]

    def maybe_weather(self, sim_minute: float) -> str:
        if self.rng.random() < 0.003:
            self.weather = self.rng.choices(["NORMAL", "HEATWAVE", "RAIN", "FOG"], weights=[7, 1.5, 1, 0.5])[0]
        self.ambient_c = {"NORMAL": 33.0, "HEATWAVE": 44.0, "RAIN": 27.0, "FOG": 25.0}[self.weather]
        return self.weather
```

### Task 3.3: FleetOrchestrator (world loop + AI hooks + persistence)
**File:** `backend/app/simulation/fleet_orchestrator.py` (new)

Responsibilities: spawn N vehicles (routes between geo nodes), run world ticks via `SimClock`, emit `vehicle.position.updated` (5 Hz aggregated JSON: `{vehicles: [snap...]}`), detect thermal incidents per vehicle (reuse: temp > box.mx sustained 4 ticks) → create `Incident` (existing table) + emit `fleet.incident.created`, run **FleetCoordinator** (Phase 4), persist `VehicleEvent` rows (rolling: keep last 200 per vehicle), update `Vehicle` rows every 5th tick. Expose `FLEET` global singleton.

Key loop (pseudocode to implement concretely):

```python
class FleetOrchestrator:
    def __init__(self, n_vehicles=12):
        self.clock = SimClock(speed=1.0)
        self.traffic = TrafficWorld()
        self.routing = RoutingService("auto")
        self.vehicles: dict[str, VehicleTwin] = {}
        self.paused = False
        self.events: list[dict] = []          # ring buffer for /live-map feed
        self.sim_minute = 0.0
    async def start(self, n=12): ...         # spawn + clock.run(self._tick)
    def spawn(self, i): ...                   # pick origin/dest pair + cargo type; VehicleTwin(...)
    async def _tick(self): ...                # for each vehicle: traffic factor, step(), collect snaps;
                                               # every tick: emit vehicle.position.updated with ALL snaps
                                               # every tick: incident check (box temp sustained) -> coordinator
                                               # every 5 ticks: persist Vehicle rows; append events ring
    async def inject(self, vehicle_id, failure): ...
    async def apply_action(self, vehicle_id, action): ...
```

Wire into FastAPI startup: in `backend/app/main.py` `startup()`, after table creation add:

```python
from .simulation.fleet_orchestrator import FLEET
import asyncio
FLEET_TASK = None  # module-level
# inside startup:
global FLEET_TASK
if os.getenv("FLEET_AUTOSTART", "1") == "1":
    FLEET_TASK = asyncio.create_task(FLEET.start(12))
```

### Task 3.4: Fleet REST endpoints
**File:** `backend/app/api/routes/fleet.py` (new), register in `main.py`.

```
GET  /api/fleet/state            -> {vehicles: [snap...], warehouses: [...], destinations: [...],
                                     sim_minute, weather, traffic, paused}
GET  /api/fleet/vehicle/{vid}    -> full snapshot + last 50 VehicleEvents
POST /api/fleet/vehicle/{vid}/inject   {"failure": "compressor_degradation"}
POST /api/fleet/vehicle/{vid}/action   {"action": "activate_backup_cooling"}
POST /api/fleet/speed           {"speed": 5}
POST /api/fleet/pause  /resume
POST /api/fleet/inject-random   (auto-demo: pick random vehicle, degrade compressor)
GET  /api/fleet/warehouses      -> live warehouse list (capacity jitter evolves)
POST /api/fleet/route-compare/{vid} -> current vs shortest vs fastest vs AI (uses agents)
```

**Verify:** with backend running: `curl -s http://127.0.0.1:8000/api/fleet/state | head -c 400` → JSON with `"vehicles": [` and 12 entries; `curl -s -X POST http://127.0.0.1:8000/api/fleet/inject-random` → `{"injected": "TRUCK-xxx", "failure": "compressor_degradation"}`.

**Commit:** `feat(fleet): vehicle twins, orchestrator, traffic world, REST endpoints`

---

## Phase 4 — AI logistics agents (deterministic)

### Task 4.1: Facility matching + route scoring agents
**File:** `backend/app/simulation/fleet_agents.py` (new)

```python
"""Deterministic logistics agents: FacilityMatcher, RouteScorer, FleetCoordinator."""
from .routing import haversine_km, RoutingService

class FacilityMatcher:
    """Rank warehouses for an at-risk vehicle. Score = weighted ETA + capacity +
    compatibility + queue + health. NEVER purely distance."""
    def __init__(self, routing: RoutingService, warehouses: list[dict]):
        self.routing = routing; self.wh = warehouses

    def rank(self, vehicle, traffic_factor_by_wh=None) -> list[dict]:
        out = []
        for w in self.wh:
            if w["status"] != "OPERATIONAL": continue
            if vehicle.cargo_type not in w["cargo_types"]:
                out.append({"id": w["id"], "name": w["name"], "compatible": False,
                            "reason": "cargo not supported", "score": 0}); continue
            if w["available_capacity"] < vehicle.load_units * 0.5:
                out.append({"id": w["id"], "name": w["name"], "compatible": False,
                            "reason": "insufficient capacity", "score": 0}); continue
            route = self.routing.calculate_route(vehicle.origin_or_current_node(), w["id"], 1.0)
            travel = route["duration_min"]; total = travel + w["queue_min"] + w["proc_min"] * 0.3
            cap_pct = w["available_capacity"] / max(1, w["capacity"])
            score = 100 - total * 2.2 + cap_pct * 25 - w["busy_docks"] * 3
            out.append({"id": w["id"], "name": w["name"], "compatible": True,
                        "eta_travel_min": round(travel, 1), "eta_total_min": round(total, 1),
                        "distance_km": round(route["distance_km"], 1), "free_capacity": w["available_capacity"],
                        "score": round(score, 1),
                        "reason": f"travel {travel:.0f}m + queue {w['queue_min']}m; capacity {w['available_capacity']}u"})
        return sorted([o for o in out if o.get("compatible")], key=lambda o: -o["score"]) \
             + [o for o in out if not o.get("compatible")]

WEIGHTS = {"eta": 0.40, "cargo": 0.20, "traffic": 0.15, "distance": 0.10, "facility": 0.10, "energy": 0.05}

class RouteScorer:
    def score(self, route: dict, traffic_factor: float, vehicle, facility=None) -> dict:
        eta = route["duration_min"]
        # projected cargo risk at arrival: hotter + longer = worse
        over = max(0.0, vehicle.box.temperature - vehicle.box.mx)
        slope = 0.20 if vehicle.compressor == "FAILED" else (0.08 if vehicle.compressor == "DEGRADED" else 0.0)
        proj_temp = vehicle.box.temperature + slope * eta
        cargo_risk_pts = min(40.0, (proj_temp - vehicle.box.mx) * 6 + over * 4)
        s = (100 - min(eta, 60) * 1.2) * WEIGHTS["eta"] \
          + (100 - cargo_risk_pts * 2) * WEIGHTS["cargo"] \
          + (100 - (traffic_factor - 1) * 100) * WEIGHTS["traffic"] \
          + (100 - min(route["distance_km"], 60)) * WEIGHTS["distance"] \
          + ((100 - facility["eta_total_min"] * 2) * WEIGHTS["facility"] if facility else 0) \
          + (vehicle.fuel_pct if vehicle.energy != "ELECTRIC" else vehicle.battery_pct) * WEIGHTS["energy"]
        return {"route": route, "score": round(s, 1), "eta_min": round(eta, 1),
                "traffic_factor": traffic_factor,
                "projected_temp_c": round(proj_temp, 1),
                "cargo_risk_after": "CRITICAL" if cargo_risk_pts > 30 else "HIGH" if cargo_risk_pts > 15 else "MEDIUM" if cargo_risk_pts > 6 else "LOW"}
```

(`vehicle.origin_or_current_node()` = nearest geo node to current lat/lng — add a small helper in the twin or orchestrator: iterate `_NODES`, return nearest id.)

### Task 4.2: FleetCoordinator (decision loop)
Same file. On incident:

1. `FacilityMatcher.rank(vehicle)` → candidates with reasons.
2. For top-3 candidates: `routing.alternatives(current_node, wh_id, traffic_factor)` → score each with `RouteScorer` (include a **continue-to-original-destination** option scored the same way).
3. Decision rule (explainable): if best facility route `eta_total_min` + margin < current-destination ETA **and** projected cargo risk improves by ≥1 level → `DIVERT`. If compressor merely degraded and backup available → `REROUTE` to nearest good facility only if ETA ≤ original. Emit `ai.route.decision` via `BROADCAST` with full explanation payload (candidates, scores, chosen, reason text) and persist `RouteDecision`.
4. Orchestrator applies: set `vehicle.route` to new geometry from current position → facility (prefix route with current `[lng, lat]`), update `vehicle.dest_id`, emit `vehicle.route.changed`, `route.rerouted`.
5. On arrival at facility (remaining_km < 0.3): simulate cargo transfer (`load_units` moves to warehouse `available_capacity -= load`, cargo health freezes, `vehicle.status = "AT FACILITY"`, emit `cargo.transferred`), then verify recovery (temp back in range via backup cooling) → resolve incident (reuse existing `Incident.status = "RESOLVED"` + reporter agent for the report).

**Verify:** Task 8.3 integration test drives the full loop headlessly.

**Commit:** `feat(fleet): facility matching, route scoring, fleet coordinator AI`

---

## Phase 5 — WebSocket fan-out

### Task 5.1: Fleet events over existing hub
In `fleet_orchestrator.py`, emit via existing `BROADCAST` (import from `.runner`): 

- per world tick: `vehicle.position.updated` with `{vehicles: [all snapshots]}` (aggregated — one message per tick, not per vehicle; frontends interpolate).
- on incidents/decisions: `fleet.incident.created`, `ai.route.decision`, `vehicle.route.changed`, `cargo.transferred`, `traffic.changed`, `weather.changed`.

Frontend store: extend `frontend/lib/store.tsx` — in `ws.onmessage` add:

```ts
if (m.type === "vehicle.position.updated") dispatch({ type: "fleet", payload: m.vehicles });
else if (["fleet.incident.created","ai.route.decision","vehicle.route.changed",
          "cargo.transferred","traffic.changed","weather.changed"].includes(m.type))
  dispatch({ type: "fleet_event", payload: m });
```

with reducer cases `fleet` (store `st.vehicles`) and `fleet_event` (prepend to `st.fleetEvents`, cap 90) + `st.fleetMeta` for weather/sim_minute.

**Verify:** Task 8.4 WS smoke: connect a `websockets` client for ~8 s, count `vehicle.position.updated` ≥ 30 messages with ≥ 10 distinct `vehicle_id`s.

**Commit:** `feat(fleet): WS broadcast of fleet telemetry + AI decisions`

---

## Phase 6 — `/live-map` frontend

### Task 6.1: Install map deps
`cd frontend && npm install maplibre-gl @types/maplibre-gl supercluster  # supercluster optional; defer if build issues`

### Task 6.2: LiveMap page
**File:** `frontend/app/live-map/page.tsx` (new) + `frontend/components/live-map/`:

- `MapCanvas.tsx` — MapLibre map, OSM raster style (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`, attribution required in corner), markers as a GeoJSON **symbol layer with truck SVG rotated via `icon-rotate: ["get","heading"]`** + per-vehicle risk pulse implemented as a circle layer with paint opacity animation; warehouses/destinations as circle+symbol layers; routes as line layers: active route solid accent, alternatives dashed, old route fading opacity transition; traffic segments colored by level on hover/selection only (YAGNI: full traffic polylines deferred).
- Interpolation: keep `useRef` of last two backend snapshots; `requestAnimationFrame` loop lerps each marker's lat/lng (~100 ms behind wall clock). No marker re-mounting: update GeoJSON **sources** only.
- Vehicle click → side panel (`VehiclePanel.tsx`) with tabs: Overview / Movement / Refrigeration / Cargo / Health / Driver / Events — all fields from the twin snapshot; buttons: Track (camera follow), AI Analysis (`POST /api/fleet/route-compare/{vid}`), Inject Failure, Apply Recovery Action.
- `FleetBar.tsx` — top strip: vehicles count, warehouses, at-risk, critical, weather, sim clock, speed controls (0.5/1/5/10 buttons → `/api/fleet/speed`), pause/resume, Run Demo (`POST /api/fleet/inject-random`).
- `Sidebar.tsx` — filters (All / At Risk / Critical / In Transit / Idle), search box (matches vehicle/warehouse/destination id or name → `flyTo`), active incidents list (click → center map + pulse).
- `EventFeed.tsx` — bottom strip: `st.fleetEvents` (AI decisions rendered with reasoning text), vehicle events, toasts.
- AI decision card overlay when `ai.route.decision` arrives: candidates table (score/ETA/reason), "APPROVE DIVERSION" (assisted) or auto-applied (autonomous toggle → `POST /api/fleet/vehicle/{vid}/action` chosen by backend).
- Add nav entry in `frontend/components/Layout.tsx` NAV array: `{ href: "/live-map", label: "Live Map", icon: Map }` (import `Map` from lucide).

**Verify:** `npm run build` exits 0; open `http://127.0.0.1:3000/live-map` → tiles load, ≥ 10 truck markers moving smoothly within 10 s, warehouse markers visible, clicking a truck opens panel with live-updating temp/ETA.

**Commit:** `feat(fleet): /live-map with animated vehicles, panels, AI decision UI`

---

## Phase 7 — one-click autonomous demo

### Task 7.1: Demo orchestration endpoint
**File:** `backend/app/api/routes/fleet.py` (extend)

`POST /api/fleet/demo` — asyncio task that: waits 10 s (healthy fleet view) → `FLEET.inject("TRUCK-104" or random, "compressor_degradation")` → the natural pipeline does the rest (incident → coordinator → divert → transfer → verify → resolve). Emits `demo.stage` events at each stage (text for the feed): "Stage 4: incident injected", etc. Frontend `FleetBar` Run Demo button calls this and shows a stage toast per event.

**Verify:** `curl -s -X POST http://127.0.0.1:8000/api/fleet/demo` then over ~90 s: WS client sees `fleet.incident.created` → `ai.route.decision` → `vehicle.route.changed` → `cargo.transferred` in order; `GET /api/incidents` shows one RESOLVED fleet incident with reporter analysis.

**Commit:** `feat(fleet): one-click autonomous rescue demo`

---

## Phase 8 — tests (TDD order per task; run whole suite at end)

### Task 8.1: `backend/tests/test_clock_geo.py`
```python
def test_clock_bounds():
    from app.simulation.clock import SimClock
    c = SimClock(speed=500); c.set_speed(500)
    assert c.speed == 100.0
    c.set_speed(0.1); assert c.speed == 0.25

def test_geo_integrity():
    from app.simulation.geo_data import WAREHOUSES, POLYLINES
    for w in WAREHOUSES:
        assert 28.0 < w["lat"] < 29.0 and 76.5 < w["lng"] < 77.8
        assert w["capacity"] >= w["available_capacity"]
    for (a, b), pts in POLYLINES.items():
        assert len(pts) >= 3
```
Run: `.venv/Scripts/python -m pytest backend/tests/test_clock_geo.py -q` → 2 passed.

### Task 8.2: `backend/tests/test_fleet_twin.py`
Create twin with fallback route, step it 40 ticks with `dt_min=0.25`, assert: position changed ≥ 1 km total, heading in [0,360), speed ≥ 0, `snapshot()["trip"]["distance_remaining_km"]` < total, inject `compressor_failure` → 30 more ticks → `refrigeration.temperature` > box mx and `cargo.risk_level != "LOW"`. Then `apply_action("activate_backup_cooling")` → 30 ticks → temperature falls and `risk_level in ("LOW","MEDIUM")`.

### Task 8.3: `backend/tests/test_fleet_ai.py`
`FacilityMatcher.rank` on a fake vehicle: closest warehouse with 0 capacity ranks below a farther one with capacity — assert order + reasons present. `RouteScorer.score`: degraded compressor + long ETA must yield `cargo_risk_after == "CRITICAL"` and a strictly lower score than a short-ETA divert route.

### Task 8.4: `backend/tests/test_fleet_ws.py` (needs running backend; mark `@pytest.mark.integration`)
Connect WS 8 s → ≥ 30 `vehicle.position.updated`, ≥ 10 distinct vehicles, each message has `payload.vehicles` list with `lat/lng/heading`.

### Task 8.5: full-suite command
`.venv/Scripts/python -m pytest backend/tests -q` → all pass (existing sim_regression included). Frontend: `npm run build` → exit 0.

**Commit:** `test(fleet): clock, twin physics, AI ranking, WS integration`

---

## Explicitly deferred (YAGNI / post-capstone)

MapLibre satellite view, minimap, geofence polygons, driver leaderboard, tire simulation, replay scrubber UI (data is persisted — playback UI later), LLM-backed agent narration (deterministic first), multi-stop VRP optimization (single-destination routing now), Postgres/Alembic (SQLite demo), Docker compose, incident heatmap. Weather = ambient scalar affecting cooling only (no rain-on-map rendering).

## Risks, tradeoffs, open questions

- **OSRM public server rate-limits** (public demo instance, ~1 req/s policy). Mitigation: fallback routing is the default for bulk simulation; OSRM used opportunistically with 4 s timeout + result cache keyed by (origin, dest). Campus network blocked `magicui.design` DNS before — external tile/route fetch may fail on campus; OSM tiles from `tile.openstreetmap.org` usually work, but the **map must render markers even with zero tiles** (dark canvas + markers) so the demo survives offline.
- **Windows asyncio + SQLite**: `check_same_thread=False` already set; avoid per-tick commits (batch every 5th tick) to prevent WS jitter.
- **WS payload size**: 12 vehicles × full snapshot at 4–5 Hz ≈ 40 KB/s — fine locally; cap at 50 vehicles before payload trimming becomes necessary (acceptance asks 10–50; ship 12, prove headroom at 25 in test).
- **Thermal engine reuse**: `Engine.tick()` was built for facility ticks (1 tick = 1 min). Vehicle steps pass fractional dt via repeated 0.25-min sub-steps — acceptable drift, deterministic, documented in code comment.
- **Open**: should fleet incidents write to the *existing* `Incident` table (yes — single incident pipeline, copilot/analytics get them free) — implemented that way; flag if evaluators want them separated.
- **Open**: MapLibre marker rotation needs a truck icon PNG in `frontend/public/truck.png` — generate a simple 48×48 SVG→PNG (or use unicode 🚚 as symbol text layer if icon tooling is unavailable — decide at Task 6.2, text-fallback is acceptable).

## Execution order & verification cadence

Phases 0→8 strictly in order; after each phase: run that phase's verify command + `pytest backend/tests -q` + `npm run build` (Phase 6+), then `git commit`. Final acceptance = the Phase 7 demo run + all Phase 8 tests green + manual checklist from spec §137 items covered by tasks above.

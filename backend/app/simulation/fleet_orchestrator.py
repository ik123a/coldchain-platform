"""FleetOrchestrator: the live world.

Owns VehicleTwins, runs the SimClock loop, detects thermal incidents,
runs FleetCoordinator decisions, applies reroutes, simulates arrival +
cargo transfer + recovery verification, persists rolling state, and
broadcasts everything over the existing BROADCAST hub.
"""
from __future__ import annotations
import asyncio, json, logging
from datetime import datetime, timedelta
from .clock import SimClock
from .traffic import TrafficWorld
from .routing import RoutingService, nearest_node, haversine_km
from .fleet import VehicleTwin
from .engine import Engine
from .risk import risk as risk_score_fn
from .fleet_agents import FacilityMatcher, RouteScorer, FleetCoordinator
from .events import make_event
from .geo_data import WAREHOUSES, DESTINATIONS, POLYLINES, DRIVERS, CARGO_TYPES, REGION, GEOFENCES
from .fleet_ops import pick_service, validate_transfer, apply_transfer, priority_queue, is_cargo_vehicle
from .analytics import fleet_kpis
from sqlalchemy import delete, select
from ..database.engine import SessionLocal
from ..models.fleet import Vehicle, FleetRoute, VehicleEvent, RouteDecision, CargoTransfer
from ..models.entities import Incident, AIAnalysis, RecommendedAction
from .runner import BROADCAST
from . import agents_d as A
from . import incidents_catalogue as IC
from . import prediction as PRED
from . import lessons as LNS

log = logging.getLogger("fleet")
SUSTAIN_TICKS = 6            # consecutive over-band world-ticks → incident
ARRIVE_KM = 0.3
# A service truck is on scene within this radius of its assigned truck. Named so
# the value is not a bare literal in two places (`_service_progress` and the
# re-target guard), which is how the two could silently drift apart.
SERVICE_ARRIVAL_KM = 0.8
EVENT_RETENTION_HOURS = 6    # telemetry history window; incidents and reports are never pruned


class FleetOrchestrator:
    def __init__(self, n_vehicles: int = 12):
        self.clock = SimClock(speed=2.0)
        self.scenario = {"seed": 42, "weather": None, "traffic_intensity": 1.0,
                         "failure_probability": 0.0, "fleet_size": n_vehicles}
        self.traffic = TrafficWorld(seed=42, traffic_intensity=1.0)
        self.routing = RoutingService("auto")
        self.warehouses = [dict(w) for w in WAREHOUSES]
        self.matcher = FacilityMatcher(self.routing, self.warehouses)
        self.scorer = RouteScorer()
        self.coordinator = FleetCoordinator(self.matcher, self.scorer, self.routing)
        self.vehicles: dict[str, VehicleTwin] = {}
        self.paused = False
        self.sim_minute = 0.0
        self.n_vehicles = n_vehicles
        self._tick_n = 0
        self.incident_db: dict[str, int] = {}     # vehicle_id -> Incident.id
        self._incident_tel: dict[int, list[dict]] = {}  # incident_id -> deep-copied tel frames
        self._over_run: dict[str, int] = {}
        self._autonomous = True                    # AI decisions auto-apply (SIMULATION ONLY)
        # Dock/capacity accounting. A delivery occupies a dock for `proc_min`
        # (its unloading/processing time), then the dock frees and the consumed
        # capacity returns to `available_capacity`. Previously the incident
        # branch decremented available_capacity and incremented busy_docks with
        # no matching release anywhere, so warehouses drained to zero over a
        # long run and every later divert failed with "insufficient capacity".
        self._pending_release: dict[str, int] = {}   # facility_id -> units to credit back
        self._dock_free_at: dict[str, float] = {}    # facility_id -> sim_minute dock frees
        # Operator-configured trucks (see the dispatch section below). Separate
        # from self.vehicles so a demo-fleet rebuild cannot delete them.
        self.dispatch: list[dict] = []
        # Monotonic counter behind every truck id (T01, T02, …). Never reused,
        # so "remove Truck 02 then add" cannot produce two twins that once
        # shared a vehicle id.
        self._dispatch_seq = 0
        # Service/transfer state lives here rather than only in _spawn_fleet:
        # removing a user truck must clean these even before any fleet spawn.
        self.service_tasks: dict[str, str] = {}    # service vid -> target vid
        self.service_pending: dict[str, str] = {}  # target vid -> task type
        # service vid -> sim_minute of its last navigation re-target. Bounds how
        # often a service truck is re-routed toward a moving target.
        self._service_retarget_at: dict[str, float] = {}
        # Monotonic counter folded into FleetRoute ids. `int(sim_minute)` alone
        # is not unique — two diverts for one vehicle inside the same sim-minute
        # collided and the insert raised UNIQUE constraint failed.
        self._route_seq = 0
        self.transfers: dict[str, dict] = {}       # donor vid -> transfer state
        # --- human-in-the-loop approval queue ---
        # `require_approval` is the master switch for the demonstration. It
        # defaults ON because the brief asks for human-in-the-loop, and the
        # operator can turn it off from the UI to show the fully autonomous
        # behaviour for comparison.
        self.require_approval = True
        # Sim-minutes a recommendation may sit before it is auto-approved.
        # 0 disables the escape hatch entirely (the run will wait forever,
        # which is the honest behaviour for a demo with an operator present).
        self.AUTO_APPROVE_TIMEOUT_S = float(
            __import__("os").getenv("AUTO_APPROVE_TIMEOUT_SIM_MIN", "0") or 0)
        # Sim-minutes an operator may take to respond to a CRITICAL
        # recommendation before the agent escalates it on its own.
        #
        # This is deliberately NOT the same as AUTO_APPROVE_TIMEOUT_S. That one
        # silently EXECUTES the divert, which is the opposite of what an
        # unattended critical incident needs: nobody asked for a truck to be
        # rerouted with no human in the loop. This one raises the alarm —
        # incident status ESCALATED, an activity-centre entry, a broadcast —
        # while still leaving the decision to a person. The load keeps
        # spoiling either way, but at least the system stops quietly waiting.
        self.ESCALATE_AFTER_SIM_MIN = float(
            __import__("os").getenv("ESCALATE_AFTER_SIM_MIN", "6") or 6)
        # incident_id -> multi-cause diagnosis, so the UI and the report can
        # show ranked alternatives without re-deriving them.
        self._diagnosis: dict[int, dict] = {}
        # incident_id -> derived lessons (requirement 12)
        self._lessons: dict[int, list[str]] = {}
        self.pending_approvals: dict[str, dict] = {}
        self.resolved_approvals: dict[str, dict] = {}
        self.event_ring: list[dict] = []
        self._task = None
        self.alert_counts: dict[str, int] = {}     # vehicle_id -> non-info alert count
        self._last_weather: str | None = None
        self._traffic_snap: dict[str, str] = {}
        self._geo_state: dict[str, str | None] = {}
        self._driver_state: dict[str, str] = {}
        import random as _r
        self._world_rng = _r.Random(42)

    # ---------------- dock / capacity accounting ----------------
    def _release_dock(self, facility_id: str, units: int, *, consumed: bool = False) -> None:
        """Free one dock and credit back the capacity a delivery consumed.

        `consumed=False` is the normal-delivery case: the load is handed over
        here, so the dock was never marked busy and only the capacity that this
        project deliberately reserved has to come back.

        `consumed=True` is the incident-rescue case: _check_arrival already
        decremented available_capacity and took a dock, so both are reversed.

        The dock is not freed instantly — it is held for `proc_min` (the
        facility's own unloading time), which is also what makes `queue_min`
        meaningful for a second arrival.
        """
        wh = next((w for w in self.warehouses if w["id"] == facility_id), None)
        if not wh:
            return
        if consumed:
            # Capacity comes back immediately: the load has been handed over.
            # The dock, though, stays occupied for proc_min — so ONLY the
            # capacity is credited here and the dock is released by
            # _expire_docks when the processing window closes. Doing both here
            # decremented busy_docks twice and drove it to zero, so the facility
            # looked idle while every truck was still unloading.
            wh["available_capacity"] = min(wh["capacity"], wh["available_capacity"] + units)
        self._dock_free_at[facility_id] = self.sim_minute + float(wh.get("proc_min", 10))

    def _expire_docks(self) -> None:
        """Called every tick: free any dock whose processing window has passed."""
        if not self._dock_free_at:
            return
        for fid, free_at in list(self._dock_free_at.items()):
            if self.sim_minute < free_at:
                continue
            self._dock_free_at.pop(fid, None)
            wh = next((w for w in self.warehouses if w["id"] == fid), None)
            if wh:
                wh["busy_docks"] = max(0, wh["busy_docks"] - 1)

    # ---------------- scenario configure / rebuild ----------------
    def configure(self, *, scenario_seed: int | None = None, weather: str | None = None,
                  traffic_intensity: float | None = None,
                  failure_probability: float | None = None, speed: float | None = None,
                  fleet_size: int | None = None) -> dict:
        """Rebuild the world: fresh TrafficWorld(seed, intensity), world-rng
        (spawn + autonomous failure dice), optional weather override.
        VehicleTwins keep their own per-vid rng; world-level randomness lives
        here — deterministic per seed, no RNG injected into twins."""
        s = self.scenario
        seed = int(s["seed"] if scenario_seed is None else scenario_seed)
        s.update({"seed": seed,
                  "weather": weather,  # None means stochastic (no override)
                  "traffic_intensity": float(1.0 if traffic_intensity is None else traffic_intensity),
                  "failure_probability": float(0.0 if failure_probability is None else failure_probability),
                  "fleet_size": int(s["fleet_size"] if fleet_size is None else fleet_size)})
        self.traffic = TrafficWorld(seed=seed, traffic_intensity=s["traffic_intensity"])
        if weather is not None:
            self.traffic.set_weather(weather)
        else:
            self.traffic.set_weather("NORMAL")
        import random as _r
        self._world_rng = _r.Random(seed)
        if speed is not None:
            self.set_speed(speed)
        return dict(s)

    async def rebuild(self, **kwargs) -> dict:
        """stop → configure → spawn → start with the scenario's fleet size."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        s = self.configure(**kwargs)
        await self.start(s["fleet_size"])
        return {"world_id": s["seed"], "vehicles": len(self.vehicles), "scenario": dict(s)}

    # ---------------- lifecycle ----------------
    async def start(self, n_vehicles: int = 12):
        """Explicit demo-world start: spawn the round-robin fleet + tick loop."""
        if self._task and not self._task.done():
            return
        self.n_vehicles = n_vehicles
        self._spawn_fleet()
        self.ensure_loop()

    def ensure_loop(self) -> None:
        """Start the world tick loop if it is not already running.

        Called before operator trucks are spawned so a COLD world (boot with
        FLEET_AUTOSTART off, nothing running) comes alive the moment the first
        truck is started. Without this, a twin spawned into a loop-less world
        would sit frozen — telemetry, movement and incidents all ride on _run.
        """
        if self._task and not self._task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no running loop (unit tests): ticks aren't needed there
        self._task = loop.create_task(self._run())
        log.info("fleet world loop started (cold start)")
        log.info("fleet started with %d vehicles", len(self.vehicles))

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    def set_speed(self, speed: float) -> float:
        return self.clock.set_speed(speed)

    def set_weather(self, weather: str) -> str:
        """Force a weather override (demo lever). Returns the applied state."""
        self.scenario["weather"] = weather
        return self.traffic.set_weather(weather)

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    # ---------------- living world: seeded autonomous failures ----------------
    async def _fail_world_tick(self) -> None:
        """Per world-tick, per cargo vehicle: world-rng < p → random failure.
        Default p=0 keeps capstone demos deterministic ("fail world rng" hook)."""
        p = float(self.scenario.get("failure_probability", 0.0))
        if p <= 0.0:
            return
        import random as _r
        kinds = ["compressor_failure", "compressor_degradation", "door_open",
                 "power_failure", "sensor_fault"]
        cargo = [v for v in self.vehicles.values() if is_cargo_vehicle(v)]
        if not cargo:
            return
        for v in cargo:
            if self._world_rng.random() < p:
                kind = kinds[self._world_rng.randrange(len(kinds))]
                v.inject_failure(kind)
                await self._evt(v, f"Living world: {kind} on {v.id}", "critical")
                await BROADCAST.emit(0, "vehicle.failure.injected",
                                     {"vehicle_id": v.id, "failure": kind,
                                      "source": "living_world"})

    # ---------------- fleet spawning ----------------
    def _spawn_fleet(self):
        # fresh world: reset per-world tracking so a same-seed rebuild re-emits
        # spawn-time zone entries, weather diffs, and alert counts
        self._geo_state = {}
        self._driver_state = {}
        self._over_run = {}
        self.incident_db = {}
        self._incident_tel = {}
        self.alert_counts = {}
        self._traffic_snap = {}
        self._last_weather = None
        self.sim_minute = 0.0
        self._tick_n = 0
        self.vehicles = {}
        rng = self._world_rng
        pairs = [(o, d) for (o, d) in POLYLINES.keys()]
        for i in range(self.n_vehicles):
            o, d = pairs[i % len(pairs)]
            # flip direction for odd indices to spread traffic both ways
            if i % 2:
                o, d = d, o
            cargo = CARGO_TYPES[i % len(CARGO_TYPES)]
            # filter pairs to cargo-compatible destination when possible
            if o.startswith("WH") and d.startswith("D"):
                dest = next(x for x in DESTINATIONS if x["id"] == d)
                if cargo not in dest["required_cargo"]:
                    cargo = dest["required_cargo"][0]
            route = self.routing.calculate_route(o, d, 1.0)
            energy = "ELECTRIC" if i % 5 == 0 else ("HYBRID" if i % 7 == 0 else "DIESEL")
            vid = f"TRUCK-{rng.randrange(10000):04d}-{i:02d}"
            self.vehicles[vid] = VehicleTwin(
                vid, "REFRIGERATED_TRUCK" if energy != "ELECTRIC" else "EV_REEFER",
                energy, DRIVERS[i % len(DRIVERS)], cargo,
                load_units=200 + ((i * 137) % 600), capacity_units=1000,
                origin_id=o, dest_id=d, route=route, seed=rng.randrange(10 ** 9))
        # service vehicles: zero cargo, wide thermal band (never trips risk)
        # exact same origin/dest unpack as cargo vehicles — no tuple bugs
        for j in range(2):
            o, d = pairs[(j + 5) % len(pairs)] if j else pairs[0]
            route = self.routing.calculate_route(o, d, 1.0)
            svc = VehicleTwin(f"SERVICE-{rng.randrange(9000) + 1000}-{j}", "SERVICE_TRUCK", "ELECTRIC",
                              "Mechanic", "pharma", 0, 100, o, d, route,
                              seed=rng.randrange(10 ** 9))
            svc.box = Engine(target=20.0, mn=-40.0, mx=60.0, hum_min=10.0, hum_max=95.0,
                             seed=svc.seed)
            self.vehicles[svc.id] = svc
        self.service_tasks: dict[str, str] = {}   # service vid -> target vid
        self.service_pending: dict[str, str] = {}  # target vid -> task type
        self._service_retarget_at: dict[str, float] = {}
        self.transfers: dict[str, dict] = {}       # donor vid -> transfer state

    # ---------------- manual dispatch fleet (user-defined trucks) ----------------
    #
    # The auto-spawned fleet above is round-robin over POLYLINES/CARGO_TYPES and
    # is what the capstone demo runs on. It is left completely untouched.
    #
    # Alongside it, the operator manages a DYNAMIC fleet of hand-configured
    # trucks — explicit product and explicit destination, added and removed
    # one at a time from the UI. Those live in `self.dispatch` rather than in
    # `self.vehicles` so that:
    #   * resetting the demo fleet cannot silently delete a configured truck,
    #   * the two populations stay distinguishable in /api/fleet/state,
    #   * each configured truck carries its own product/destination spec that a
    #     panel can read back.
    #
    # A configured truck is spawned into `self.vehicles` when the operator
    # starts the run, so it moves, emits telemetry, raises incidents and can be
    # rescued through exactly the same code path as any other vehicle. There is
    # no second movement or thermal implementation.

    # The cap is a presentation limit, not a technical one: the tick loop,
    # state payload and map already run the 12-truck demo fleet, and `rebuild`
    # accepts up to 60. 12 keeps the management panel readable while allowing
    # a real multi-truck demonstration. Enforced with a 400 + readable reason
    # (never silently) and exposed to the UI via GET /api/fleet/dispatch → max.
    DISPATCH_MAX = 12

    def _dispatch_specs(self) -> list[dict]:
        """Specs plus live status, so the UI can render Not Started / Running /
        Arrived without a second request."""
        out: list[dict] = []
        for s in self.dispatch:
            d = dict(s)
            vid = d.get("vehicle_id")
            if vid and vid in self.vehicles:
                d["status"] = self.vehicles[vid].snapshot().get("status", "RUNNING")
                d["running"] = True
            else:
                d["status"] = "NOT_STARTED"
                d["running"] = False
            out.append(d)
        return out

    def _next_dispatch_id(self) -> str:
        self._dispatch_seq += 1
        return f"T{self._dispatch_seq:02d}"

    def _spec_with_status(self, truck: dict) -> dict:
        """One spec with live status attached (same shape as _dispatch_specs)."""
        d = dict(truck)
        vid = d.get("vehicle_id")
        if vid and vid in self.vehicles:
            d["status"] = self.vehicles[vid].snapshot().get("status", "RUNNING")
            d["running"] = True
        else:
            d["status"] = "NOT_STARTED"
            d["running"] = False
        return d

    def _validate_dispatch_spec(self, s: dict, used_dests: set[str]) -> dict:
        """Validate one truck definition; returns the cleaned spec.

        Raises ValueError with a human-readable reason on anything the
        simulation cannot honour, so the API can return 400 instead of
        silently substituting a random product or destination — which is the
        exact failure mode this feature exists to remove.
        """
        name = (s.get("name") or "").strip()[:40]
        cargo = (s.get("cargo_type") or "").strip()
        dest = (s.get("destination_id") or "").strip()
        origin = (s.get("origin_id") or "").strip() or None

        if not name:
            raise ValueError("truck name is required")
        known_cargo = set(CARGO_TYPES) | {"pharmaceutical"}
        known_nodes = {w["id"] for w in self.warehouses} | {d["id"] for d in DESTINATIONS}
        if not cargo:
            raise ValueError(f"{name}: product is required")
        if cargo not in known_cargo:
            raise ValueError(f"{name}: unknown product '{cargo}'. "
                             f"Choose one of {sorted(known_cargo)}")
        if not dest:
            raise ValueError(f"{name}: destination warehouse is required")
        if dest not in known_nodes:
            raise ValueError(f"{name}: unknown destination '{dest}'. "
                             f"Choose one of {sorted(known_nodes)}")
        if dest in used_dests:
            raise ValueError(f"{name}: destination {dest} is already used by "
                             f"another truck in this run")
        used_dests.add(dest)

        # Destination compatibility is CHECKED, not silently rewritten. The
        # auto-spawn path overwrites an incompatible cargo (line ~228); doing
        # that here would defeat the point of a user-defined product.
        if dest.startswith("D"):
            dnode = next((x for x in DESTINATIONS if x["id"] == dest), None)
            if dnode and cargo not in dnode["required_cargo"]:
                raise ValueError(
                    f"{name}: {dest} only accepts "
                    f"{sorted(dnode['required_cargo'])}, not '{cargo}'")

        try:
            load = int(s.get("load_units") or 400)
        except (TypeError, ValueError):
            raise ValueError(f"{name}: load_units must be a whole number")
        if not 1 <= load <= 1000:
            raise ValueError(f"{name}: load_units must be between 1 and 1000")

        return {
            "name": name,
            "cargo_type": cargo,
            "destination_id": dest,
            "origin_id": origin,
            "load_units": load,
        }

    def add_dispatch_truck(self, spec: dict | None = None) -> dict:
        """Create one truck and return it, without starting anything.

        A fresh truck is a DRAFT: no product, no destination, no route, no
        twin in the world. The operator chooses every field explicitly; the
        only automatic assignment is the unique id (T01, T02, …) and a
        non-colliding display name, both of which can be renamed afterwards.
        """
        if len(self.dispatch) >= self.DISPATCH_MAX:
            raise ValueError(f"fleet is full: at most {self.DISPATCH_MAX} trucks "
                             f"can be managed at once (already have {len(self.dispatch)})")
        spec = dict(spec or {})
        tid = self._next_dispatch_id()
        taken_names = {s["name"] for s in self.dispatch}
        n = self._dispatch_seq
        while f"Truck {n:02d}" in taken_names:
            n += 1
        truck: dict = {"id": tid, "name": spec.get("name") or f"Truck {n:02d}",
                       "cargo_type": "", "destination_id": "", "origin_id": None,
                       "load_units": 400, "vehicle_id": None}
        # Honour any fields the caller supplied up front. Product/destination
        # are a PAIR: accepting one without the other would leave a half-typed
        # truck that looks configured, and defaulting the missing half is the
        # automatic assignment this module exists to prevent.
        patch = {k: spec[k] for k in ("name", "cargo_type", "destination_id",
                                      "origin_id", "load_units") if spec.get(k) is not None}
        if "load_units" in patch:
            try:
                load = int(patch.pop("load_units"))
            except (TypeError, ValueError):
                raise ValueError("load_units must be a whole number")
            if not 1 <= load <= 1000:
                raise ValueError("load_units must be between 1 and 1000")
            truck["load_units"] = load
        if "origin_id" in patch:
            truck["origin_id"] = (str(patch.pop("origin_id") or "")).strip() or None
        if "name" in patch:
            truck["name"] = str(patch.pop("name")).strip()[:40] or truck["name"]
        if patch:
            if not (patch.get("cargo_type") and patch.get("destination_id")):
                raise ValueError("choose both a product and a destination — "
                                 "nothing is assigned automatically")
            used = {s["destination_id"] for s in self.dispatch if s.get("destination_id")}
            truck.update(self._validate_dispatch_spec({**truck, **patch}, used))
        self.dispatch.append(truck)
        return self._spec_with_status(truck)

    def update_dispatch_truck(self, tid: str, patch: dict) -> dict:
        """Configure one truck by id. Merges the patch and revalidates.

        An empty product or destination in the patch CLEARS that field (back
        to draft) rather than failing — that is how the UI lets the operator
        change the product without the old destination blocking the edit.
        A full pair is revalidated exactly like any other configuration.

        Product/destination changes are refused while the truck is running —
        the twin already has a route and cargo; silently rewiring it mid-trip
        is exactly the automatic behaviour this module exists to prevent. The
        operator removes and re-adds (or waits for arrival) to change them.
        """
        truck = next((s for s in self.dispatch if s["id"] == tid), None)
        if truck is None:
            raise ValueError(f"no truck with id {tid}")
        patch = {k: v for k, v in dict(patch).items()
                 if k in ("name", "cargo_type", "destination_id", "origin_id", "load_units")}
        running = bool(truck.get("vehicle_id") and truck["vehicle_id"] in self.vehicles)
        # "" = clear the field (back to draft), never a value to store.
        # A running truck cannot be un-configured: its twin already carries
        # the product and route the operator chose.
        if running and any(k in patch and str(patch[k]).strip() == ""
                           for k in ("cargo_type", "destination_id")):
            raise ValueError(f"{truck['name']} is currently in delivery — remove it "
                             f"or wait for arrival before changing product/destination")
        for k in ("cargo_type", "destination_id"):
            if k in patch and str(patch[k]).strip() == "":
                truck[k] = ""
                patch.pop(k)
        if "origin_id" in patch and str(patch["origin_id"] or "").strip() == "":
            truck["origin_id"] = None
            patch.pop("origin_id")
        if running and (
                (patch.get("cargo_type") and patch["cargo_type"] != truck["cargo_type"]) or
                (patch.get("destination_id") and patch["destination_id"] != truck["destination_id"])):
            raise ValueError(f"{truck['name']} is currently in delivery — remove it "
                             f"or wait for arrival before changing product/destination")
        merged = {**truck, **patch}
        if "name" in patch:
            merged["name"] = str(patch["name"]).strip()[:40] or truck["name"]
        if "load_units" in patch:
            try:
                merged["load_units"] = int(patch["load_units"])
            except (TypeError, ValueError):
                raise ValueError(f"{truck['name']}: load_units must be a whole number")
        if merged.get("cargo_type") and merged.get("destination_id"):
            # full pair present: validate like any other configuration
            used = {s["destination_id"] for s in self.dispatch
                    if s.get("destination_id") and s["id"] != tid}
            merged.update(self._validate_dispatch_spec(merged, used))
        truck.update(merged)
        return self._spec_with_status(truck)

    def start_dispatch_truck(self, tid: str) -> dict:
        """Spawn ONE configured truck into the live world.

        Refuses a draft (missing product or destination) with a readable 400 —
        the operator decides when a truck starts; nothing is started for them.
        Idempotent: starting a running truck returns its current twin.
        """
        truck = next((s for s in self.dispatch if s["id"] == tid), None)
        if truck is None:
            raise ValueError(f"no truck with id {tid}")
        if truck.get("vehicle_id") and truck["vehicle_id"] in self.vehicles:
            return {"started": [truck["vehicle_id"]], "already_running": True,
                    "trucks": self._dispatch_specs()}
        if not truck.get("cargo_type") or not truck.get("destination_id"):
            raise ValueError(f"{truck['name']} is not configured — choose a product "
                             f"and a destination before starting the delivery")
        # a cold world must come alive when the operator starts its first truck
        self.ensure_loop()
        vid = self._spawn_dispatch_twin(truck)
        return {"started": [vid], "already_running": False,
                "trucks": self._dispatch_specs()}

    async def remove_dispatch_truck(self, tid: str) -> dict:
        """Remove one truck and ONLY that truck.

        If it was started, the twin and every per-vehicle simulation state
        (incident, alert counters, service call, pending approval) are cleaned
        up here; other trucks are untouched. Historical report data in the
        database (Incident/AIAnalysis/RecommendedAction rows) is deliberately
        preserved — deletion removes the truck from the live fleet, it does not
        rewrite the reports.
        """
        truck = next((s for s in self.dispatch if s["id"] == tid), None)
        if truck is None:
            raise ValueError(f"no truck with id {tid}")
        vid = truck.get("vehicle_id")
        if vid:
            await self._remove_vehicle_state(vid)
        self.dispatch = [s for s in self.dispatch if s["id"] != tid]
        return {"removed": tid, "vehicle_id": vid,
                "trucks": self._dispatch_specs()}

    async def _remove_vehicle_state(self, vid: str) -> None:
        """Drop a vehicle twin and everything that hangs off its id.

        Only live/in-memory state is cleared: incident_db (the active incident
        mapping), escalation counters, alert counters, geofence/driver/traffic
        display caches, an in-flight service call and pending approvals raised
        by this truck. DB rows stay, so /reports keeps its history.
        """
        self.vehicles.pop(vid, None)
        self.incident_db.pop(vid, None)
        self._over_run.pop(vid, None)
        self.alert_counts.pop(vid, None)
        self._geo_state.pop(vid, None)
        self._driver_state.pop(vid, None)
        self._traffic_snap.pop(vid, None)
        self.transfers.pop(vid, None)
        task = self.service_pending.pop(vid, None)
        if task:
            # the dispatched service truck must not keep driving at a ghost
            for svc_id, tgt in list(self.service_tasks.items()):
                if tgt == vid:
                    self.service_tasks.pop(svc_id, None)
        for key, p in list(self.pending_approvals.items()):
            if p.get("vehicle_id") == vid:
                self.pending_approvals.pop(key, None)
        await BROADCAST.emit(0, "vehicle.removed",
                             {"vehicle_id": vid, "reason": "removed_by_operator"})

    def configure_dispatch(self, specs: list[dict]) -> dict:
        """Validate and store the operator's truck definitions (bulk path).

        The per-truck add/update/remove endpoints are the primary interface
        now; this bulk replace is kept for compatibility with the demo
        recorder and existing callers. Raises ValueError with a human-readable
        reason on anything the simulation cannot honour.
        """
        if not specs:
            raise ValueError("at least one truck is required")
        if len(specs) > self.DISPATCH_MAX:
            raise ValueError(f"at most {self.DISPATCH_MAX} trucks can be dispatched "
                             f"at once (got {len(specs)})")

        cleaned: list[dict] = []
        used: set[str] = set()
        for s in specs:
            c = self._validate_dispatch_spec(s, used)
            c["id"] = self._next_dispatch_id()
            c["vehicle_id"] = None
            cleaned.append(c)

        self.dispatch = cleaned
        return {"trucks": self._dispatch_specs(), "count": len(cleaned)}

    async def clear_dispatch(self) -> dict:
        """Clear the plan AND any trucks already spawned from it.

        Previously this only dropped the spec list, leaving started trucks
        driving around with no spec behind them — orphaned twins no panel
        could configure or remove.
        """
        for s in list(self.dispatch):
            vid = s.get("vehicle_id")
            if vid:
                await self._remove_vehicle_state(vid)
        self.dispatch = []
        return {"trucks": [], "count": 0}

    def start_dispatch(self) -> dict:
        """Spawn all configured trucks into the live world (bulk path).

        Drafts are skipped, not started by accident: only trucks with an
        explicit product AND destination are spawned.
        """
        if not self.dispatch:
            raise ValueError("no trucks configured — define them first")

        # a cold world must come alive when the operator starts its first trucks
        self.ensure_loop()
        started: list[str] = []
        for s in self.dispatch:
            if not s.get("cargo_type") or not s.get("destination_id"):
                continue
            started.append(self._spawn_dispatch_twin(s))
        return {"started": started, "count": len(started),
                "trucks": self._dispatch_specs()}

    def _spawn_dispatch_twin(self, s: dict) -> str:
        """Create the VehicleTwin for one configured truck. Shared by the
        per-truck and bulk start paths so there is no second spawn logic."""
        dest = s["destination_id"]
        origin = s.get("origin_id") or self._origin_for(dest, s.get("cargo_type"))
        route = self.routing.calculate_route(origin, dest, 1.0)
        vid = f"USER-{s['id']}"
        # replace any previous twin with this id (re-start is idempotent)
        self.vehicles.pop(vid, None)
        twin = VehicleTwin(
            vid, "REFRIGERATED_TRUCK", "DIESEL", s["name"],
            s["cargo_type"],
            load_units=int(s["load_units"]), capacity_units=1000,
            origin_id=origin, dest_id=dest, route=route,
            seed=self._world_rng.randrange(10 ** 9))
        # Mark it so the UI and the state payload can tell configured trucks
        # from the round-robin demo fleet.
        twin.user_defined = True
        twin.display_name = s["name"]
        self.vehicles[vid] = twin
        s["vehicle_id"] = vid
        return vid

    def _origin_for(self, dest: str, cargo: str | None = None) -> str:
        """Pick a sensible origin node for a hand-configured truck.

        Prefers a warehouse that stocks the product, so the load is coherent
        with the simulation rather than starting from an unrelated node.
        Falls back to any other warehouse.
        """
        wanted = {cargo} if cargo else {s.get("cargo_type") for s in self.dispatch}
        for w in self.warehouses:
            if w["id"] == dest:
                continue
            if wanted & set(w.get("cargo_types") or []):
                return w["id"]
        for w in self.warehouses:
            if w["id"] != dest:
                return w["id"]
        return "WH-001"

    # ---------------- main loop ----------------
    async def _run(self):
        try:
            while True:
                await asyncio.sleep(0.25)
                if self.paused:
                    continue
                dt = self.clock.dt_sim_min()
                if dt <= 0:
                    continue
                self.sim_minute += dt
                self._tick_n += 1
                if self._tick_n % 2400 == 0:
                    await self._prune_events()
                self.traffic.maybe_weather()
                await self._fail_world_tick()
                self._expire_docks()          # free docks whose processing window closed
                await self._expire_approvals()   # auto-approve stale recommendations
                await self._escalate_unanswered()  # agent flags critical items nobody actioned
                snaps = []
                for vid, v in list(self.vehicles.items()):
                    factor = self.traffic.factor_for(v.origin_id, v.dest_id)
                    v.sim_minute = self.sim_minute
                    s = v.step(dt, factor, self.traffic.ambient_c)
                    # per-incident telemetry deep-copy (survives respawns)
                    iid = self.incident_db.get(v.id)
                    if iid is not None:
                        self._incident_tel.setdefault(iid, []).append(
                            dict(v._tel[-1]) if v._tel else
                            {"min": round(self.sim_minute, 2), "speed": 0, "temp": 0,
                             "humidity": 0, "energy": 0, "cargo_health": 0, "risk": 0})
                        if len(self._incident_tel[iid]) > 2400:
                            self._incident_tel[iid] = self._incident_tel[iid][-2400:]
                    delta = v.alerts_delta()
                    if delta:
                        self.alert_counts[v.id] = self.alert_counts.get(v.id, 0) + delta
                        s["alerts_new"] = delta
                    # Attach the safe-remaining-time projection HERE, at the point
                    # the tick builds its snapshot — not only in state().
                    #
                    # This was the reason the predictive panel never appeared in
                    # the telemetry drawer: state() attached the projection, but
                    # the per-tick `vehicle.position.updated` frame did not. The
                    # frontend store maps that frame to the same `fleet` action as
                    # the REST poll, so every WebSocket tick overwrote the polled
                    # state and stripped the prediction back off. Whichever
                    # arrived last won, and the socket won — roughly twice a
                    # second. The dashboard banner was unaffected only because it
                    # fetches /api/fleet/predictions directly instead of reading
                    # the store.
                    s["prediction"] = PRED.project(s, self._incident_ctx(v))
                    snaps.append(s)
                    await self._check_incident(v, s)
                    await self._check_arrival(v)
                    await self._check_geofence(v)
                    await self._check_idling(v, s)
                # weather / traffic world events
                w = self.traffic.maybe_weather()
                if w != self._last_weather:
                    first = self._last_weather is None
                    self._last_weather = w
                    if not first:
                        await BROADCAST.emit(0, "weather.changed",
                                             {"weather": w, "ambient_c": self.traffic.ambient_c})
                        await self._evt(None, f"Weather changed to {w} "
                                          f"(ambient {self.traffic.ambient_c}C)", "warning")
                if self._tick_n % 40 == 0:
                    for seg, lvl in self.traffic.segments.items():
                        if self._traffic_snap.get(seg) != lvl:
                            self._traffic_snap[seg] = lvl
                            await BROADCAST.emit(0, "traffic.changed",
                                                 {"segment": seg, "level": lvl})
                # aggregated position update every world tick
                await BROADCAST.emit(0, "vehicle.position.updated",
                                     {"vehicles": snaps, "sim_minute": round(self.sim_minute, 2),
                                      "weather": self.traffic.weather,
                                      "ambient_c": self.traffic.ambient_c})
                if self._tick_n % 20 == 0:
                    await self._persist_vehicles(snaps)
                self._service_progress(dt)
        except asyncio.CancelledError:
            log.info("fleet loop cancelled")
        except Exception as e:
            log.exception("fleet loop unhandled error: %s", e)

    # ---------------- geofence checks ----------------
    async def _check_idling(self, v: VehicleTwin, snap: dict):
        """Emit vehicle.idling / vehicle.stopped on the corresponding state transition."""
        dstate = snap["driver"]["state"]
        prev = self._driver_state.get(v.id)
        if dstate == prev:
            return
        self._driver_state[v.id] = dstate
        if dstate == "IDLE":
            await BROADCAST.emit(0, "vehicle.idling",
                                 {"vehicle_id": v.id, "sim_minute": round(self.sim_minute, 2),
                                  "idle_min": round(v.idle_min, 1)})
        elif prev == "IDLE" and dstate == "DRIVING":
            await BROADCAST.emit(0, "vehicle.stopped",
                                 {"vehicle_id": v.id, "sim_minute": round(self.sim_minute, 2)})

    async def _check_geofence(self, v: VehicleTwin):
        from .geo_data import geofence_for
        cur = geofence_for(v.lat, v.lng)
        prev = self._geo_state.get(v.id)
        if cur != prev:
            self._geo_state[v.id] = cur
            if cur is not None:
                await BROADCAST.emit(0, "geofence.entered",
                                     {"vehicle_id": v.id, "fence": cur["id"], "fence_type": cur["type"]})
                sev = "warning" if cur["type"] == "RESTRICTED" else "info"
                await self._evt(v, f"{v.id} entered {cur['type']} zone {cur['id']}", sev)
            elif prev is not None:
                await BROADCAST.emit(0, "geofence.exited",
                                     {"vehicle_id": v.id, "fence": prev["id"], "fence_type": prev["type"]})

    # ---------------- incidents ----------------
    def _incident_ctx(self, v: VehicleTwin) -> dict:
        """Run-level signals a single snapshot cannot see.

        Traffic severity and ambient temperature are world state, not vehicle
        state — which is exactly why ambient heat can be told apart from a
        compressor fault only when both are considered together.
        """
        node = nearest_node(v.lng, v.lat)
        return {
            "traffic_level": self.traffic.level_for(node, v.dest_id),
            "ambient_c": self.traffic.ambient_c,
            "weather": self.traffic.weather,
        }

    async def _check_incident(self, v: VehicleTwin, snap: dict):
        over = snap["refrigeration"]["temperature"] > v.box.mx or \
               snap["refrigeration"]["temperature"] < v.box.mn
        run = self._over_run.get(v.id, 0)
        run = run + 1 if over else 0
        self._over_run[v.id] = run
        if run >= SUSTAIN_TICKS and v.id not in self.incident_db:
            sev = "CRITICAL" if snap["cargo"]["risk_level"] == "CRITICAL" else "HIGH"
            await self._create_incident(v, snap, sev)

    async def _create_incident(self, v: VehicleTwin, snap: dict, sev: str):
        # Classify against the catalogue rather than a five-way ternary, so the
        # incident records which kind of failure it was instead of collapsing
        # every cause into "vehicle_thermal_excursion". See
        # incidents_catalogue.py for why each detector reads only real signals.
        hit = IC.detect(snap, self._incident_ctx(v))
        if hit:
            inc_type = hit["type"]
            cause = hit["cause"]
            evidence = hit["evidence"]
        else:
            # Should not happen — _check_incident only calls this once the box is
            # out of band — but never drop an incident silently.
            inc_type = "temperature_excursion"
            cause = "unclassified thermal excursion"
            evidence = [f"cargo {snap['refrigeration']['temperature']}C"]
        async with SessionLocal() as s:
            inc = Incident(simulation_id=0, type=inc_type, severity=sev,
                           status="DETECTED", detected_tick=int(self.sim_minute),
                           root_cause=cause[:60],
                           description=f"{v.id}: cargo temp {snap['refrigeration']['temperature']}C "
                                       f"outside band [{v.box.mn},{v.box.mx}]C in transit",
                           peak_temperature=snap["refrigeration"]["temperature"])
            s.add(inc)
            await s.commit()
            iid = inc.id
        self.incident_db[v.id] = iid
        # Persist the evidence trail so the report and the incident panel can
        # show WHY this classification was chosen, not just its label.
        async with SessionLocal() as s:
            s.add(AIAnalysis(incident_id=iid, agent_name="incident_classifier",
                            analysis=json.dumps({"type": inc_type, "cause": cause,
                                                 "evidence": evidence,
                                                 "catalogue_category": (hit or {}).get("category")})[:4000],
                            confidence=1.0))
            await s.commit()

        # Multi-cause analysis. The catalogue classifies WHAT happened; this
        # answers WHY, and returns ranked alternatives with reasoning rather
        # than a single cause. Reuses agents_d.DiagnosisAgent via an adapter,
        # so the fleet and the classic path share one diagnosis implementation.
        diagnosis = IC.diagnose(snap, list(getattr(v, "_snaps", []))[-8:],
                                self._incident_ctx(v))
        async with SessionLocal() as s:
            s.add(AIAnalysis(incident_id=iid, agent_name="diagnosis",
                            analysis=json.dumps(diagnosis)[:4000],
                            confidence=diagnosis.get("confidence", 0.5)))
            await s.commit()
        self._diagnosis[iid] = diagnosis
        await self._evt(v, f"Incident detected on {v.id}: {cause} — temp "
                          f"{snap['refrigeration']['temperature']}C", "critical")
        await BROADCAST.emit(0, "fleet.incident.created",
                             {"vehicle_id": v.id, "incident_id": iid, "severity": sev,
                              "root_cause": cause, "incident_type": inc_type,
                              "evidence": evidence,
                              "diagnosis": diagnosis,
                              "snapshot": snap,
                              "sim_minute": round(self.sim_minute, 1)})
        task = asyncio.create_task(self._decide(v))

        async def _guarded():
            try:
                await task
            except Exception as e:
                log.exception("fleet AI decision crashed for %s: %s", v.id, e)
                await BROADCAST.emit(0, "ai.analysis.failed",
                                     {"agent": "fleet_coordinator", "vehicle_id": v.id, "error": str(e)})
        asyncio.create_task(_guarded())

    async def _decide(self, v: VehicleTwin):
        await BROADCAST.emit(0, "ai.analysis.started",
                             {"agent": "fleet_coordinator", "vehicle_id": v.id})
        bundle = self.coordinator.evaluate(v, self.traffic, v.dest_id)
        async with SessionLocal() as s:
            s.add(RouteDecision(vehicle_id=v.id, decision=bundle["decision"],
                                recommended=json.dumps({"target": bundle.get("target"),
                                                        "scored": bundle.get("scored", {}),
                                                        "candidates": bundle.get("candidates", [])[:4]})[:4000],
                                reason=bundle["reason"][:2000],
                                confidence=bundle.get("confidence", 0.0),
                                sim_minute=self.sim_minute))
            await s.commit()
        await BROADCAST.emit(0, "ai.route.decision",
                             {"agent": "fleet_coordinator", "vehicle_id": v.id,
                              "incident_id": self.incident_db.get(v.id),
                              **{k: bundle[k] for k in ("decision", "target", "reason", "confidence",
                                                       "scored", "candidates", "options") if k in bundle}})
        await self._evt(v, f"AI {bundle['decision']} -> {bundle.get('target', v.dest_id)}: "
                          f"{bundle['reason'][:120]}", "warning")

        if bundle["decision"] != "DIVERT":
            return

        # --- human-in-the-loop gate -------------------------------------
        # A DIVERT changes where a load is going and which warehouse consumes
        # capacity, so it waits for a person. Before this, `_autonomous=True`
        # applied it inline and the operator only ever saw it after the fact.
        #
        # Two escape hatches, both explicit rather than implicit:
        #   * `_autonomous` still applies immediately (used by the demo flow and
        #     by tests that assert the divert actually happens),
        #   * AUTO_APPROVE_TIMEOUT_S lets an unattended run continue after a
        #     grace period instead of stalling forever.
        # Service dispatch is NOT gated: repairing a compressor is restorative,
        # not a routing commitment, and the brief chose to keep it automatic.
        if not self.approval_required(bundle):
            if self._autonomous:
                await self._apply_divert(v, bundle)
            return

        await self._queue_for_approval(v, bundle)

    def approval_required(self, bundle: dict) -> bool:
        """Should this decision wait for a human?

        Diverts always wait. `self.require_approval` is the master switch so a
        demonstration can be run either way from one place.
        """
        if not self.require_approval:
            return False
        return bundle.get("decision") == "DIVERT"

    async def _queue_for_approval(self, v: VehicleTwin, bundle: dict):
        """Record the recommendation and surface it. Nothing is applied yet."""
        incident_id = self.incident_db.get(v.id)
        key = f"{v.id}:{bundle.get('target')}:{int(self.sim_minute)}"
        proposal = {
            "key": key,
            "vehicle_id": v.id,
            "vehicle_name": getattr(v, "display_name", None) or v.id,
            "incident_id": incident_id,
            "decision": "DIVERT",
            "target": bundle.get("target"),
            "current_destination": v.dest_id,
            "reason": bundle.get("reason", ""),
            "confidence": bundle.get("confidence", 0.0),
            "score": (bundle.get("scored") or {}).get("score"),
            "scored": bundle.get("scored", {}),
            "candidates": bundle.get("candidates", [])[:4],
            "options": bundle.get("options", []),
            "cargo_type": v.cargo_type,
            "load_units": v.load_units,
            "temperature": round(v.box.temperature, 2),
            "cargo_health": round(v.box.cargo_health, 1),
            "raised_at_sim_minute": round(self.sim_minute, 1),
            "status": "PENDING",
            # Carried here because _escalate_unanswered() decides on the cargo
            # verdict and the incident severity. Without them the escalation
            # gate had nothing to read and would never fire.
            "severity": ("CRITICAL" if v.snapshot()["cargo"]["risk_level"] == "CRITICAL"
                         else "HIGH" if incident_id else "MEDIUM"),
            "prediction": PRED.project(v.snapshot(), self._incident_ctx(v)),
            "escalated": False,
        }
        self.pending_approvals[key] = proposal
        async with SessionLocal() as s:
            inc = await s.get(Incident, incident_id) if incident_id else None
            # recommended_actions.incident_id is NOT NULL, so a recommendation
            # raised before any Incident row exists cannot be persisted there.
            # The in-memory queue is the source of truth for the operator; the DB
            # row is written only once there is an incident to attach it to. The
            # proposal is therefore still shown and still actionable — it just
            # is not double-recorded.
            if incident_id:
                s.add(RecommendedAction(
                    incident_id=incident_id, action="reroute",
                    label=f"Divert {proposal['vehicle_name']} to {proposal['target']}",
                    priority="HIGH",
                    reason=proposal["reason"][:500],
                    expected_effect=f"Arrive at {proposal['target']} with cargo at "
                                    f"{proposal['temperature']}C",
                    status="PENDING"))
            if inc and inc.status == "DETECTED":
                inc.status = "AWAITING_APPROVAL"
            await s.commit()
        await BROADCAST.emit(0, "ai.approval.requested", proposal)
        await self._evt(v, f"AI recommends divert to {proposal['target']} — "
                           f"waiting for operator approval", "warning")

    async def resolve_approval(self, key: str, approve: bool, note: str = "") -> dict:
        """Operator decision on a queued recommendation.

        `approve=False` is a first-class outcome, not an error: the load keeps
        running to its planned destination and the rejection is recorded so the
        report can show that a human chose differently from the agent.
        """
        prop = self.pending_approvals.get(key)
        already_resolved = self.resolved_approvals.get(key)
        if not prop:
            # tolerate a stale key from a client that reloaded mid-decision
            for k, p in self.pending_approvals.items():
                if p["vehicle_id"] == key:
                    key, prop = k, p
                    break
        if not prop:
            # A double-clicked Approve must not look like a failure. The decision
            # was already recorded and already applied, so return it as-is.
            if already_resolved is not None:
                return already_resolved
            for p in self.resolved_approvals.values():
                if p["vehicle_id"] == key:
                    return p
            raise KeyError("no pending approval with that key")
        if prop["status"] != "PENDING":
            return prop  # idempotent: approving twice must not double-apply

        prop["status"] = "APPROVED" if approve else "REJECTED"
        prop["resolved_at_sim_minute"] = round(self.sim_minute, 1)
        prop["note"] = note
        self.resolved_approvals[key] = prop
        self.pending_approvals.pop(key, None)

        v = self.vehicles.get(prop["vehicle_id"])
        if approve and v is not None:
            await self._apply_divert(v, prop)
        else:
            await self._evt(v, f"Operator REJECTED divert to {prop['target']}"
                               f"{(' — ' + note) if note else ''}", "warning")

        async with SessionLocal() as s:
            rows = await s.execute(
                select(RecommendedAction).where(
                    RecommendedAction.incident_id == prop["incident_id"],
                    RecommendedAction.status == "PENDING"))
            for row in rows.scalars().all():
                row.status = "EXECUTED" if approve else "SKIPPED"
                row.executed_at = datetime.utcnow() if approve else None
            inc = await s.get(Incident, prop["incident_id"]) if prop["incident_id"] else None
            if inc and inc.status == "AWAITING_APPROVAL":
                inc.status = "RECOVERING" if approve else "MONITORING"
            await s.commit()
        await BROADCAST.emit(0, "ai.approval.resolved",
                             {"key": key, "approved": approve,
                              "vehicle_id": prop["vehicle_id"],
                              "target": prop["target"], "note": note})
        return prop

    async def _expire_approvals(self):
        """Auto-approve past the grace period so an unattended run continues."""
        if not self.pending_approvals or self.AUTO_APPROVE_TIMEOUT_S <= 0:
            return
        for key, prop in list(self.pending_approvals.items()):
            waited = self.sim_minute - prop["raised_at_sim_minute"]
            if waited < self.AUTO_APPROVE_TIMEOUT_S:
                continue
            try:
                await self.resolve_approval(key, True, note="auto-approved: no operator response")
            except KeyError:
                continue

    async def _escalate_unanswered(self):
        """Escalate CRITICAL recommendations nobody acted on (requirement 15).

        The brief is explicit: warn first, and if no reply comes, let the agent
        flag it itself. Before this, a critical recommendation with no operator
        response simply sat in the queue indefinitely — the agent asked for help
        and then gave up quietly, which is the worst of both worlds.

        Escalation deliberately does NOT execute the divert. AUTO_APPROVE_
        TIMEOUT_S already covers "run unattended" and it applies the action;
        escalating is for the case where a human is present but has not
        responded. So this raises the alarm and leaves the decision alone:

          * incident status  DETECTED -> ESCALATED
          * an activity-centre entry saying the agent is flagging it itself
          * fleet.incident.escalated broadcast so the UI can highlight it
          * the approval stays pending and still actionable

        Only CRITICAL/ESCALATED-severity items escalate. A LOW-severity
        suggestion left unanswered is not an emergency, and nagging about it
        would train an operator to ignore the queue.
        """
        if not self.pending_approvals or self.ESCALATE_AFTER_SIM_MIN <= 0:
            return
        for key, prop in list(self.pending_approvals.items()):
            if prop.get("escalated"):
                continue
            waited = self.sim_minute - prop["raised_at_sim_minute"]
            if waited < self.ESCALATE_AFTER_SIM_MIN:
                continue

            incident_id = prop.get("incident_id")
            severity = (prop.get("severity") or "MEDIUM").upper()
            # Critical cargo risk, or an incident already at ESCALATED.
            pred = prop.get("prediction") or {}
            spoiling = pred.get("verdict") in (
                "ALREADY PAST CRITICAL CEILING", "ALREADY BELOW SAFE FLOOR",
                "WILL SPOIL BEFORE ARRIVAL")
            if severity not in ("CRITICAL", "ESCALATED") and not spoiling:
                continue

            prop["escalated"] = True
            prop["escalated_at_sim_minute"] = round(self.sim_minute, 2)
            vehicle_id = prop.get("vehicle_id")

            if incident_id:
                try:
                    async with SessionLocal() as s:
                        inc = await s.get(Incident, incident_id)
                        if inc and inc.status in ("DETECTED", "PENDING"):
                            inc.status = "ESCALATED"
                        if inc:
                            inc.description = (inc.description or "")[:1800] + (
                                f" | AGENT ESCALATED at sim-min "
                                f"{round(self.sim_minute, 1)}: no operator "
                                f"response within {self.ESCALATE_AFTER_SIM_MIN} "
                                f"sim-min. Awaiting human decision.")
                        await s.commit()
                except Exception:
                    # Never let a bookkeeping failure break the tick; the
                    # broadcast below is what the UI actually reacts to.
                    pass

            self.event_ring.append({
                "sim_minute": round(self.sim_minute, 1),
                "vehicle_id": vehicle_id,
                "text": (f"AGENT ESCALATED — no operator response in "
                         f"{self.ESCALATE_AFTER_SIM_MIN} sim-min. Incident "
                         f"flagged by the agent; the decision still requires "
                         f"a human."),
                "severity": "critical",
                "source": "ai.escalation",
            })
            del self.event_ring[:-200]
            await BROADCAST.emit(0, "fleet.incident.escalated",
                                 {"vehicle_id": vehicle_id,
                                  "incident_id": incident_id,
                                  "approval_key": key,
                                  "severity": severity,
                                  "verdict": pred.get("verdict"),
                                  "waited_sim_min": round(waited, 2),
                                  "requires_human": True})

    async def _apply_divert(self, v: VehicleTwin, bundle: dict):
        target = bundle["target"]
        factor = self.traffic.factor_for(nearest_node(v.lng, v.lat), target)
        new_route = self.routing.route_from_point(v.lng, v.lat, target, factor)
        old_target = v.dest_id
        v.geom = [list(p) for p in new_route["geometry"]]
        v.total_km = new_route["distance_km"]
        v.done_km = 0.0
        v.dest_id = target
        v.route_adherence = 60.0
        self._route_seq += 1     # see __init__: int(sim_minute) alone collides
        async with SessionLocal() as s:
            # The id embeds int(sim_minute), which is NOT unique: two diverts for
            # the same vehicle to the same target within one sim-minute produce
            # the same id, and the insert then dies with
            # `UNIQUE constraint failed: fleet_routes.id` — surfacing as HTTP 500
            # on the operator's approval. A per-process counter disambiguates.
            # `merge` (not `add`) makes a genuine repeat an update rather than an
            # error, so the operator's second click can never fail this way.
            await s.merge(FleetRoute(id=f"R-{v.id}-{int(self.sim_minute)}-{target}-{old_target}-{self._route_seq}",
                             vehicle_id=v.id,
                             origin_id=old_target, destination_id=target, route_type="AI",
                             geometry=json.dumps(v.geom)[:60000],
                             distance_km=new_route["distance_km"],
                             eta_min=new_route["duration_min"],
                             score=(bundle.get("scored") or {}).get("score", 0.0),
                             reason=bundle["reason"][:2000]))
            if v.id in self.incident_db:
                inc = await s.get(Incident, self.incident_db[v.id])
                if inc:
                    inc.status = "REROUTED"
            await s.commit()
        await BROADCAST.emit(0, "vehicle.route.changed",
                             {"vehicle_id": v.id, "old_target": old_target, "new_target": target,
                              "eta_min": new_route["duration_min"],
                              "geometry": v.geom[:80],
                              "reason": bundle["reason"][:300]})
        await self._evt(v, f"{v.id} rerouted {old_target} -> {target}", "warning")

    # ---------------- arrival / transfer / verify ----------------
    async def _check_arrival(self, v: VehicleTwin):
        if v.status != "ARRIVED":
            return
        inc_id = self.incident_db.pop(v.id, None)
        units = v.load_units
        if inc_id is None:
            # normal delivery: register transfer at destination if it's a facility,
            # then respawn on a new mission (keeps the fleet alive)
            await self._evt(v, f"{v.id} arrived at {v.dest_id} — delivered {units}u", "info")
            await BROADCAST.emit(0, "cargo.transferred",
                              {"vehicle_id": v.id, "facility_id": v.dest_id, "units": units,
                               "resolved": True, "incident_id": None, "normal_delivery": True})
            # Release the dock. Previously only the incident branch below ever touched
            # busy_docks, and NOTHING incremented it on the normal path — so normal
            # deliveries consumed capacity that was never recorded as in use.
            self._release_dock(v.dest_id, units)
            self._respawn(v)
            return
        wh = next((w for w in self.warehouses if w["id"] == v.dest_id), None)
        if wh:
            wh["available_capacity"] = max(0, wh["available_capacity"] - units)
            wh["busy_docks"] = min(wh["docks"], wh["busy_docks"] + 1)
            # The rescued load is unloaded here, so the capacity this incident consumed
            # is free again. Without this every rescue drained a warehouse monotonically
            # and the fleet eventually had nowhere to divert to — which presents as "no
            # cold storage available" rather than the bug it is.
            self._release_dock(v.dest_id, units, consumed=True)
        # Recovery is verified BEFORE the load is unloaded: once `v.load_units = 0`
        # the box temperature describes an empty vehicle, which is no evidence that
        # the cargo it was carrying was recovered. `backup_cooling` stays out of the
        # proof: switching a mitigation on must not on its own resolve an incident.
        _t = v.box.snapshot()["true_temperature"]
        within_band = v.box.mn <= _t <= v.box.mx
        verdict = A.RecoveryVerifierAgent().run(
            v.box, getattr(v, "_snaps", [])[-8:], {"mn": v.box.mn, "mx": v.box.mx},
            ["activate_backup_cooling"] if v.box.backup_cooling else [])
        resolved = bool(verdict.get("verified", False)) and within_band
        # A load that reached a facility was rescued by relocation. That is a
        # different outcome from an in-situ temperature recovery, so it keeps its
        # own state instead of being folded into RESOLVED.
        transferred = units > 0 and wh is not None
        outcome = "RESOLVED" if resolved else ("TRANSFERRED" if transferred else "ESCALATED")
        async with SessionLocal() as s:
            if transferred:
                s.add(CargoTransfer(vehicle_id=v.id, facility_id=v.dest_id, units=units,
                                    health_pct=v.box.cargo_health, sim_minute=self.sim_minute))
            inc = await s.get(Incident, inc_id)
            if inc:
                inc.status = outcome
                if resolved:
                    inc.resolved_at = datetime.utcnow()
                    inc.resolved_tick = int(self.sim_minute)
            await s.commit()
        # Cargo only leaves the vehicle when a facility actually took delivery.
        # After a failed divert the load stays aboard, so ESCALATED does not also
        # silently erase a stranded load and record it as a completed move.
        if wh is not None:
            v.load_units = 0

        # Requirement 12: the report must say what the agent learned, including
        # when it failed. The reporter already renders a `lessons` list but the
        # fleet path never populated it — only the classic runner did, with four
        # hardcoded strings. These are derived from the actual outcome instead,
        # so the report cannot claim a lesson the evidence does not support.
        snap_now = v.snapshot()
        approval = next((p for p in list(self.pending_approvals.values())
                         + list(self.resolved_approvals.values())
                         if p.get("vehicle_id") == v.id), None)
        lessons = LNS.derive(
            snap_now,
            self._diagnosis.get(inc_id),
            {"observed": True,
             "resolved": resolved,
             "verified": bool(verdict.get("verified")),
             "evidence": verdict.get("evidence", []),
             "peak_temperature": round(snap_now["refrigeration"]["temperature"], 2),
             "recovered_to": round(v.box.temperature, 2),
             "backup_cooling": v.box.backup_cooling,
             "transferred_units": units},
            approval)

        async with SessionLocal() as s:
            # `outcome` was already committed with the transfer above; re-writing
            # it here would clobber a TRANSFERRED result with ESCALATED.
            s.add(AIAnalysis(incident_id=inc_id, agent_name="recovery_verifier",
                             analysis=json.dumps(verdict)[:4000],
                             confidence=verdict.get("confidence", 0.5)))
            s.add(AIAnalysis(incident_id=inc_id, agent_name="lessons",
                             analysis=json.dumps({"lessons": lessons,
                                                  "outcome": outcome,
                                                  "resolved": resolved,
                                                  "verified": bool(verdict.get("verified")),
                                                  "transferred": transferred,
                                                  "basis": "derived from outcome evidence, not canned text"},
                                                 )[:4000],
                             confidence=1.0))
            await s.commit()
        self._lessons[inc_id] = lessons
        await BROADCAST.emit(0, "cargo.transferred",
                             {"vehicle_id": v.id, "facility_id": v.dest_id, "units": units,
                              "resolved": resolved, "transferred": transferred,
                              "outcome": outcome, "incident_id": inc_id,
                              "evidence": verdict.get("evidence", [])})
        moved = f"transferred {units}u to {v.dest_id}" if transferred else \
                f"no facility accepted {units}u"
        await self._evt(v, f"{v.id} {moved} — {outcome.lower()}",
                        "info" if outcome == "RESOLVED" else "critical")
        # respawn the vehicle on a new mission to keep the fleet alive
        self._respawn(v)

    def _respawn(self, v: VehicleTwin):
        # A user-configured truck keeps the product and destination the operator
        # chose. _respawn otherwise picks a random POLYLINE and may even rewrite
        # the cargo to match that destination's required_cargo, which would
        # silently undo the explicit configuration the moment a delivery
        # completed — the truck would come back carrying something else, or
        # heading somewhere the user never selected. A configured truck
        # therefore completes its run and stops, and the operator starts the next
        # leg explicitly.
        if getattr(v, "user_defined", False):
            # match by the stable vehicle id (USER-<truck id>) first; the
            # display-name fallback covers twins spawned before ids existed
            spec = next((s for s in self.dispatch if s.get("vehicle_id") == v.id), None) \
                or next((s for s in self.dispatch
                         if getattr(v, "display_name", None) == s.get("name")), None)
            dest = (spec or {}).get("destination_id") or v.dest_id
            cargo = (spec or {}).get("cargo_type") or v.cargo_type
            origin = v.origin_id
            load = int((spec or {}).get("load_units") or 0)
            if load <= 0:
                return  # single-load truck: finished, do not recycle it
            route = self.routing.calculate_route(origin, dest, 1.0)
            fresh = VehicleTwin(v.id, v.kind, v.energy, v.driver, cargo,
                                load, v.capacity_units, origin, dest, route,
                                seed=v.seed + 1)
            fresh.user_defined = True
            fresh.display_name = getattr(v, "display_name", v.id)
            self.vehicles[v.id] = fresh
            return

        import random as _r
        rng = _r.Random(v.seed + int(self.sim_minute))
        pairs = list(POLYLINES.keys())
        o, d = pairs[rng.randrange(len(pairs))]
        cargo = v.cargo_type
        if d.startswith("D"):
            dest = next(x for x in DESTINATIONS if x["id"] == d)
            if cargo not in dest["required_cargo"]:
                cargo = dest["required_cargo"][0]
        route = self.routing.calculate_route(o, d, 1.0)
        fresh = VehicleTwin(v.id, v.kind, v.energy, v.driver, cargo,
                           200 + rng.randrange(600), 1000, o, d, route, seed=v.seed + 1)
        self.vehicles[v.id] = fresh

    # ---------------- service dispatch / cargo transfer / priority queue ----------------
    async def dispatch_service(self, target_id: str, task: str = "repair") -> dict:
        v = self.vehicles.get(target_id)
        if not v or v.kind == "SERVICE_TRUCK":
            return {"dispatched": False, "reason": "target must be a cargo vehicle"}
        if target_id in self.service_pending:
            return {"dispatched": False, "reason": f"service already en route ({self.service_pending[target_id]})"}
        fleet = [s for s in self.vehicles.values()
                 if s.kind == "SERVICE_TRUCK" and s.id not in self.service_tasks]
        svc = pick_service(fleet, v.lat, v.lng)
        if not svc:
            return {"dispatched": False, "reason": "no service vehicle available"}
        self.service_tasks[svc.id] = target_id
        self.service_pending[target_id] = task
        await self._evt(v, f"Service vehicle {svc.id} dispatched for {task}", "info")
        await BROADCAST.emit(0, "service.dispatched",
                             {"service_id": svc.id, "vehicle_id": target_id, "task": task})
        return {"dispatched": True, "service_id": svc.id, "vehicle_id": target_id, "task": task}

    async def request_transfer(self, donor_id: str, receiver_id: str) -> dict:
        donor, receiver = self.vehicles.get(donor_id), self.vehicles.get(receiver_id)
        if not donor or not receiver:
            return {"transferred": False, "reason": "unknown vehicle"}
        ok, why = validate_transfer(donor, receiver)
        if not ok:
            return {"transferred": False, "reason": why}

        async def _progress():
            """Cargo hand-off runs over ~6 world ticks: emit 0→100% progress,
            then apply + broadcast completion (cargo.transfer.progress)."""
            for pct in (0, 20, 40, 60, 80, 100):
                await asyncio.sleep(0.25)
                await BROADCAST.emit(0, "cargo.transfer.progress",
                                     {"from": donor_id, "to": receiver_id,
                                      "progress_pct": pct})
            if donor_id not in self.vehicles or receiver_id not in self.vehicles:
                await self._evt(donor, f"Transfer {donor_id} → {receiver_id} aborted "
                              "(vehicle left the fleet)", "warning")
                return
            res = apply_transfer(donor, receiver)
            await self._evt(donor, f"Cargo transfer {donor_id} → {receiver_id}: {res['units']}u",
                            "warning")
            await BROADCAST.emit(0, "cargo.transferred.truck",
                                 {"from": donor_id, "to": receiver_id, **res})
        asyncio.create_task(_progress())
        return {"transferred": True, "from": donor_id, "to": receiver_id,
                "note": "progress 0→100 over ~6 ticks, then completion"}

    def priority_queue(self) -> list[dict]:
        return priority_queue(self.vehicles, self.incident_db)

    def _service_progress(self, dt: float):
        """Advance service trucks toward their target; repair on arrival.

        A service truck has no destination node, so the generic `_place_on_route`
        movement cannot bring it anywhere: its `dest_id` is whatever cargo route
        it spawned with. Measured live: service trucks sat 4.9 km and 6.7 km from
        their assigned truck and never closed the gap, because nothing steered
        them toward it.

        Fix: on dispatch the service truck is RE-TARGETED at its target truck's
        current position, using the same route-from-current-position primitive
        `_apply_divert` uses. `step()` then closes the distance normally on every
        world tick, and arrival fires when it enters the service radius.

        Re-targeting only happens in the tick BEFORE the truck is within the
        arrival radius, so a truck already on scene is not re-routed under itself
        and the arrival branch cannot thrash between `d < R` and `d >= R`.
        """
        for svc_id, target_id in list(self.service_tasks.items()):
            svc, tgt = self.vehicles.get(svc_id), self.vehicles.get(target_id)
            if not tgt or tgt.id not in self.vehicles:
                self.service_tasks.pop(svc_id, None)
                self.service_pending.pop(target_id, None)
                continue
            d = haversine_km((svc.lng, svc.lat), (tgt.lng, tgt.lat))
            if d < SERVICE_ARRIVAL_KM:   # arrived at the broken truck
                task = self.service_pending.pop(target_id, "repair")
                tgt.repair()
                self.service_tasks.pop(svc_id, None)
                self._queue_event_nowait("service.completed",
                                         {"service_id": svc_id, "vehicle_id": target_id, "task": task})
                continue
            # Not yet on scene: steer the truck at the target's live position.
            #
            # There must be NO gap between the arrival radius and the re-target
            # threshold. A first version only re-targeted while `d > 0.8 * 2.5`
            # (2.0 km), which left a dead zone: a truck that drifted to 0.82 km
            # was already outside the 0.8 km arrival radius, so it could never
            # arrive, and it was under 2.0 km, so it was never re-targeted
            # either. It sat there for the rest of the run and
            # `service.completed` never fired. Measured live: SERVICE-1236-0 at
            # exactly 0.82 km, stranded.
            #
            # The guard now re-targets at anything beyond the arrival radius, so
            # closing the gap is always possible. The rate limit (once a sim
            # minute, and only while it is a meaningful correction) is what stops
            # the truck being yanked around during a normal approach.
            if d > SERVICE_ARRIVAL_KM and \
                    (self.sim_minute - self._service_retarget_at.get(svc_id, -99.0)) >= 1.0:
                prev = self._service_retarget_at.get(svc_id)
                self._retarget_service(svc, tgt)
                self._service_retarget_at[svc_id] = self.sim_minute
                # Only log the first re-target of a task, not every sim-minute.
                if prev is None:
                    log.info("service %s re-targeted at %s (%.2f km out)",
                             svc_id, target_id, d)

    def _retarget_service(self, svc, tgt) -> None:
        """Point a service truck at its target truck's current position.

        Uses the same route-from-current-position primitive `_apply_divert` uses,
        so geometry/distance units stay consistent with every other reroute. No
        broadcast: this is internal fleet movement, not an operator-visible route
        decision, and emitting `vehicle.route.changed` here would falsely satisfy
        the acceptance sweep's chain assertion.
        """
        try:
            factor = self.traffic.factor_for(nearest_node(svc.lng, svc.lat),
                                             nearest_node(tgt.lng, tgt.lat))
            r = self.routing.route_from_point(svc.lng, svc.lat, nearest_node(tgt.lng, tgt.lat), factor)
            if not r or r.get("distance_km", 0) <= 0:
                return
            svc.geom = [list(p) for p in r["geometry"]]
            svc.total_km = r["distance_km"]
            svc.done_km = 0.0
        except Exception:
            # Navigation is best-effort: a routing failure must not kill the
            # world tick. The truck simply keeps its previous heading.
            pass

    def _queue_event_nowait(self, etype: str, payload: dict):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(BROADCAST.emit(0, etype, payload))
        except RuntimeError:
            pass

    # ---------------- injection & manual action ----------------
    async def inject(self, vehicle_id: str, failure: str) -> dict:
        v = self.vehicles.get(vehicle_id)
        if not v:
            return {"injected": False, "reason": "unknown vehicle"}
        v.inject_failure(failure)
        await self._evt(v, f"Failure injected on {vehicle_id}: {failure}", "critical")
        await BROADCAST.emit(0, "vehicle.failure.injected",
                             {"vehicle_id": vehicle_id, "failure": failure})
        return {"injected": True, "vehicle_id": vehicle_id, "failure": failure}

    async def inject_random(self) -> dict:
        vid = sorted(self.vehicles.keys())[self._tick_n % len(self.vehicles)]
        return await self.inject(vid, "compressor_degradation")

    async def apply_action(self, vehicle_id: str, action: str) -> dict:
        v = self.vehicles.get(vehicle_id)
        if not v:
            return {"applied": False, "reason": "unknown vehicle"}
        ok = v.apply_action(action)
        await self._evt(v, f"Action {action} on {vehicle_id}: {'applied' if ok else 'rejected'}",
                        "info" if ok else "warning")
        return {"applied": ok, "vehicle_id": vehicle_id, "action": action}

    # ---------------- persistence + events ----------------
    async def _evt(self, v, text: str, severity: str = "info"):
        """v may be None for world-level events (weather/traffic)."""
        ev = make_event("vehicle.event" if v else "world.event",
                        {"vehicle_id": v.id if v else None, "text": text, "severity": severity},
                        source=v.id if v else "world")
        self.event_ring.insert(0, ev)
        self.event_ring = self.event_ring[:90]
        if v is not None:
            async with SessionLocal() as s:
                s.add(VehicleEvent(vehicle_id=v.id, event_type="note", lat=v.lat, lng=v.lng,
                                   severity=severity, description=text, sim_minute=self.sim_minute))
                await s.commit()

    async def _persist_vehicles(self, snaps: list[dict]):
        try:
            async with SessionLocal() as s:
                for snap in snaps:
                    vid = snap["vehicle_id"]
                    veh = await s.get(Vehicle, vid)
                    if not veh:
                        veh = Vehicle(id=vid)
                        s.add(veh)
                    veh.lat = snap["lat"]; veh.lng = snap["lng"]
                    veh.heading = snap["heading"]; veh.speed_kmh = snap["speed_kmh"]
                    veh.fuel_pct = snap["vehicle"]["fuel_percent"]
                    veh.battery_pct = snap["vehicle"]["battery_percent"]
                    veh.vehicle_health = snap["vehicle"]["vehicle_health"]
                    veh.load_units = snap["cargo"]["load_units"]
                    veh.cargo_type = snap["cargo"]["cargo_type"]
                    dest = snap["trip"].get("destination_id")
                    if isinstance(dest, (tuple, list)):
                        dest = str(dest[0]) if dest else None
                    veh.destination_id = dest
                    veh.status = snap["status"]
                await s.commit()
        except Exception as e:
            log.warning("persist failed: %s", e)

    async def _prune_events(self):
        """Bound fleet_vehicle_events growth.

        Only append-only telemetry history is removed; incidents, AI analyses,
        route decisions and cargo transfers are deliberately left intact so that
        reporting and replay keep working over the full retained horizon.
        """
        try:
            cutoff = datetime.utcnow() - timedelta(hours=EVENT_RETENTION_HOURS)
            async with SessionLocal() as s:
                res = await s.execute(
                    delete(VehicleEvent).where(VehicleEvent.created_at < cutoff))
                await s.commit()
                removed = res.rowcount or 0
            if removed:
                log.info("pruned %d vehicle events older than %dh",
                         removed, EVENT_RETENTION_HOURS)
        except Exception as e:
            log.warning("event prune failed: %s", e)

    # ---------------- introspection ----------------
    def state(self) -> dict:
        snaps = []
        for vid, v in self.vehicles.items():
            s = v.snapshot()
            s["alerts"] = self.alert_counts.get(vid, 0)
            # Predictive safe-remaining-time. state() builds fresh snapshots, so it
            # needs its own projection — the one attached in the tick lives on
            # that tick's snapshot objects, not on these.
            #
            # Uses true temperature on purpose: a frozen probe reports a
            # healthy-looking load, and projecting from that fiction is how a
            # spoiling load slips through with no warning.
            s["prediction"] = PRED.project(s, self._incident_ctx(v))
            snaps.append(s)
        return {"vehicles": snaps,
                "warehouses": self.warehouses,
                "destinations": DESTINATIONS,
                "region": REGION,
                "sim_minute": round(self.sim_minute, 2),
                "paused": self.paused,
                "speed": self.clock.speed,
                "scenario": dict(self.scenario),
                "weather": self.traffic.state(),
                "geofences": GEOFENCES,
                "events": self.event_ring[:40],
                "counts": {
                    "vehicles": len(snaps),
                    "in_transit": sum(1 for s in snaps if s["status"] == "IN_TRANSIT"),
                    "at_risk": sum(1 for s in snaps if s["cargo"]["risk_level"] in ("HIGH", "CRITICAL")),
                    "critical": sum(1 for s in snaps if s["cargo"]["risk_level"] == "CRITICAL"),
                    "arrived": sum(1 for s in snaps if s["status"] == "ARRIVED"),
                    "completed": sum(1 for s in snaps if s["status"] == "ARRIVED"),
                    "active_incidents": len(self.incident_db),
                }}

    def vehicle_detail(self, vid: str) -> dict | None:
        v = self.vehicles.get(vid)
        if not v:
            return None
        return {"snapshot": v.snapshot(),
                "recent_events": [e for e in self.event_ring if e["payload"].get("vehicle_id") == vid][:30],
                "geometry": v.geom[:120]}

    # ---------------- incident replay ----------------
    async def replay(self, incident_id: int) -> dict | None:
        """Reassemble the incident window for an orchestrator (fleet) incident.

        Only simulation_id == 0 is a fleet incident; classic sim-pipeline
        incidents (simulation_id > 0) are a separate system. Joins VehicleEvents,
        RouteDecisions, CargoTransfers, the Incident row, and any in-memory
        per-incident telemetry frames into one {incident, frames[]} timeline
        sorted by sim_minute. Returns None when the incident isn't a fleet one.
        """
        async with SessionLocal() as s:
            inc = await s.get(Incident, incident_id)
            if inc is None:
                return None
            if inc.simulation_id != 0:
                return None
            lo = (inc.detected_tick or 0) - 5
            hi = (inc.resolved_tick if inc.resolved_tick is not None
                  else int(self.sim_minute)) + 5
            vevs = (await s.execute(
                select(VehicleEvent).where(VehicleEvent.vehicle_id == inc.description.split(":")[0].strip(),
                                           VehicleEvent.sim_minute >= lo,
                                           VehicleEvent.sim_minute <= hi,
                                           VehicleEvent.event_type.in_(["note"]))
                .order_by(VehicleEvent.sim_minute))).scalars().all()
            rvs = (await s.execute(
                select(RouteDecision).where(RouteDecision.sim_minute >= lo,
                                            RouteDecision.sim_minute <= hi)
                .order_by(RouteDecision.sim_minute))).scalars().all()
            cts = (await s.execute(
                select(CargoTransfer).where(CargoTransfer.sim_minute >= lo,
                                            CargoTransfer.sim_minute <= hi)
                .order_by(CargoTransfer.sim_minute))).scalars().all()
        vid = (inc.description or "").split(":")[0].strip()
        frames: list[dict] = []
        for e in vevs:
            frames.append({"sim_minute": round(e.sim_minute, 2), "kind": "event",
                           "data": {"type": e.event_type, "severity": e.severity,
                                    "description": e.description, "vehicle_id": e.vehicle_id}})
        for rv in rvs:
            if rv.vehicle_id != vid:
                continue
            frames.append({"sim_minute": round(rv.sim_minute, 2), "kind": "route_decision",
                           "data": {"decision": rv.decision, "reason": rv.reason,
                                    "confidence": rv.confidence, "vehicle_id": rv.vehicle_id}})
        for ct in cts:
            frames.append({"sim_minute": round(ct.sim_minute, 2), "kind": "cargo_transfer",
                           "data": {"vehicle_id": ct.vehicle_id, "facility_id": ct.facility_id,
                                    "units": ct.units, "health_pct": ct.health_pct}})
        for fr in self._incident_tel.get(incident_id, []):
            frames.append({"sim_minute": fr["min"], "kind": "telemetry", "data": fr})
        frames.sort(key=lambda f: f["sim_minute"])
        return {"incident": {"id": inc.id, "type": inc.type, "severity": inc.severity,
                             "status": inc.status, "root_cause": inc.root_cause,
                             "description": inc.description,
                             "detected_tick": inc.detected_tick,
                             "resolved_tick": inc.resolved_tick,
                             "peak_temperature": inc.peak_temperature,
                             "simulation_id": inc.simulation_id,
                             "vehicle_id": vid},
                "frames": frames}

    # ---------------- telemetry history ----------------
    def history(self, vid: str, window: str = "5m") -> dict | None:
        """Slice the vehicle's capped telemetry buffer by sim-minute.

        window: 5m | 15m | 1h | trip (whole buffer).
        Returns {points, window, sim_minute} or None for unknown vehicle.
        """
        v = self.vehicles.get(vid)
        if not v:
            return None
        span = {"5m": 5.0, "15m": 15.0, "1h": 60.0}.get(window)
        pts = list(v._tel)
        if window != "trip" and span is not None:
            cutoff = self.sim_minute - span
            pts = [p for p in pts if p["min"] >= cutoff]
        return {"vehicle_id": vid, "window": window,
                "sim_minute": round(self.sim_minute, 2), "points": pts}


FLEET = FleetOrchestrator()

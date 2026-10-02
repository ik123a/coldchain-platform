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
from ..models.entities import Incident, AIAnalysis
from .runner import BROADCAST
from . import agents_d as A

log = logging.getLogger("fleet")
SUSTAIN_TICKS = 6            # consecutive over-band world-ticks → incident
ARRIVE_KM = 0.3
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
        if self._task and not self._task.done():
            return
        self.n_vehicles = n_vehicles
        self._spawn_fleet()
        self._task = asyncio.create_task(self._run())
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
        self.transfers: dict[str, dict] = {}       # donor vid -> transfer state

    # ---------------- manual dispatch fleet (user-defined trucks) ----------------
    #
    # The auto-spawned fleet above is round-robin over POLYLINES/CARGO_TYPES and
    # is what the capstone demo runs on. It is left completely untouched.
    #
    # Alongside it, a user may configure 2-3 trucks by hand — explicit product
    # and explicit destination — for the human-in-the-loop demonstration. Those
    # live in `self.dispatch` rather than in `self.vehicles` so that:
    #   * resetting the demo fleet cannot silently delete a configured truck,
    #   * the two populations stay distinguishable in /api/fleet/state,
    #   * each configured truck carries its own product/destination spec that a
    #     panel can read back.
    #
    # A configured truck is spawned into `self.vehicles` when the operator
    # starts the run, so it moves, emits telemetry, raises incidents and can be
    # rescued through exactly the same code path as any other vehicle. There is
    # no second movement or thermal implementation.

    DISPATCH_MAX = 3

    def _dispatch_specs(self) -> list[dict]:
        return [dict(s) for s in self.dispatch]

    def configure_dispatch(self, specs: list[dict]) -> dict:
        """Validate and store the operator's truck definitions.

        Raises ValueError with a human-readable reason on anything the
        simulation cannot honour, so the API can return 400 instead of
        silently substituting a random product or destination — which is the
        exact failure mode this feature exists to remove.
        """
        if not specs:
            raise ValueError("at least one truck is required")
        if len(specs) > self.DISPATCH_MAX:
            raise ValueError(f"at most {self.DISPATCH_MAX} trucks can be dispatched "
                             f"at once (got {len(specs)})")

        known_cargo = set(CARGO_TYPES) | {"pharmaceutical"}
        known_nodes = {w["id"] for w in self.warehouses} | {d["id"] for d in DESTINATIONS}

        seen: set[str] = set()
        cleaned: list[dict] = []
        for i, s in enumerate(specs):
            name = (s.get("name") or f"Truck {i + 1}").strip()[:40]
            cargo = (s.get("cargo_type") or "").strip()
            dest = (s.get("destination_id") or "").strip()
            origin = (s.get("origin_id") or "").strip() or None

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
            if dest in seen:
                raise ValueError(f"{name}: destination {dest} is already used by "
                                 f"another truck in this run")
            seen.add(dest)

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

            cleaned.append({
                "name": name,
                "cargo_type": cargo,
                "destination_id": dest,
                "origin_id": origin,
                "load_units": load,
            })

        self.dispatch = cleaned
        return {"trucks": self._dispatch_specs(), "count": len(cleaned)}

    def clear_dispatch(self) -> dict:
        self.dispatch = []
        return {"trucks": [], "count": 0}

    def start_dispatch(self) -> dict:
        """Spawn the configured trucks into the live world.

        Idempotent per spec: a truck already running with the same name is
        replaced, so pressing Start twice does not double the fleet.
        """
        if not self.dispatch:
            raise ValueError("no trucks configured — define them first")

        started: list[str] = []
        for i, s in enumerate(self.dispatch):
            dest = s["destination_id"]
            origin = s.get("origin_id") or self._origin_for(dest)
            route = self.routing.calculate_route(origin, dest, 1.0)
            vid = s.get("vehicle_id") or f"USER-{dest}-{i}"
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
            started.append(vid)
        return {"started": started, "count": len(started),
                "trucks": self._dispatch_specs()}

    def _origin_for(self, dest: str) -> str:
        """Pick a sensible origin node for a hand-configured truck.

        Prefers a warehouse that stocks the product, so the load is coherent
        with the simulation rather than starting from an unrelated node.
        Falls back to any other warehouse.
        """
        wanted = {s.get("cargo_type") for s in self.dispatch}
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
        cause = ("compressor_failure" if v.compressor == "FAILED"
                 else "cooling_degradation" if v.compressor == "DEGRADED"
                 else "door_open" if v.door_open else "power_failure" if not v.box.power_ok
                 else "environmental_deviation")
        async with SessionLocal() as s:
            inc = Incident(simulation_id=0, type="vehicle_thermal_excursion", severity=sev,
                           status="DETECTED", detected_tick=int(self.sim_minute),
                           root_cause=cause,
                           description=f"{v.id}: cargo temp {snap['refrigeration']['temperature']}C "
                                       f"outside band [{v.box.mn},{v.box.mx}]C in transit",
                           peak_temperature=snap["refrigeration"]["temperature"])
            s.add(inc)
            await s.commit()
            iid = inc.id
        self.incident_db[v.id] = iid
        await self._evt(v, f"Incident detected on {v.id}: {cause} — temp "
                          f"{snap['refrigeration']['temperature']}C", "critical")
        await BROADCAST.emit(0, "fleet.incident.created",
                             {"vehicle_id": v.id, "incident_id": iid, "severity": sev,
                              "root_cause": cause, "snapshot": snap,
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
        if self._autonomous and bundle["decision"] == "DIVERT":
            await self._apply_divert(v, bundle)

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
        async with SessionLocal() as s:
            s.add(FleetRoute(id=f"R-{v.id}-{int(self.sim_minute)}", vehicle_id=v.id,
                             origin_id=old_target, destination_id=target, route_type="AI",
                             geometry=json.dumps(v.geom)[:60000],
                             distance_km=new_route["distance_km"],
                             eta_min=new_route["duration_min"], score=bundle["scored"]["score"],
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
        async with SessionLocal() as s:
            s.add(CargoTransfer(vehicle_id=v.id, facility_id=v.dest_id, units=units,
                                health_pct=v.box.cargo_health, sim_minute=self.sim_minute))
            inc = await s.get(Incident, inc_id)
            if inc:
                inc.status = "TRANSFERRED"
            await s.commit()
        v.load_units = 0
        # recovery verification: backup cooling must pull temp back in band
        ok = v.box.temperature <= v.box.mx + 1.0 or v.box.backup_cooling
        verdict = A.RecoveryVerifierAgent().run(
            v.box, getattr(v, "_snaps", [])[-8:], {"mn": v.box.mn, "mx": v.box.mx},
            ["activate_backup_cooling"] if v.box.backup_cooling else [])
        resolved = verdict.get("verified", False) or ok
        async with SessionLocal() as s:
            inc = await s.get(Incident, inc_id)
            if inc:
                inc.status = "RESOLVED" if resolved else "ESCALATED"
                inc.resolved_at = datetime.utcnow() if resolved else None
                inc.resolved_tick = int(self.sim_minute) if resolved else None
            s.add(AIAnalysis(incident_id=inc_id, agent_name="recovery_verifier",
                             analysis=json.dumps(verdict)[:4000],
                             confidence=verdict.get("confidence", 0.5)))
            await s.commit()
        await BROADCAST.emit(0, "cargo.transferred",
                             {"vehicle_id": v.id, "facility_id": v.dest_id, "units": units,
                              "resolved": resolved, "incident_id": inc_id,
                              "evidence": verdict.get("evidence", [])})
        await self._evt(v, f"{v.id} transferred {units}u to {v.dest_id} — "
                          f"{'recovery verified' if resolved else 'still critical'}",
                          "info" if resolved else "critical")
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
            spec = next((s for s in self.dispatch
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
        """Advance service trucks toward their target; repair on arrival."""
        for svc_id, target_id in list(self.service_tasks.items()):
            svc, tgt = self.vehicles.get(svc_id), self.vehicles.get(target_id)
            if not tgt or tgt.id not in self.vehicles:
                self.service_tasks.pop(svc_id, None)
                continue
            d = haversine_km((svc.lng, svc.lat), (tgt.lng, tgt.lat))
            if d < 0.8:   # arrived at the broken truck
                task = self.service_pending.pop(target_id, "repair")
                tgt.repair()
                self.service_tasks.pop(svc_id, None)
                self._queue_event_nowait("service.completed",
                                         {"service_id": svc_id, "vehicle_id": target_id, "task": task})
            # else: keep driving; trucks respawn toward their own destinations,
            # so distance closes only via target's own motion — acceptable for sim.

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

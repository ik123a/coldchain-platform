"""FleetOrchestrator: the live world.

Owns VehicleTwins, runs the SimClock loop, detects thermal incidents,
runs FleetCoordinator decisions, applies reroutes, simulates arrival +
cargo transfer + recovery verification, persists rolling state, and
broadcasts everything over the existing BROADCAST hub.
"""
from __future__ import annotations
import asyncio, json, logging
from datetime import datetime
from .clock import SimClock
from .traffic import TrafficWorld
from .routing import RoutingService, nearest_node
from .fleet import VehicleTwin
from .fleet_agents import FacilityMatcher, RouteScorer, FleetCoordinator
from .events import make_event
from .geo_data import WAREHOUSES, DESTINATIONS, POLYLINES, DRIVERS, CARGO_TYPES, REGION, GEOFENCES
from ..database.engine import SessionLocal
from ..models.fleet import Vehicle, FleetRoute, VehicleEvent, RouteDecision, CargoTransfer
from ..models.entities import Incident, AIAnalysis
from .runner import BROADCAST
from . import agents_d as A

log = logging.getLogger("fleet")
SUSTAIN_TICKS = 6            # consecutive over-band world-ticks → incident
ARRIVE_KM = 0.3


class FleetOrchestrator:
    def __init__(self, n_vehicles: int = 12):
        self.clock = SimClock(speed=2.0)
        self.traffic = TrafficWorld(seed=42)
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
        self._over_run: dict[str, int] = {}
        self._autonomous = True                    # AI decisions auto-apply (SIMULATION ONLY)
        self.event_ring: list[dict] = []
        self._task = None
        self._seed_i = 100
        self.alert_counts: dict[str, int] = {}     # vehicle_id -> non-info alert count
        self._last_weather: str | None = None
        self._traffic_snap: dict[str, str] = {}
        self._geo_state: dict[str, str | None] = {}

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

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused

    # ---------------- fleet spawning ----------------
    def _spawn_fleet(self):
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
            vid = f"TRUCK-{101 + i}"
            self._seed_i += 1
            self.vehicles[vid] = VehicleTwin(
                vid, "REFRIGERATED_TRUCK" if energy != "ELECTRIC" else "EV_REEFER",
                energy, DRIVERS[i % len(DRIVERS)], cargo,
                load_units=200 + ((i * 137) % 600), capacity_units=1000,
                origin_id=o, dest_id=d, route=route, seed=self._seed_i)

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
                self.traffic.maybe_weather()
                snaps = []
                for vid, v in self.vehicles.items():
                    factor = self.traffic.factor_for(v.origin_id, v.dest_id)
                    s = v.step(dt, factor, self.traffic.ambient_c)
                    delta = v.alerts_delta()
                    if delta:
                        self.alert_counts[v.id] = self.alert_counts.get(v.id, 0) + delta
                        s["alerts_new"] = delta
                    snaps.append(s)
                    await self._check_incident(v, s)
                    await self._check_arrival(v)
                    await self._check_geofence(v)
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
        except asyncio.CancelledError:
            log.info("fleet loop cancelled")

    # ---------------- geofence checks ----------------
    async def _check_geofence(self, v: VehicleTwin):
        from .geo_data import geofence_for
        cur = geofence_for(v.lat, v.lng)
        prev = self._geo_state.get(v.id)
        if cur != prev:
            self._geo_state[v.id] = cur
            if cur is not None:
                await BROADCAST.emit(0, "geofence.entered",
                                     {"vehicle_id": v.id, "fence": cur["id"], "type": cur["type"]})
                sev = "warning" if cur["type"] == "RESTRICTED" else "info"
                await self._evt(v, f"{v.id} entered {cur['type']} zone {cur['id']}", sev)
            elif prev is not None:
                await BROADCAST.emit(0, "geofence.exited",
                                     {"vehicle_id": v.id, "fence": prev["id"], "type": prev["type"]})

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
            self._respawn(v)
            return
        wh = next((w for w in self.warehouses if w["id"] == v.dest_id), None)
        if wh:
            wh["available_capacity"] = max(0, wh["available_capacity"] - units)
            wh["busy_docks"] = min(wh["docks"], wh["busy_docks"] + 1)
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
                    veh.destination_id = snap["trip"]["destination_id"]
                    veh.status = snap["status"]
                await s.commit()
        except Exception as e:
            log.warning("persist failed: %s", e)

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


FLEET = FleetOrchestrator()

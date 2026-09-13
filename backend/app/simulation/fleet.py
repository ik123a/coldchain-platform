"""Live vehicle twin.

Movement (GPS noise, speed dynamics, harsh events, driver score) + energy +
vehicle health, with the existing thermal Engine reused as the reefer box.
One authoritative snapshot() shape feeds WS + REST + persistence.
"""
from __future__ import annotations
import math, random
from .engine import Engine
from .risk import risk as risk_fn

COMPRESSOR_OK, COMPRESSOR_DEGRADED, COMPRESSOR_FAILED = "ONLINE", "DEGRADED", "FAILED"

BOX_PROFILES = {
    "fresh_produce": (4.0, 2.0, 8.0),
    "dairy": (4.0, 1.0, 5.0),
    "frozen_goods": (-18.0, -22.0, -15.0),
    "pharma": (5.0, 2.0, 8.0),
}

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _tel_append(self, snap: dict, sim_minute: float):
    """Append one capped telemetry frame (2400-deep deque semantics via list slice)."""
    self._tel.append({
        "min": round(sim_minute, 2),
        "speed": round(snap["speed_kmh"], 1),
        "temp": snap["refrigeration"]["temperature"],
        "humidity": snap["refrigeration"]["humidity"],
        "energy": round(self.battery_pct if self.energy == "ELECTRIC" else self.fuel_pct, 1),
        "cargo_health": snap["cargo"]["cargo_health"],
        "risk": round(snap["cargo"]["risk_score"], 1),
    })
    if len(self._tel) > 2400:
        self._tel = self._tel[-2400:]


class VehicleTwin:
    def __init__(self, vid: str, kind: str, energy: str, driver: str, cargo_type: str,
                 load_units: int, capacity_units: int, origin_id: str, dest_id: str,
                 route: dict, seed: int):
        self.id = vid
        self.kind = kind
        self.energy = energy
        self.driver = driver
        self.cargo_type = cargo_type
        self.load_units = load_units
        self.capacity_units = capacity_units
        self.origin_id = origin_id
        self.dest_id = dest_id
        self.route_id = route.get("id", "R-?")
        self.geom = [list(p) for p in route["geometry"]]
        self.total_km = float(route["distance_km"])
        self.done_km = 0.0
        self.rng = random.Random(seed)
        self.seed = seed

        # kinematics
        self.lat, self.lng = self.geom[0][1], self.geom[0][0]
        self.heading = 0.0
        self.speed_kmh = 0.0
        self.speed_limit = float(route.get("speed_limit_kmh", 55.0))
        self.accel_mps2 = 0.0
        self.speeds: list[float] = []
        self.avg_speed = 0.0
        self.max_speed = 0.0

        # energy / health
        self.fuel_pct = 55.0 + self.rng.uniform(0, 40)
        self.battery_pct = 65.0 + self.rng.uniform(0, 30)
        self.vehicle_health = 86.0 + self.rng.uniform(0, 12)
        self.engine_temp_c = 88.0 + self.rng.uniform(-4, 4)

        # reefer box (existing thermal engine)
        tgt, mn, mx = BOX_PROFILES[cargo_type]
        self.box = Engine(target=tgt, mn=mn, mx=mx, hum_min=55.0, hum_max=85.0, seed=seed)
        self.compressor = COMPRESSOR_OK
        self.door_open = False
        self.cooling_eff_pct = 97.0

        # behavior / state
        self.status = "IN_TRANSIT"
        self.speed_events = 0
        self.harsh_brakes = 0
        self.harsh_accels = 0
        self.idle_min = 0.0
        self.stop_min = 0.0
        self.route_adherence = 100.0
        self.time_over_limit_min = 0.0
        self.max_excess_kmh = 0.0
        self.stops: list[dict] = []
        self._open_stop: dict | None = None
        self._last_alerts = 0
        self.original_eta_min = 0.0  # set at first step

        # connectivity
        self.gps_acc = self.rng.uniform(2.5, 6.0)
        self.signal = self.rng.uniform(70, 99)

        # incident memory
        self.over_ticks = 0
        self.risk: dict = {"score": 0.0, "level": "LOW"}
        self._snaps: list[dict] = []
        self._tel: list[dict] = []          # capped per-world-tick telemetry
        self.sim_minute = 0.0               # orchestrator stamps each tick

    # ---------------- per world tick ----------------
    def step(self, dt_min: float, traffic_factor: float, ambient_c: float) -> dict:
        self.box.ambient = ambient_c

        # --- kinematics with traffic, noise, near-arrival deceleration ---
        rem = self.remaining_km()
        target = self.speed_limit / max(0.55, traffic_factor)
        target *= self.rng.uniform(0.85, 1.10)
        if rem < 1.0:
            target = min(target, max(6.0, rem * 12.0))  # decelerate on approach
        if rem < 0.15:
            target = 0.0                                # dock: come to a stop
        if self.door_open:
            target = min(target, 8.0)
        old = self.speed_kmh
        # noise scales with target speed: a stationary truck doesn't jitter ±1.3 km/h
        noise = self.rng.gauss(0, 1.3 * min(1.0, max(0.15, target / 25.0)))
        self.speed_kmh = max(0.0, self.speed_kmh + (target - self.speed_kmh) * 0.28 + noise)
        self.speeds.append(self.speed_kmh)
        self.speeds = self.speeds[-240:]
        self.max_speed = max(self.max_speed, self.speed_kmh)
        window = self.speeds[-60:]
        self.avg_speed = sum(window) / len(window)

        # harsh-event detection (dt in sim-minutes → accel in m/s²)
        if dt_min > 0:
            self.accel_mps2 = ((self.speed_kmh - old) / 3.6) / (dt_min * 60.0)
        if self.accel_mps2 < -2.5:
            self.harsh_brakes += 1
        elif self.accel_mps2 > 1.8:
            self.harsh_accels += 1
        if self.speed_kmh > self.speed_limit + 5:
            self.speed_events += 1
            self.time_over_limit_min += dt_min
            self.max_excess_kmh = max(self.max_excess_kmh, self.speed_kmh - self.speed_limit)
        if self.speed_kmh < 1.0:
            self.idle_min += dt_min
            self.stop_min += dt_min
            if self._open_stop is None:
                # planned if within 0.5 km of destination node else unexpected
                import math as _m
                planned = self.remaining_km() < 0.5
                self._open_stop = {"sim_min": self.total_km and 0 or 0, "lat": self.lat, "lng": self.lng,
                                   "planned": planned, "duration_min": 0.0,
                                   "reason": "arrival stop" if planned else "unplanned stop"}
            self._open_stop["duration_min"] += dt_min
        elif self._open_stop is not None:
            self.stops.append({**self._open_stop, "sim_min": round(self.done_km, 2)})
            self.stops = self.stops[-12:]
            self._open_stop = None

        # --- advance along polyline ---
        adv_km = self.speed_kmh * (dt_min / 60.0)
        self.done_km = min(self.total_km, self.done_km + adv_km)
        self._place_on_route(self.done_km / max(self.total_km, 1e-6))

        # --- reefer thermal physics: sub-step at 0.25 sim-min granularity ---
        steps = max(1, int(round(dt_min / 0.25)))
        sub = dt_min / steps
        snap = None
        for _ in range(steps):
            self._box_tick(sub)
            snap = self.box.snapshot()
            self._snaps.append(snap)
        self._snaps = self._snaps[-600:]

        # --- cargo risk from real thermal exposure ---
        true_t = snap["true_temperature"]
        if true_t > self.box.mx or true_t < self.box.mn:
            self.over_ticks += steps
        else:
            self.over_ticks = 0
        r = risk_fn(snap, {"mn": self.box.mn, "mx": self.box.mx, "hum_min": self.box.hum_min,
                           "hum_max": self.box.hum_max},
                    self.over_ticks, cargo_type=self.cargo_type,
                    trend_c_per_min=self.trend_c_per_min())
        self.risk = r

        # --- energy / health / connectivity drift ---
        burn = (0.02 + self.speed_kmh / 3000.0 + (0.6 if self.box.compressor_on else 0.25)) * dt_min
        if self.energy == "ELECTRIC":
            self.battery_pct = max(0.0, self.battery_pct - burn * 1.35)
        elif self.energy == "HYBRID":
            self.battery_pct = max(0.0, self.battery_pct - burn * 0.6)
            self.fuel_pct = max(0.0, self.fuel_pct - burn * 0.5)
        else:
            self.fuel_pct = max(0.0, self.fuel_pct - burn)
        self.vehicle_health = max(35.0, self.vehicle_health - 0.0005 * dt_min)
        self.engine_temp_c = 88.0 + (10.0 if self.rng.random() < 0.005 else 0.0) + self.rng.gauss(0, 0.8)
        self.gps_acc = max(1.8, min(12.0, self.gps_acc + self.rng.gauss(0, 0.2)))
        self.signal = max(25.0, min(99.0, self.signal + self.rng.gauss(0, 0.9)))

        if self.done_km >= self.total_km - 0.05:
            self.status = "ARRIVED"
        # original ETA captured on first step; multi-ETA snapshot data
        if self.original_eta_min == 0.0:
            self.original_eta_min = self.eta_min()
        snap = self.snapshot()
        _tel_append(self, snap, self.sim_minute)
        return snap

    def eta_bundle(self) -> dict:
        cur = self.eta_min()
        ttc = self.time_to_critical_min()
        return {"original_min": round(self.original_eta_min, 1),
                "current_min": round(cur, 1),
                "ai_optimized_min": round(cur * (0.85 if self.compressor == "DEGRADED" else 1.0), 1),
                "best_possible_min": round((self.remaining_km() / max(30.0, self.speed_limit)) * 60.0, 1),
                "arrival_after_critical": bool(ttc is not None and cur > ttc)}

    def _box_tick(self, dt_min: float):
        """Engine.tick() advances one fixed step; emulate fractional dt by scaling
        its output deltas. Simplest honest approach: run it and accept its
        internal 1-min cadence, but scale physical time by calling only when
        >=0.25 min accumulated. To keep the box consistent with the clock we
        instead nudge the engine's temperature manually per dt."""
        if dt_min >= 0.25:
            self.box.tick()
            # extra fractional remainder ignored (0.25 granularity)
        else:
            # sub-quarter-minute interpolation: pull temperature 1/4 of a tick
            before = self.box.temperature
            self.box.tick()
            self.box.temperature = before + (self.box.temperature - before) * (dt_min / 0.25)

    # ---------------- failures & recovery ----------------
    def repair(self):
        """Field repair by a service vehicle: full compressor + electrical restore.
        Cargo temperature is NOT reset — thermal recovery takes time realistically."""
        self.compressor = COMPRESSOR_OK
        self.fault = None
        # broaden compressor contactor path first
        self.box.compressor_on = True
        self.box.cooling_efficiency = 1.0
        # sensor health recovered, door confirmed shut, power restored
        self.box.inject("repair")
        self.door_open = False

    def inject_failure(self, kind: str):
        if kind == "compressor_failure":
            self.compressor = COMPRESSOR_FAILED
            self.box.compressor_on = False
        elif kind == "compressor_degradation":
            self.compressor = COMPRESSOR_DEGRADED
            self.box.cooling_efficiency = min(self.box.cooling_efficiency, 0.55)
        elif kind == "door_open":
            self.door_open = True
            self.box.inject("door_open")
        elif kind == "power_failure":
            self.box.inject("power_failure")
        elif kind == "heatwave":
            self.box.ambient_target = 46.0
        elif kind == "sensor_fault":
            self.box.inject("sensor_fault")

    def apply_action(self, action: str) -> bool:
        if action == "activate_backup_cooling":
            ok = self.box.activate_backup_cooling()
            return ok
        if action == "close_door":
            self.door_open = False
            self.box.close_door()
            return True
        if action == "restart_compressor":
            if self.box.power_ok:
                self.box.compressor_on = True
                self.box.cooling_efficiency = 1.0
                self.compressor = COMPRESSOR_OK
                return True
            return False
        if action == "restore_power":
            self.box.restore_power()
            return True
        return False

    # ---------------- helpers ----------------
    def _place_on_route(self, frac: float):
        pts = self.geom
        seg_total = len(pts) - 1
        idx_f = min(max(frac, 0.0), 0.999999) * seg_total
        i = min(seg_total - 1, int(idx_f))
        t = idx_f - i
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        # GPS noise: small meters-scale jitter on the reported position
        jit = self.rng.gauss(0, 0.00004)
        self.lng = x0 + (x1 - x0) * t + jit
        self.lat = y0 + (y1 - y0) * t + jit * 0.7
        self.heading = (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360.0) % 360.0

    def remaining_km(self) -> float:
        return max(0.0, self.total_km - self.done_km)

    def eta_min(self, traffic_factor: float = 1.0) -> float:
        eff = max(8.0, self.avg_speed if self.avg_speed else 30.0)
        return (self.remaining_km() / eff) * 60.0 * max(0.55, traffic_factor)

    def trend_c_per_min(self) -> float:
        vals = [s["true_temperature"] for s in self._snaps[-8:]]
        if len(vals) < 3:
            return 0.0
        x = list(range(len(vals)))
        xm, ym = sum(x) / len(x), sum(vals) / len(vals)
        num = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, vals))
        den = sum((xi - xm) ** 2 for xi in x) or 1
        return num / den  # degC per world-tick-sample (0.25 sim-min steps)

    def time_to_critical_min(self) -> float | None:
        """minutes until box temp exceeds max+2, given current trend"""
        tr = self.trend_c_per_min() * 4.0  # per sim-minute
        if tr <= 0.005:
            return None
        gap = (self.box.mx + 2.0) - self.box.temperature
        return max(0.0, gap / tr) if gap > 0 else 0.0

    def direction_label(self) -> str:
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[int(((self.heading + 22.5) % 360) / 45)]

    def driver_score(self) -> int:
        pen = self.speed_events * 2 + self.harsh_brakes * 3 + self.harsh_accels * 2 + int(self.idle_min / 10)
        return int(max(40, 100 - pen))

    def snapshot(self) -> dict:
        snap = self.box.snapshot()
        return {
            "vehicle_id": self.id,
            "type": self.kind,
            "energy_type": self.energy,
            "lat": round(self.lat, 5), "lng": round(self.lng, 5),
            "heading": round(self.heading, 1), "direction": self.direction_label(),
            "speed_kmh": round(self.speed_kmh, 1),
            "avg_speed_kmh": round(self.avg_speed, 1),
            "max_speed_kmh": round(self.max_speed, 1),
            "speed_limit_kmh": self.speed_limit,
            "accel_mps2": round(self.accel_mps2, 2),
            "trip": {
                "route_id": self.route_id,
                "origin_id": self.origin_id, "destination_id": self.dest_id,
                "distance_total_km": round(self.total_km, 2),
                "distance_completed_km": round(self.done_km, 2),
                "distance_remaining_km": round(self.remaining_km(), 2),
                "eta_min": round(self.eta_min(), 1),
                "route_progress_percent": round(100.0 * self.done_km / max(0.01, self.total_km), 1),
                "eta": self.eta_bundle(),
            },
            "vehicle": {
                "engine_status": "RUNNING" if self.box.power_ok else "BATTERY",
                "fuel_percent": round(self.fuel_pct, 1),
                "battery_percent": round(self.battery_pct, 1),
                "vehicle_health": round(self.vehicle_health, 1),
                "engine_temperature": round(self.engine_temp_c, 1),
            },
            "refrigeration": {
                "compressor_status": self.compressor,
                "cooling_efficiency": round(self.box.cooling_efficiency * 100, 1),
                "temperature": snap["temperature"],
                "humidity": snap["humidity"],
                "door_open": self.door_open,
                "backup_cooling": self.box.backup_cooling,
                "power_ok": self.box.power_ok,
            },
            "cargo": {
                "cargo_type": self.cargo_type,
                "load_percent": round(100.0 * self.load_units / max(1, self.capacity_units), 1),
                "load_units": self.load_units,
                "cargo_health": snap["cargo_health"],
                "risk_level": self.risk.get("level", "LOW"),
                "risk_score": self.risk.get("score", 0.0),
                "risk_explain": self.risk.get("explain", ""),
                "exposure_ticks": self.over_ticks,
                "time_to_critical_min": (round(self.time_to_critical_min(), 1)
                                         if self.time_to_critical_min() is not None else None),
            },
            "driver": {
                "name": self.driver,
                "state": ("DRIVING" if self.speed_kmh > 2 else
                          "IDLE" if self.box.power_ok else "OFFLINE"),
                "driving_score": self.driver_score(),
                "speeding_events": self.speed_events,
                "harsh_braking": self.harsh_brakes,
                "harsh_accel": self.harsh_accels,
                "idle_min": round(self.idle_min, 1),
            },
            "connectivity": {
                "gps_accuracy_m": round(self.gps_acc, 1),
                "signal_strength": round(self.signal, 1),
            },
            "speeding": {"events": self.speed_events,
                         "time_over_limit_min": round(self.time_over_limit_min, 1),
                         "max_excess_kmh": round(self.max_excess_kmh, 1)},
            "stops": self.stops[-8:],
            "outside_temperature": round(self.box.ambient, 1),
            "route_adherence": round(self.route_adherence, 1),
            "status": self.status,
            "risk_level": self.risk.get("level", "LOW"),
        }

    def alerts_delta(self) -> int:
        """New alert-worthy readings since last poll: harsh events + risk escalation
        + energy below 20%. Used by orchestrator for per-vehicle alert counts."""
        n = self.harsh_brakes + self.harsh_accels + self.speed_events
        energy = self.battery_pct if self.energy == "ELECTRIC" else self.fuel_pct
        if energy < 20.0:
            n += 1
        if self.risk.get("level") in ("HIGH", "CRITICAL"):
            n += 1
        d = max(0, n - self._last_alerts)
        self._last_alerts = n
        return d

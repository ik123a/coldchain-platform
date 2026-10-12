"""Thermal engine — physics-inspired, deterministic-seeded.
per-minute update:
  dT = ambient_pull + door_warm + powerless_warm + noise        (no effective cooling)
  T += (target - T) * cooling_return                            (healthy cooling)
Coefficients are per-minute (1 tick = 1 simulated minute).
"""
from __future__ import annotations
import random

K_AMBIENT = 0.012          # ambient pull factor (2°C/min for a 30°C ambient -> 0.36)
K_COMPRESSOR = 0.14        # healthy cooling return-rate toward target
K_BACKUP = 0.22            # stronger recovery cooling
K_DOOR = 0.22              # warming when door open
K_POWERLESS = 0.10         # passive warming with no cooling at all
K_NOISE = 0.05             # gaussian sigma
K_BATTERY = 1.2            # %/min drain on battery backup
K_DEGRADE = 0.008          # efficiency decay per tick in degrade scenario
K_HEAT_REDUCE = 0.35       # cooling efficiency loss per °C ambient over 36
H_RELAX = 0.06
H_DOOR = 1.4
H_NOISE = 1.0

CAUSES = ("compressor_failure", "door_open", "power_failure",
          "heatwave", "cooling_degradation", "sensor_fault", "multiple_failure", "normal")


class Engine:
    def __init__(self, target=4.0, mn=2.0, mx=8.0, ambient=30.0,
                 hum_min=60.0, hum_max=85.0, seed: int | None = None, profile=None):
        self.target = float(target)
        self.mn, self.mx = float(mn), float(mx)
        self.ambient = float(ambient)
        self.ambient_target = float(ambient)
        self.temperature = self.target + 0.25
        self.humidity = 72.0
        self.hum_min, self.hum_max = float(hum_min), float(hum_max)
        self.door_open = False
        self.compressor_on = True
        self.backup_cooling = False
        self.power_ok = True
        self.battery = 100.0
        self.cargo_health = 100.0
        self.cooling_efficiency = 1.0
        self.scenario = "normal"
        self.hypothetical = False
        self.control_for_hum = False
        self.profile = profile or {"name": "fresh_produce", "freeze_decay": 0.6, "heat_decay": 1.0}
        self.rng = random.Random(seed if seed is not None else random.randrange(1 << 30))
        self._frozen_reported = None   # sensor-fault: freeze reported value

    # ---------------- scenario injection ----------------
    def inject(self, cause: str):
        self.scenario = cause
        if cause == "compressor_failure":
            self.compressor_on = False
        elif cause == "door_open":
            self.door_open = True
        elif cause == "power_failure":
            self.power_ok = False
            self.compressor_on = False
        elif cause == "heatwave":
            self.ambient_target = 46.0
        elif cause == "cooling_degradation":
            pass  # efficiency decays per tick
        elif cause == "sensor_fault":
            self._frozen_reported = round(self.temperature, 2)
        elif cause == "multiple_failure":
            self.power_ok = False
            self.compressor_on = False
            self.door_open = True
            self.ambient_target = 44.0

    # ---------------- recovery actions ----------------
    def activate_backup_cooling(self):
        if self.power_ok or self.battery > 5:
            self.backup_cooling = True
            self.compressor_on = False
            return True
        return False

    def close_door(self):
        self.door_open = False
        if self.scenario == "door_open":
            self.scenario = "normal"

    def restore_power(self):
        self.power_ok = True
        self.compressor_on = True
        self.scenario = "normal" if self.scenario in ("power_failure", "multiple_failure") else self.scenario

    def restart_compressor(self):
        if self.power_ok:
            self.compressor_on = True
            self.cooling_efficiency = min(1.0, self.cooling_efficiency + 0.45)
            self.scenario = "normal"
            return True
        return False

    # ---------------- per-tick physics ----------------
    def tick(self):
        # ambient relaxes to scenario target slowly
        self.ambient += (self.ambient_target - self.ambient) * 0.02

        if self.scenario == "cooling_degradation":
            self.cooling_efficiency = max(0.12, self.cooling_efficiency - K_DEGRADE)

        # A dead compressor delivers no cooling, whatever its last recorded
        # efficiency was. Without this the reported efficiency stayed at 100%
        # after a compressor failure, and incident evidence read
        # "compressor=FAILED, cooling_efficiency=100%" — self-contradictory on
        # the exact line an examiner would read. Efficiency tracks the hardware
        # that is actually running: the compressor, or backup cooling if the
        # compressor is gone but the battery is holding.
        if not self.compressor_on and not (self.backup_cooling and self.power_ok):
            self.cooling_efficiency = 0.0

        # cooling works if power and compressor healthy, or backup cooling on power
        healthy = self.power_ok and self.compressor_on and self.cooling_efficiency > 0.2
        recovery = self.backup_cooling and self.power_ok

        if healthy or recovery:
            heat_penalty = max(0.0, (self.ambient - 36) * K_HEAT_REDUCE / 10.0)
            eff = self.cooling_efficiency * (K_BACKUP if (recovery or self.backup_cooling) else K_COMPRESSOR)
            eff = max(0.10, eff - heat_penalty)
            # exponential return toward target
            self.temperature += (self.target - self.temperature) * min(0.45, eff)
        else:
            # no effective cooling -> warm toward ambient
            d = (self.ambient - self.temperature) * K_AMBIENT
            if self.door_open:
                d += K_DOOR
            if not self.power_ok:
                d += K_POWERLESS
            self.temperature += d
            if self.backup_cooling and self.power_ok:  # unreachable (recovery branch)
                pass
            # battery drains when on backup power without cooling
            if not self.power_ok:
                self.battery = max(0.0, self.battery - K_BATTERY)

        self.temperature += self.rng.gauss(0, K_NOISE)

        # humidity
        dh = (72.0 - self.humidity) * H_RELAX
        if self.door_open:
            dh += H_DOOR
        self.humidity = max(35.0, min(98.0, self.humidity + dh + self.rng.gauss(0, H_NOISE)))

        # cargo degradation (exposure-weighted, cold-side gentler)
        over = max(0.0, self.temperature - self.mx)
        under = max(0.0, self.mn - self.temperature)
        if over > 0:
            w = over * (1.0 + 0.10 * max(0.0, over - 2.0))
            self.cargo_health = max(0.0, self.cargo_health - w * 0.11)
        elif under > 0:
            self.cargo_health = max(0.0, self.cargo_health - under * 0.04)

        # battery-assisted backup cooling drain while active
        if self.backup_cooling and self.power_ok:
            self.battery = max(0.0, self.battery - K_BATTERY * 0.8)

        # sensor freeze fault: report the stored frozen reading
        reported = self._frozen_reported if self._frozen_reported is not None else self.temperature

        return self.snapshot(reported)

    def snapshot(self, reported_temp=None):
        return {
            "temperature": round(reported_temp if reported_temp is not None else self.temperature, 2),
            # A frozen sensor reports a plausible, unchanging value, so nothing
            # downstream could tell a healthy box from a faulty probe. Exposing
            # the freeze lets the incident catalogue classify sensor_fault
            # instead of leaving it silently undetectable.
            "sensor_frozen": self._frozen_reported is not None,
            "true_temperature": round(self.temperature, 2),
            "humidity": round(self.humidity, 1),
            "ambient_temperature": round(self.ambient, 1),
            "door_open": self.door_open,
            "compressor_on": self.compressor_on and self.power_ok,
            "backup_cooling": self.backup_cooling,
            "power_ok": self.power_ok,
            "battery_level": round(self.battery, 1),
            "cargo_health": round(self.cargo_health, 1),
            "cooling_efficiency": round(self.cooling_efficiency, 3),
            "scenario": self.scenario,
            "target": self.target, "mn": self.mn, "mx": self.mx,
        }

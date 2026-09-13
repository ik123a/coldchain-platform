"""Anomaly detection — distinguishes sensor faults from real environmental issues
and detects threshold excursions. Operates on recent engine snapshots."""
from __future__ import annotations
from .engine import Engine

JUMP_LIMIT = 4.0      # > 4°C jump between consecutive ticks impossible physically
SUSTAIN_N = 4         # consecutive over-limit readings required to confirm excursion


class AnomalyDetector:
    def __init__(self):
        self._last = None
        self._over_run = 0
        self._frozen_run = 0

    def update(self, engine: Engine):
        """Returns one of: None | 'sensor_fault' | 'excursion'.
        Also emits meta used by monitoring agent (alerts)."""
        snap = engine.snapshot()
        true_t = snap["true_temperature"]
        rep_t = snap["temperature"]
        mx, mn = engine.mx, engine.mn

        # --- sensor fault detection ---
        # case 1: reported != true beyond noise (frozen sensor)
        if abs(rep_t - true_t) > 2.5:
            self._frozen_run = 0
            self._last = rep_t
            return {"kind": "sensor_fault",
                    "reason": f"reported {rep_t}°C diverges from true {true_t}°C",
                    "severity": "MEDIUM"}
        # case 2: frozen readings (identical value repeatedly)
        if self._last is not None and abs(rep_t - self._last) < 0.01:
            self._frozen_run += 1
        else:
            self._frozen_run = 0
        if self._frozen_run >= 25:
            self._last = rep_t
            return {"kind": "sensor_fault",
                    "reason": f"identical reading {rep_t}°C repeated for 25+ ticks (frozen sensor)",
                    "severity": "MEDIUM"}
        # case 3: impossible jump
        if self._last is not None and abs(rep_t - self._last) > JUMP_LIMIT and not engine.scenario.startswith("#"):
            # a genuine failure ramps (rarely jumps instantly); a jump > 4°C is suspicious
            self._last = rep_t
            return {"kind": "sensor_fault",
                    "reason": f"impossible jump {self._last if self._last is not None else rep_t}°C -> {rep_t}°C",
                    "severity": "MEDIUM"}

        self._last = rep_t

        # --- threshold excursion (on TRUE temperature, sustained) ---
        if true_t > mx or true_t < mn:
            self._over_run += 1
        else:
            self._over_run = 0
        if self._over_run >= SUSTAIN_N:
            return {"kind": "excursion",
                    "reason": f"temperature {true_t}°C outside [{mn}, {mx}]°C for {self._over_run} ticks",
                    "severity": ("CRITICAL" if (true_t - mx) > 4 or (mn - true_t) > 4 else "HIGH")}
        return None

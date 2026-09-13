"""Simulated per-road traffic + ambient weather, seed-driven and time-varying."""
from __future__ import annotations
import random

LEVELS = ["LOW", "MODERATE", "HIGH", "SEVERE"]
FACTOR = {"LOW": 1.0, "MODERATE": 1.3, "HIGH": 1.8, "SEVERE": 2.6}
AMBIENT = {"NORMAL": 33.0, "HEATWAVE": 44.0, "RAIN": 27.0, "FOG": 25.0}


class TrafficWorld:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.segments: dict[str, str] = {}
        self.weather = "NORMAL"
        self.ambient_c = AMBIENT["NORMAL"]

    def level_for(self, origin_id: str, dest_id: str) -> str:
        key = f"{origin_id}>{dest_id}"
        if key not in self.segments or self.rng.random() < 0.02:
            self.segments[key] = self.rng.choices(LEVELS, weights=[6, 3, 1.5, 0.5])[0]
        return self.segments[key]

    def factor_for(self, origin_id: str, dest_id: str) -> float:
        return FACTOR[self.level_for(origin_id, dest_id)]

    def maybe_weather(self) -> str:
        if self.rng.random() < 0.002:
            self.weather = self.rng.choices(["NORMAL", "HEATWAVE", "RAIN", "FOG"],
                                            weights=[7, 1.5, 1, 0.5])[0]
        self.ambient_c = AMBIENT[self.weather]
        return self.weather

    def state(self) -> dict:
        return {"weather": self.weather, "ambient_c": self.ambient_c,
                "segments": dict(list(self.segments.items())[:40])}

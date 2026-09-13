"""Fleet simulation clock.

ONE compression constant: at speed=1 the world advances 0.5 sim-minutes per
wall second (30x real time). Everything — movement, thermal physics,
traffic — derives from dt_sim so the map and the thermodynamics share
the same clock. Speed multiplier (0.25..100) scales it.
"""
from __future__ import annotations
import asyncio, time

MIN_SPEED, MAX_SPEED = 0.25, 100.0
SIM_MIN_PER_WALL_SEC_AT_1X = 0.5
WORLD_HZ = 4.0


class SimClock:
    def __init__(self, speed: float = 2.0):
        self.speed = float(max(MIN_SPEED, min(MAX_SPEED, speed)))
        self.sim_minute = 0.0
        self._last = None

    def set_speed(self, speed: float) -> float:
        self.speed = float(max(MIN_SPEED, min(MAX_SPEED, speed)))
        return self.speed

    def dt_wall(self) -> float:
        """seconds since last call (first call returns 0)"""
        now = time.perf_counter()
        dt = 0.0 if self._last is None else min(0.5, now - self._last)
        self._last = now
        return dt

    def dt_sim_min(self) -> float:
        """sim-minutes elapsed since last dt_wall call"""
        return self.dt_wall() * SIM_MIN_PER_WALL_SEC_AT_1X * self.speed

    async def run(self, on_tick) -> None:
        while True:
            t0 = time.perf_counter()
            self.sim_minute += self.dt_sim_min()
            await on_tick()
            spent = time.perf_counter() - t0
            await asyncio.sleep(max(0.0, (1.0 / WORLD_HZ) - spent))

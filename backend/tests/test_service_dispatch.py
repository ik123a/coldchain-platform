"""Service dispatch: navigation, arrival, completion, and no-duplicate guarantees.

THE DEFECT THESE PIN DOWN
-------------------------
A dispatched service truck never closed on its target. `_service_progress` only
checked `d < 0.8 km` for arrival and had NO navigation branch, while the twin's
generic `step()`/-`_place_on_route()` movement walks a route to its `dest_id` —
which for a service truck is whatever cargo destination it spawned with, never
the truck it was dispatched to repair. Measured live before the fix: the two
service trucks sat 4.93 km and 6.68 km from their assigned truck and the gap
never closed, so `service.completed` was unreachable.

Each test below can FAIL against the pre-fix code, which is the point.

Database isolation: DATABASE_URL is redirected before any app import, so the
live backend/coldchain.db is never opened.
"""
import math
import os
import sys
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="cc_service_")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + os.path.join(
    _TMP, "test.db").replace("\\", "/")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from app.database.engine import Base, engine  # noqa: E402
from app.models import entities as _entities  # noqa: F401,E402
from app.models import fleet as _fleet  # noqa: F401,E402
from app.simulation.fleet_orchestrator import (  # noqa: E402
    FleetOrchestrator, SERVICE_ARRIVAL_KM, haversine_km)


def build(n=4):
    """A live orchestrator with a spawned fleet, no DB needed for the maths."""
    F = FleetOrchestrator(n)
    F._spawn_fleet()
    return F


def cargo_and_service(F):
    cargo = [v for v in F.vehicles.values() if v.kind != "SERVICE_TRUCK"]
    svc = [v for v in F.vehicles.values() if v.kind == "SERVICE_TRUCK"]
    return cargo, svc


def advance(F, ticks=1, dt=0.5):
    """One world step per vehicle, matching the real tick loop's order."""
    for _ in range(ticks):
        F.sim_minute += dt
        for v in F.vehicles.values():
            v.sim_minute = F.sim_minute
            v.step(dt, 1.0, F.traffic.ambient_c)
        F._service_progress(dt)


def place(v, lat, lng):
    """Teleport a twin by rewriting the head of its geometry (the sim's own
    representation of position), so a test can start it at a known distance."""
    v.geom = [[lng, lat]] + list(v.geom[1:])
    v.done_km = 0.0
    v._place_on_route(0.0)


async def dispatch_far(F, target, offset_km=0.055):
    """Dispatch a service truck, then put the truck that was ACTUALLY dispatched
    on an AWAY-BOUND route far from its target.

    `dispatch_service` picks the nearest available service truck, so a test that
    positions `svc[0]` may move a truck that was never dispatched.

    The route is deliberately pointed AWAY from the target. Merely teleporting the
    truck is not enough: the twin walks its own geometry, so if that geometry
    still runs toward the target it would arrive even with no navigation logic —
    and the test would pass without the fix. A route heading the other way means
    arrival is only possible if something re-targets the truck, which is exactly
    the behaviour under test.
    """
    res = await F.dispatch_service(target.id, "repair")
    if not res.get("dispatched"):
        raise AssertionError(f"dispatch refused: {res}")
    svc = F.vehicles[res["service_id"]]

    # Heading north on a straight leg while the target sits to the south.
    start_lat = target.lat + offset_km
    svc.geom = [[target.lng, start_lat], [target.lng, start_lat + 0.05],
                [target.lng, start_lat + 0.10]]
    svc.total_km = 11.1          # ~0.10 deg of latitude
    svc.done_km = 0.0
    svc._place_on_route(0.0)
    return res, svc


class ServiceDispatchTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def test_distance_decreases_from_outside_the_arrival_radius(self):
        """The core defect: a truck dispatched from far away must close the gap."""
        F = build()
        cargo, _ = cargo_and_service(F)
        target = cargo[0]

        res, svc_t = await dispatch_far(F, target)
        d0 = haversine_km((svc_t.lng, svc_t.lat), (target.lng, target.lat))
        self.assertGreater(d0, SERVICE_ARRIVAL_KM * 2,
                           "precondition: service truck starts outside the radius")
        self.assertNotAlmostEqual(d0, 0.0, places=2)

        # Freeze the TARGET so we measure the service truck's own navigation
        # rather than the target driving toward it.
        target.step = lambda *a, **k: None  # type: ignore[assignment]

        distances = []
        for _ in range(80):
            F.sim_minute += 0.5
            for v in F.vehicles.values():
                if v is target:
                    continue
                v.sim_minute = F.sim_minute
                v.step(0.5, 1.0, F.traffic.ambient_c)
            F._service_progress(0.5)
            distances.append(haversine_km((svc_t.lng, svc_t.lat),
                                          (target.lng, target.lat)))
            if distances[-1] < SERVICE_ARRIVAL_KM:
                break

        self.assertLess(distances[-1], distances[0],
                        f"distance never decreased: {distances[0]:.2f} -> {distances[-1]:.2f} km")
        self.assertLess(distances[-1], SERVICE_ARRIVAL_KM,
                        f"service truck did not arrive within {SERVICE_ARRIVAL_KM} km "
                        f"(closest {distances[-1]:.2f} km after {len(distances)} ticks)")

    async def test_completion_event_is_emitted_after_arrival(self):
        """`service.completed` must be queued once the truck is on scene."""
        F = build()
        cargo, _ = cargo_and_service(F)
        target = cargo[0]

        emitted = []
        F._queue_event_nowait = lambda etype, payload: emitted.append((etype, payload))

        res = await F.dispatch_service(target.id, "repair")
        self.assertTrue(res.get("dispatched"), f"dispatch refused: {res}")
        svc_t = F.vehicles[res["service_id"]]
        place(svc_t, target.lat + 0.002, target.lng)   # on scene

        F._service_progress(0.5)

        kinds = [e for e, _ in emitted]
        self.assertIn("service.completed", kinds,
                      f"no completion event after arrival (got {kinds})")
        payload = next(p for e, p in emitted if e == "service.completed")
        self.assertEqual(payload["vehicle_id"], target.id)
        self.assertEqual(payload["service_id"], svc_t.id)
        self.assertEqual(payload["task"], "repair")

    async def test_no_completion_before_arrival(self):
        """A truck still far away must NOT emit completion."""
        F = build()
        cargo, _ = cargo_and_service(F)
        target = cargo[0]

        emitted = []
        F._queue_event_nowait = lambda etype, payload: emitted.append((etype, payload))

        await dispatch_far(F, target)   # ~6 km away
        F._service_progress(0.5)

        self.assertNotIn("service.completed", [e for e, _ in emitted],
                         "completion fired while the truck was still kilometres away")

    async def test_no_duplicate_completion_for_the_same_task(self):
        """Arriving twice must not emit twice, and repair must not re-apply."""
        F = build()
        cargo, _ = cargo_and_service(F)
        target = cargo[0]

        emitted = []
        F._queue_event_nowait = lambda etype, payload: emitted.append((etype, payload))

        res = await F.dispatch_service(target.id, "repair")
        self.assertTrue(res.get("dispatched"), f"dispatch refused: {res}")
        svc_t = F.vehicles[res["service_id"]]
        place(svc_t, target.lat + 0.002, target.lng)

        for _ in range(6):          # several ticks on scene
            F._service_progress(0.5)

        completions = [p for e, p in emitted if e == "service.completed"]
        self.assertEqual(len(completions), 1,
                         f"expected exactly one completion, got {len(completions)}")
        self.assertNotIn(target.id, F.service_pending,
                         "service_pending not cleared after completion")
        self.assertNotIn(svc_t.id, F.service_tasks,
                         "service_tasks not cleared after completion")

    async def test_removed_target_does_not_wedge_the_service_truck(self):
        """If the target disappears, the task must be released, not retried forever."""
        F = build()
        cargo, _ = cargo_and_service(F)
        target = cargo[0]

        res, svc_t = await dispatch_far(F, target)
        del F.vehicles[target.id]
        F._service_progress(0.5)

        self.assertNotIn(svc_t.id, F.service_tasks,
                         "service task survived its target being removed")
        self.assertNotIn(target.id, F.service_pending,
                         "service_pending survived its target being removed")

    async def test_no_dead_zone_between_arrival_and_retarget(self):
        """The re-target threshold must not exceed the arrival radius.

        HONEST SCOPE: this asserts the GUARD INVARIANT, not a reproduced
        stranding. A behavioural version of this test was written first and it
        PASSED against the old code — because a truck starting just outside the
        radius simply drives away, grows past the larger threshold, and is then
        re-targeted anyway. So the old code could not be shown to strand a truck
        this way, and claiming it did would be unsupported.

        What IS verifiable is the invariant: if the code only re-targets beyond
        `arrival * N` for N > 1, there exists a band where a truck is too close to
        re-target and too far to arrive. Widening the guard to the arrival radius
        removes that band by construction.
        """
        import inspect

        src = inspect.getsource(FleetOrchestrator._service_progress)
        self.assertIn("d > SERVICE_ARRIVAL_KM and", src.replace("  ", " "),
                      "re-target guard no longer covers everything outside the "
                      "arrival radius — a dead band may exist between arrival and "
                      "re-target thresholds")
        self.assertNotIn("SERVICE_ARRIVAL_KM * 2.5", src,
                         "re-target threshold is a multiple of the arrival radius, "
                         "which leaves a band where the truck can neither arrive "
                         "nor re-target")
        self.assertNotIn("SERVICE_ARRIVAL_KM * 2 and", src,
                         "re-target threshold is a multiple of the arrival radius")

    async def test_two_diverts_in_one_sim_minute_get_distinct_route_ids(self):
        """`fleet_routes.id` embeds int(sim_minute), which is not unique.

        Two diverts for the same vehicle to the same target inside one sim-minute
        used to produce an identical id, and the insert died with
        `UNIQUE constraint failed: fleet_routes.id` — surfacing as HTTP 500 on the
        operator's approval. The route-sequence counter must make them distinct.
        """
        from sqlalchemy import text

        F = build()
        cargo, _ = cargo_and_service(F)
        v = cargo[0]

        bundle = {"target": "WH-001", "reason": "unit test", "scored": {}}
        for _ in range(3):                     # same vehicle, same target, same minute
            await F._apply_divert(v, bundle)

        async with engine.begin() as conn:
            rows = (await conn.execute(text(
                "SELECT id FROM fleet_routes WHERE vehicle_id = :vid"), {"vid": v.id})).fetchall()
        ids = [r[0] for r in rows]
        self.assertEqual(len(ids), 3, f"expected 3 route rows, got {ids}")
        self.assertEqual(len(set(ids)), 3, f"route ids collided: {ids}")
        self.assertGreaterEqual(F._route_seq, 3,
                                "route sequence counter did not advance")


if __name__ == "__main__":
    unittest.main(verbosity=2)

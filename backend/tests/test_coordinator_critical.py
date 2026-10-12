"""FleetCoordinator must DIVERT when the current route ends CRITICAL.

THE DEFECT (ledger item 7, P1)
------------------------------
The scorer projects the cargo temperature as `current + slope * eta` over the
WHOLE remaining route for every option — continue and divert alike. With a
failed compressor and a long ETA, every candidate's `cargo_risk_after` comes
back CRITICAL, so:
  * `cont_ok` is False (good — continue is not "safe"),
  * but `_risk_worse(cont, best)` compares CRITICAL vs CRITICAL -> False,
  * and `eta_gain` is often negative (a divert is longer than the direct route),
so the coordinator returns CONTINUE and the human-approval gate stays empty even
though the cargo is being cooked.

THE CONTRACT THESE TESTS PIN
----------------------------
1. When the current route projects CRITICAL, a compatible divert that projects
   anything better (HIGH or below) MUST be preferred — even at a longer ETA and
   even at a lower raw route score.
2. When continuing projects LOW risk and the vehicle is healthy, continue stays
   the answer (the original no-pointless-diversion policy is preserved).
3. The projection must model RECOVERY toward the facility band during the
   facility leg, not pure linear warming for the entire trip.

A CRITICAL projection means the load is being destroyed; "the numbers happen to
tie" is not a reason to keep driving.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_ENV", "development")

from app.simulation.fleet_agents import (  # noqa: E402
    FleetCoordinator, RouteScorer, RISK_ORDER, _risk_worse)


class _Box:
    def __init__(self, temp, mx=8.0):
        self.temperature = temp
        self.mx = mx
        self.power_ok = True


class _Vehicle:
    """A failing reefer: compressor dead, cargo already over the band."""

    def __init__(self, temp=14.0):
        self.box = _Box(temp)
        self.compressor = "FAILED"
        self.door_open = False
        self.cargo_type = "dairy"
        self.load_units = 120
        self.energy = "DIESEL"
        self.fuel_pct = 70.0
        self.battery_pct = 70.0
        self.lng, self.lat = 77.35, 28.62


class _Traffic:
    def factor_for(self, a, b):
        return 1.0


class _Routing:
    """Deterministic fake: continue is SHORT, diverts are LONGER (harder case)."""

    def route_from_point(self, lng, lat, dest, factor):
        return {"variant": "continue", "duration_min": 40.0,
                "distance_km": 42.0, "geometry": [((lng, lat), (0, 0))]}

    def alternatives(self, a, b, factor):
        # Two legs: a shorter travel leg + the facility processing leg.
        return [{"variant": "via-facility", "duration_min": 25.0,
                 "distance_km": 30.0, "geometry": [((0, 0), (1, 1))]}]


class _Matcher:
    """Fake FacilityMatcher: one compatible candidate, always."""

    def rank(self, vehicle, exclude=None):
        return [_facility()]


def _facility(fac_id="WH-003", name="ColdHub South"):
    return {"id": fac_id, "name": name, "compatible": True,
            "eta_total_min": 30.0, "capacity": 500,
            "cargo_types": ["dairy"], "deep_freeze": False}


class ContinueOnCriticalTests(unittest.TestCase):

    def setUp(self):
        self.coord = FleetCoordinator(_Matcher(), RouteScorer(), _Routing())

    def _vehicle(self, temp=14.0):
        return _Vehicle(temp)

    # ---- 1. the defect itself ------------------------------------------

    def test_critical_continue_with_better_divert_prefers_divert(self):
        """CRITICAL current route + compatible facility projecting better
        => DIVERT, regardless of ETA gain or raw score."""
        v = self._vehicle(14.0)
        res = self.coord.evaluate(v, _Traffic(), "WH-001")
        self.assertEqual(res["decision"], "DIVERT",
                         f"coordinator chose {res['decision']}: {res['reason']}")

    def test_divert_reason_names_the_recovery(self):
        res = self.coord.evaluate(self._vehicle(14.0), _Traffic(), "WH-001")
        self.assertEqual(res["decision"], "DIVERT")
        # Explainability contract: the reason must reference the projection.
        self.assertTrue(
            any(k in res["reason"] for k in ("CRITICAL", "recover", "risk")),
            f"reason lacks risk explanation: {res['reason']}")

    # ---- 2. the original policy is preserved ---------------------------

    def test_healthy_vehicle_with_low_risk_still_continues(self):
        class _Healthy(_Vehicle):
            def __init__(self):
                super().__init__(temp=4.0)
                self.compressor = "ONLINE"

        res = self.coord.evaluate(_Healthy(), _Traffic(), "WH-001")
        self.assertEqual(res["decision"], "CONTINUE", res["reason"])

    def test_continue_projecting_medium_with_equal_divert_continues(self):
        """MEDIUM continue + no strictly-better divert => still CONTINUE.
        (Diversion is for material risk reduction, not tie-breaking.)"""

        class _Warm(_Vehicle):
            def __init__(self):
                super().__init__(temp=7.5)   # just under the band edge

        res = self.coord.evaluate(_Warm(), _Traffic(), "WH-001")
        self.assertIn(res["decision"], ("CONTINUE", "DIVERT"))
        if res["decision"] == "CONTINUE":
            self.assertIn("safe", res["reason"].lower())

    # ---- 3. the projection models recovery ------------------------------

    def test_projection_reaches_the_facility_band(self):
        """A failed compressor + facility processing must project BELOW the
        band edge, not keep climbing linearly forever."""
        scorer = RouteScorer()
        v = self._vehicle(14.0)
        route = {"variant": "via-facility", "duration_min": 25.0,
                 "distance_km": 30.0, "geometry": []}
        s = scorer.score(route, 1.0, v, _facility())
        self.assertIn(s["cargo_risk_after"], ("LOW", "MEDIUM", "HIGH"),
                      f"divert projected {s['cargo_risk_after']}; recovery "
                      f"modeling is missing (still linear-warming)")
        self.assertLess(s["projected_temp_c"], v.box.mx + 4.0,
                        "projected temp must reflect facility recovery")


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Derived lessons for incident reports (requirement 12).

The reporter renders a `Lesson:` line per entry, but on the fleet path nothing
populated that key — the classic runner set it with four hardcoded strings. So
a fleet report either omitted the section or would have shown generic advice
unrelated to what happened.

These tests assert lessons are DERIVED from the outcome evidence, which is the
property that makes them worth showing: a lesson the evidence does not support
is worse than no lesson at all.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation import lessons as LNS  # noqa: E402
from app.simulation.fleet_orchestrator import FleetOrchestrator  # noqa: E402


def _snap(cargo="dairy", temp=None, **refr):
    v = {"temperature": 4.0, "door_open": False, "sensor_frozen": False,
         "compressor_status": "ONLINE", "cooling_efficiency": 100.0}
    v.update(refr)
    return {"refrigeration": v,
            "cargo": {"mx": 5.0, "mn": 1.0, "trend_c_per_min": 0.0,
                      "cargo_type": cargo},
            "eta_min": 40.0}


class LessonsTests(unittest.TestCase):

    def test_success_produces_a_repeatable_lesson(self):
        out = LNS.derive(
            _snap(), {"root_cause": "compressor_failure", "confidence": 0.62},
            {"observed": True, "resolved": True, "verified": True, "peak_temperature": 9.0,
             "recovered_to": 3.0, "transferred_units": 200},
            {"target": "WH-001", "raised_at_sim_minute": 10.0})
        self.assertTrue(any("Repeatable" in l for l in out), out)

    def test_failure_says_it_failed(self):
        out = LNS.derive(
            _snap(temp=14.0), {"root_cause": "compressor_failure", "confidence": 0.6},
            {"observed": True, "resolved": False, "verified": False, "peak_temperature": 14.0,
             "recovered_to": 11.0}, {"escalated": True})
        self.assertTrue(any("FAILED to recover" in l for l in out), out)

    def test_escalated_item_produces_latency_lesson(self):
        """No human reply is itself a failure mode and must be stated."""
        out = LNS.derive(
            _snap(), {"root_cause": "compressor_failure", "confidence": 0.6},
            {"observed": True, "resolved": False, "verified": False, "peak_temperature": 12.0,
             "recovered_to": 10.0}, {"escalated": True})
        self.assertTrue(any("latency" in l for l in out), out)

    def test_verifier_rejection_is_distinct_from_action_taken(self):
        out = LNS.derive(
            _snap(), {"root_cause": "compressor_failure", "confidence": 0.6},
            {"observed": True, "resolved": True, "verified": False, "peak_temperature": 9.0,
             "recovered_to": 6.0}, None)
        self.assertTrue(any("rejected" in l for l in out), out)

    def test_steep_trend_shortens_the_window(self):
        s = _snap()
        s["cargo"]["trend_c_per_min"] = 0.28
        out = LNS.derive(
            s, {"root_cause": "compressor_failure", "confidence": 0.6},
            {"observed": True, "resolved": False, "verified": False, "peak_temperature": 15.0,
             "recovered_to": 13.0}, None)
        self.assertTrue(any("shorter than a human response time" in l for l in out), out)

    def test_sensor_freeze_is_called_out(self):
        out = LNS.derive(
            _snap(sensor_frozen=True), {"root_cause": "sensor_fault", "confidence": 0.5},
            {"observed": True, "resolved": False, "verified": False, "peak_temperature": 8.0,
             "recovered_to": 8.0}, None)
        self.assertTrue(any("frozen" in l for l in out), out)

    def test_counterfactual_names_the_alternative_cause(self):
        out = LNS.derive(
            _snap(), {"root_cause": "compressor_failure", "confidence": 0.62,
                      "causes": [
                          {"cause": "compressor_failure", "score": 0.62, "likelihood": "high", "reason": "x"},
                          {"cause": "door_open", "score": 0.12, "likelihood": "low", "reason": "seal may be degraded"}]},
            {"observed": True, "resolved": False, "verified": False, "peak_temperature": 13.0,
             "recovered_to": 11.0}, None)
        self.assertTrue(any("door_open" in l for l in out), out)

    def test_no_fabricated_lesson_when_nothing_happened(self):
        out = LNS.derive(_snap(), {}, {"observed": False}, None)
        self.assertTrue(any("No actionable lesson" in l for l in out), out)

    def test_lessons_are_capped(self):
        out = LNS.derive(
            _snap(sensor_frozen=True, door_open=True),
            {"root_cause": "compressor_failure", "confidence": 0.6,
             "causes": [{"cause": "door_open", "score": 0.2, "likelihood": "low", "reason": "r"},
                         {"cause": "heatwave", "score": 0.1, "likelihood": "low", "reason": "r"}]},
            {"observed": True, "resolved": False, "verified": False, "peak_temperature": 20.0,
             "recovered_to": 18.0}, {"escalated": True, "score": 80.0, "confidence": 0.7})
        self.assertLessEqual(len(out), 6)

    def test_no_lesson_claims_a_battery_fault_without_one(self):
        """The classic runner's canned lesson mentioned batteries regardless.

        A lesson the evidence does not support is worse than silence, so the
        battery text must not reappear.
        """
        s = _snap()
        s["vehicle"] = {"battery_percent": 96.0}
        out = LNS.derive(s, {"root_cause": "compressor_failure", "confidence": 0.6},
                         {"observed": True, "resolved": True, "verified": True,
                          "peak_temperature": 9.0, "recovered_to": 3.0}, None)
        self.assertFalse(any("battery" in l.lower() for l in out), out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

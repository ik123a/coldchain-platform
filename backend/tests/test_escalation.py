"""Escalation of unanswered critical recommendations (requirement 15).

The brief: warn first, and if no reply comes, let the agent flag it itself.
Before this the agent asked for help and then waited indefinitely.

These tests drive the real orchestrator with a real critical fault and NO
operator response, then assert the escalation happened — and, critically,
that it did NOT execute the divert. Escalating is not the same as acting.
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation.fleet_orchestrator import FleetOrchestrator  # noqa: E402


class EscalationTests(unittest.IsolatedAsyncioTestCase):

    async def _drive(self, ticks=70, ambient=33.0):
        """Run a fleet with one compressor failure and no operator response."""
        F = FleetOrchestrator(3)
        F._spawn_fleet()
        # Short grace period so the test does not have to simulate forever.
        F.ESCALATE_AFTER_SIM_MIN = 4.0
        # Auto-approve must stay OFF: if it fires first, escalation would never
        # get the chance and the test would pass for the wrong reason.
        F.AUTO_APPROVE_TIMEOUT_S = 0.0
        F.require_approval = True

        v = [x for x in F.vehicles.values() if x.kind != "SERVICE_TRUCK"][0]
        v.inject_failure("compressor_failure")
        for _ in range(ticks):
            F.sim_minute += 0.5
            await F._escalate_unanswered()
            F.traffic.maybe_weather()
            for veh in F.vehicles.values():
                veh.step(0.5, 1.0, ambient)
            # Raise the recommendation the way the real tick does once the
            # coordinator decides a divert is warranted. Without this there is
            # no approval in the queue and escalation has nothing to act on.
            if v.id not in F.incident_db and v.box.temperature > v.box.mx:
                await F._check_incident(v, v.snapshot())
            if (v.id in F.incident_db
                    and not any(p["vehicle_id"] == v.id
                                for p in F.pending_approvals.values())):
                await F._decide(v)
        return F, v

    async def test_escalation_fires_without_operator_response(self):
        F, v = await self._drive()
        pending = list(F.pending_approvals.values())
        self.assertTrue(pending, "expected a recommendation awaiting approval")
        escalated = [p for p in pending if p.get("escalated")]
        self.assertTrue(escalated,
                        "critical recommendation left unanswered was never "
                        "escalated by the agent")

    async def test_escalation_does_not_execute_the_divert(self):
        """The alarm is raised; the human still decides."""
        F, v = await self._drive()
        for p in F.pending_approvals.values():
            if p.get("escalated"):
                self.assertEqual(p["status"], "PENDING",
                                 "escalated item must stay pending, not resolved")
                self.assertNotIn(v.id, F.resolved_approvals)

    async def test_escalation_is_idempotent(self):
        """A second pass must not re-escalate or duplicate the event."""
        F, v = await self._drive()
        before = len([e for e in F.event_ring
                      if e.get("source") == "ai.escalation"])
        for _ in range(10):
            F.sim_minute += 0.5
            await F._escalate_unanswered()
        after = len([e for e in F.event_ring
                     if e.get("source") == "ai.escalation"])
        self.assertEqual(before, after, "escalation fired more than once")

    async def test_low_severity_is_not_escalated(self):
        """Nagging about a LOW item trains an operator to ignore the queue."""
        F = FleetOrchestrator(3)
        F._spawn_fleet()
        F.ESCALATE_AFTER_SIM_MIN = 1.0
        F.AUTO_APPROVE_TIMEOUT_S = 0.0
        F.pending_approvals["k-low"] = {
            "key": "k-low", "vehicle_id": "TRUCK-X", "incident_id": None,
            "severity": "LOW", "prediction": {"verdict": "STABLE"},
            "raised_at_sim_minute": 0.0, "status": "PENDING",
            "escalated": False,
        }
        F.sim_minute = 99.0
        await F._escalate_unanswered()
        self.assertFalse(F.pending_approvals["k-low"]["escalated"],
                         "a LOW-severity item must not escalate")

    async def test_zero_disables_escalation(self):
        F = FleetOrchestrator(3)
        F._spawn_fleet()
        F.ESCALATE_AFTER_SIM_MIN = 0.0
        F.pending_approvals["k"] = {
            "key": "k", "vehicle_id": "T", "incident_id": None,
            "severity": "CRITICAL", "prediction": {"verdict": "CRITICAL"},
            "raised_at_sim_minute": 0.0, "status": "PENDING", "escalated": False,
        }
        F.sim_minute = 999.0
        await F._escalate_unanswered()
        self.assertFalse(F.pending_approvals["k"]["escalated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

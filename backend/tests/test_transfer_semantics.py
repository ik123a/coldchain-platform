"""Terminal-state integration tests for _check_arrival (real orchestrator path).

These drive FleetOrchestrator._check_arrival itself rather than a mirrored
helper, so the ordering fix is exercised where it actually runs.

Database isolation: DATABASE_URL is redirected to a throwaway temp file BEFORE
any app module is imported. engine.py reads that variable at import time, so the
live backend/coldchain.db is never opened. The file is deleted on exit.

Run:  backend\\.venv\\Scripts\\python.exe tests\\test_transfer_semantics.py
"""
import os
import shutil
import sys
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="cc_recovery_")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + os.path.join(
    _TMP, "test.db").replace("\\", "/")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import insert, select, text  # noqa: E402
from app.database.engine import Base, engine  # noqa: E402
from app.models.entities import Incident  # noqa: E402
from app.models.fleet import CargoTransfer  # noqa: E402
from app.simulation.fleet_agents import FacilityMatcher, FleetCoordinator  # noqa: E402
from app.simulation.fleet_orchestrator import FleetOrchestrator  # noqa: E402
from app.simulation.routing import RoutingService  # noqa: E402


class TransferSemanticsTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Per-test, not class-level: IsolatedAsyncioTestCase ignores
        # asyncSetUpClass, and each test gets a fresh event loop.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for table in ("ai_analyses", "incidents", "fleet_cargo_transfers",
                          "fleet_vehicle_events"):
                await conn.execute(text("DELETE FROM " + table))

    async def asyncTearDown(self):
        # aiosqlite connections are loop-bound; drop them between tests.
        await engine.dispose()

    def _orch(self, n=2):
        F = FleetOrchestrator(n)
        # Keep the test offline and fast: the "auto" router probes OSRM first.
        F.routing = RoutingService("fallback")
        F.matcher = FacilityMatcher(F.routing, F.warehouses)
        F.coordinator = FleetCoordinator(F.matcher, F.scorer, F.routing)
        F._spawn_fleet()
        return F

    async def _arriving(self, F, temp, mn, mx, backup, units, dest=None):
        """Put one vehicle at ARRIVED with a real incident row behind it."""
        v = next(x for x in F.vehicles.values() if x.kind != "SERVICE_TRUCK")
        v.status = "ARRIVED"
        v.load_units = units
        v.box.mn, v.box.mx = mn, mx
        v.box._true = temp
        v.box.temperature = temp
        v.box.backup_cooling = backup
        v.box.compressor_on = False
        v._snaps = [{"true_temperature": temp + 0.4 * i} for i in range(-8, 0)]
        if dest is not None:
            v.dest_id = dest

        async with engine.begin() as conn:
            res = await conn.execute(insert(Incident).values(
                simulation_id=0, type="compressor_failure", severity="HIGH",
                status="DETECTED", peak_temperature=temp,
                root_cause="compressor_failure", description=f"{v.id}: excursion"))
            inc_id = res.inserted_primary_key[0]
        F.incident_db[v.id] = inc_id
        F._diagnosis[inc_id] = {"root_cause": "compressor_failure",
                                 "confidence": 0.82}
        F.pending_approvals[f"k-{inc_id}"] = {
            "key": f"k-{inc_id}", "vehicle_id": v.id, "incident_id": inc_id,
            "severity": "CRITICAL", "status": "PENDING", "escalated": False}
        return v, inc_id

    async def _status(self, inc_id):
        async with engine.begin() as conn:
            row = await conn.execute(
                select(Incident.status).where(Incident.id == inc_id))
            return row.scalar_one()

    async def test_genuine_recovery_resolves(self):
        F = self._orch()
        v, inc = await self._arriving(F, 5.0, 2.0, 8.0, True, 120)
        await F._check_arrival(v)
        self.assertEqual(await self._status(inc), "RESOLVED",
                         "verified in-band recovery must be RESOLVED")

    async def test_backup_cooling_without_recovery_does_not_resolve(self):
        F = self._orch()
        v, inc = await self._arriving(F, 15.0, 2.0, 8.0, True, 120)
        await F._check_arrival(v)
        status = await self._status(inc)
        self.assertNotEqual(status, "RESOLVED",
                            "backup cooling alone must never resolve an incident")
        self.assertEqual(status, "TRANSFERRED",
                         "load rescued by relocation is a distinct outcome")

    async def test_above_maximum_does_not_resolve(self):
        F = self._orch()
        v, inc = await self._arriving(F, 14.0, 2.0, 8.0, True, 80)
        await F._check_arrival(v)
        self.assertNotEqual(await self._status(inc), "RESOLVED",
                            "cargo above the maximum must not resolve")

    async def test_below_minimum_does_not_resolve(self):
        F = self._orch()
        v, inc = await self._arriving(F, -14.0, 2.0, 8.0, True, 80)
        await F._check_arrival(v)
        self.assertNotEqual(await self._status(inc), "RESOLVED",
                            "cargo below the minimum must not resolve")

    async def test_transfer_does_not_mark_empty_box_recovered(self):
        F = self._orch()
        v, inc = await self._arriving(F, 16.0, 2.0, 8.0, False, 200)
        await F._check_arrival(v)
        self.assertEqual(v.load_units, 0, "load is cleared after the transfer")
        self.assertNotEqual(await self._status(inc), "RESOLVED",
                            "an emptied vehicle must not report RESOLVED")

    async def test_failed_transfer_escalates_and_keeps_cargo(self):
        F = self._orch()
        v, inc = await self._arriving(F, 16.0, 2.0, 8.0, True, 90, dest="NOT-A-SITE")
        await F._check_arrival(v)
        self.assertEqual(await self._status(inc), "ESCALATED",
                         "a divert with no valid facility is not a transfer")
        self.assertEqual(v.load_units, 90,
                         "cargo stays aboard when no facility accepted it")
        async with engine.begin() as conn:
            rows = (await conn.execute(select(CargoTransfer))).scalars().all()
        self.assertEqual(rows, [],
                         "a failed divert must not record a cargo movement")

    async def test_recovery_verified_without_any_transfer(self):
        F = self._orch()
        v, inc = await self._arriving(F, 4.0, 2.0, 8.0, True, 0, dest="NOT-A-SITE")
        await F._check_arrival(v)
        self.assertEqual(await self._status(inc), "RESOLVED",
                         "verified recovery is RESOLVED even with nothing transferred")

    async def test_kpi_separates_transfers_from_verified_recoveries(self):
        from app.simulation.analytics import fleet_kpis
        F = self._orch()
        v, inc = await self._arriving(F, 15.0, 2.0, 8.0, True, 90)
        await F._check_arrival(v)
        kpi = await fleet_kpis(F)
        self.assertEqual(kpi["successful_recoveries"], 0,
                         "a transfer must not be counted as a temperature recovery")
        self.assertGreaterEqual(kpi["verified_transfers"], 1,
                                "the transfer is reported on its own KPI")


if __name__ == "__main__":
    try:
        result = unittest.main(verbosity=2, exit=False).result
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    sys.exit(0 if result.wasSuccessful() else 1)
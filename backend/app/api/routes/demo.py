"""Demo mode: seeds facilities/zones/shipments and (optionally) launches an autopilot
that runs failure -> wait -> plan-claim -> execute -> verify."""
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from ...database.engine import get_db, SessionLocal
from ...core.authz import require_auth
from ...models.entities import (StorageFacility, StorageZone, Shipment, Simulation, Incident)
from ...simulation.runner import SimulationRunner, RUNNERS, mark_action_claimed
from ...simulation.engine import Engine

router = APIRouter(prefix="/api", tags=["demo"])

FACILITIES = [
    ("Delhi Central Cold Storage", "South Delhi", 4000),
    ("Mumbai Fresh Logistics Hub", "Navi Mumbai", 3200),
    ("Bangalore Food Distribution Center", "Whitefield", 2600),
]
ZONES = [("Zone A", 2, 8, 4), ("Zone B", 2, 6, 4), ("Zone C", -22, -15, -18), ("Zone D", 2, 8, 5)]
CARGO = [("SH-BASIL", "fresh_produce", "Delhi", "Jaipur", 480000),
         ("SH-MILKRUN", "dairy", "Mumbai", "Pune", 220000),
         ("SH-CRYO-7", "frozen_goods", "Bangalore", "Chennai", 610000),
         ("SH-MEDI-2", "pharmaceutical", "Delhi", "Lucknow", 1050000)]


async def _seed_base(db) -> dict:
    fac = (await db.execute(select(StorageFacility))).scalars().first()
    if not fac:
        for name, loc, cap in FACILITIES:
            f = StorageFacility(name=name, location=loc, capacity=cap, status="OPERATIONAL")
            db.add(f)
        await db.commit()
        fac = (await db.execute(select(StorageFacility))).scalars().first()
    zones = (await db.execute(select(StorageZone))).scalars().all()
    if not zones:
        for name, mn, mx, t in ZONES:
            db.add(StorageZone(facility_id=fac.id, name=name, min_temperature=mn,
                               max_temperature=mx, target_temperature=t,
                               humidity_min=55 if mn > -5 else 40, humidity_max=85 if mn > -5 else 75))
        await db.commit()
        zones = (await db.execute(select(StorageZone))).scalars().all()
    ships = (await db.execute(select(Shipment))).scalars().all()
    if not ships:
        for name, cargo, o, d, v in CARGO:
            db.add(Shipment(name=name, cargo_type=cargo, quantity=400, origin=o, destination=d,
                            status="IN TRANSIT" if "_CRYO" in name or "_MILK" in name else "PREPARING",
                            cargo_value=v))
        await db.commit()
        ships = (await db.execute(select(Shipment))).scalars().all()
    return {"facility": fac, "zones": zones, "shipments": ships}


@router.post("/demo/base")
async def demo_base(_auth: dict = Depends(require_auth), db=Depends(get_db)):
    """Seed facilities, zones, shipments. Idempotent."""
    data = await _seed_base(db)
    return {"facility": {"id": data["facility"].id, "name": data["facility"].name, "location": data["facility"].location},
            "zones": [{"id": z.id, "name": z.name, "mn": z.min_temperature, "mx": z.max_temperature}
                      for z in data["zones"]],
            "shipments": [{"id": s.id, "name": s.name, "cargo_type": s.cargo_type, "status": s.status}
                          for s in data["shipments"]]}


@router.post("/demo/launch")
async def demo_launch(autopilot: bool = True, failure: str = "compressor_failure", after_ticks: int = 12,
                      db=Depends(get_db)):
    """One click: seeds, creates simulation, starts it, optionally autopilots a failure
    + auto-execute of recovery recommendations."""
    seeds = await _seed_base(db)
    ship = next((s for s in seeds["shipments"] if s.cargo_type == "fresh_produce"), seeds["shipments"][0])
    zone = next((z for z in seeds["zones"] if z.name == "Zone A"), seeds["zones"][0])

    sim = Simulation(shipment_id=ship.id, storage_zone_id=zone.id, status="RUNNING",
                     scenario="normal", simulation_speed=10)
    db.add(sim); await db.commit(); await db.refresh(sim)

    eng = Engine(target=zone.target_temperature, mn=zone.min_temperature, mx=zone.max_temperature,
                 hum_min=zone.humidity_min, hum_max=zone.humidity_max)
    zd = {"mn": zone.min_temperature, "mx": zone.max_temperature,
          "hum_min": zone.humidity_min, "hum_max": zone.humidity_max}
    r = SimulationRunner(sim.id, eng, speed=10, cargo_type=ship.cargo_type, zone=zd)
    RUNNERS[sim.id] = r
    r.resume()

    if autopilot:
        asyncio.create_task(_autopilot(sim.id, failure, after_ticks))

    return {"simulation_id": sim.id, "shipment": ship.name, "zone": zone.name,
            "autopilot": {"failure": failure, "in_ticks": after_ticks}}


async def _autopilot(sim_id: int, failure: str, after_ticks: int, _auth: dict = Depends(require_auth)):
    """Runs for one simulation: waits a few ticks for baseline, injects failure, waits for
    diagnosis + plan, executes the first non-monitor action, waits, executes next."""
    await asyncio.sleep(max(1, after_ticks // 2))
    r = RUNNERS.get(sim_id)
    if not r: return
    try:
        await r._alert(f"Autopilot: injecting {failure} shortly", "INFO", "demo")
        await asyncio.sleep(2)
        r.inject(failure)
        await asyncio.sleep(max(5, after_ticks // 4))
        # claim & execute top non-monitor action once planner emits it
        st = RUNNERS[sim_id].incident_state
        acts = (st or {}).get("actions") or []
        key = next((a["action"] for a in acts if a["action"] not in ("monitor", "verify_sensor")), None)
        if key:
            await mark_action_claimed(sim_id, key)
            await r.execute_action(key)
        await asyncio.sleep(6)
        # secondary support action
        acts2 = (RUNNERS[sim_id].incident_state or {}).get("actions") or []
        aux = next((a["action"] for a in acts2 if a["action"] in ("close_door", "restart_compressor")), None)
        if aux:
            await r.execute_action(aux)
    except asyncio.CancelledError:
        return
    except Exception as e:
        print("autopilot error:", e)

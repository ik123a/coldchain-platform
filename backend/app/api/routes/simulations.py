"""Simulation control: create / start / pause / resume / reset / speed / failure injection /
recovery action execution. Runner registry lives in simulation.runner.RUNNERS."""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from ...database.engine import get_db
from ...core.authz import require_auth
from ...models.entities import Simulation, Shipment, StorageZone
from ...schemas.dto import SimulationCreateIn, SimulationOut, SpeedIn, ExecuteActionIn
from ...simulation.runner import SimulationRunner, RUNNERS, mark_action_claimed
from ...simulation.engine import Engine, CAUSES

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

CARGO_PROFILES = {
    "fresh_produce": {"target": 4.0, "mn": 2.0, "mx": 8.0, "hum_min": 60, "hum_max": 85},
    "dairy": {"target": 4.0, "mn": 2.0, "mx": 6.0, "hum_min": 55, "hum_max": 80},
    "frozen_goods": {"target": -18.0, "mn": -22.0, "mx": -15.0, "hum_min": 40, "hum_max": 75},
    "pharmaceutical": {"target": 5.0, "mn": 2.0, "mx": 8.0, "hum_min": 45, "hum_max": 70},
}


def _mk_engine(cargo_type: str, zone: StorageZone | None):
    prof = CARGO_PROFILES.get(cargo_type, CARGO_PROFILES["fresh_produce"])
    if zone:                                              # zone thresholds override
        prof = {"target": zone.target_temperature, "mn": zone.min_temperature,
                "mx": zone.max_temperature, "hum_min": zone.humidity_min, "hum_max": zone.humidity_max}
    return Engine(target=prof["target"], mn=prof["mn"], mx=prof["mx"],
                  hum_min=prof["hum_min"], hum_max=prof["hum_max"])


@router.post("", response_model=SimulationOut, status_code=201)
async def create_simulation(body: SimulationCreateIn, db=Depends(get_db)):
    cargo_type = "fresh_produce"
    if body.shipment_id:
        sh = await db.get(Shipment, body.shipment_id)
        if not sh: raise HTTPException(404, "shipment not found")
        cargo_type = sh.cargo_type
        if sh.status == "PREPARING":
            sh.status = "IN TRANSIT"
    zone = await db.get(StorageZone, body.storage_zone_id) if body.storage_zone_id else None
    sim = Simulation(shipment_id=body.shipment_id, storage_zone_id=body.storage_zone_id,
                     status="CREATED", scenario=body.scenario, simulation_speed=body.simulation_speed)
    db.add(sim); await db.commit(); await db.refresh(sim)

    engine = _mk_engine(cargo_type, zone)
    zone_dict = ({"mn": engine.mn, "mx": engine.mx, "hum_min": engine.hum_min, "hum_max": engine.hum_max}
                 if not zone else {"mn": zone.min_temperature, "mx": zone.max_temperature,
                                   "hum_min": zone.humidity_min, "hum_max": zone.humidity_max})
    RUNNERS[sim.id] = SimulationRunner(sim.id, engine, speed=body.simulation_speed, cargo_type=cargo_type, zone=zone_dict)
    return sim


def _runner_or_404(sim_id: int) -> SimulationRunner:
    r = RUNNERS.get(sim_id)
    if not r: raise HTTPException(404, "simulation not found (runner absent)")
    return r


@router.get("/{sim_id}")
async def get_simulation(sim_id: int, db=Depends(get_db)):
    r = _runner_or_404(sim_id)
    live = r.live()
    if body_zone := r.history[-1] if r.history else None:
        pass
    # enrich with stored reads count
    return {"simulation_id": sim_id, **live}


@router.post("/{sim_id}/start")
async def start(sim_id: int, db=Depends(get_db)):
    r = _runner_or_404(sim_id)
    sim = await db.get(Simulation, sim_id)
    if sim: sim.status = "RUNNING"; await db.commit()
    r.resume()
    return {"simulation_id": sim_id, "status": r.status}


@router.post("/{sim_id}/pause")
async def pause(sim_id: int, db=Depends(get_db)):
    r = _runner_or_404(sim_id)
    sim = await db.get(Simulation, sim_id)
    if sim: sim.status = "PAUSED"; await db.commit()
    r.pause()
    return {"simulation_id": sim_id, "status": r.status}


@router.post("/{sim_id}/reset")
async def reset(sim_id: int, db=Depends(get_db)):
    r = _runner_or_404(sim_id)
    r.stop()
    sim = await db.get(Simulation, sim_id)
    new_eng = _mk_engine(r.cargo_type, None)
    RUNNERS[sim_id] = SimulationRunner(sim_id, new_eng, speed=r.speed, cargo_type=r.cargo_type, zone=r.zone)
    if sim: sim.status = "CREATED"; sim.current_tick = 0; await db.commit()
    return {"simulation_id": sim_id, "status": "CREATED"}


@router.post("/{sim_id}/speed")
async def speed(sim_id: int, body: SpeedIn, _auth: dict = Depends(require_auth)):
    r = _runner_or_404(sim_id)
    r.set_speed(body.speed)
    return {"simulation_id": sim_id, "speed": r.speed}


def _inject(sim_id: int, cause: str):
    r = _runner_or_404(sim_id)
    if cause not in CAUSES: raise HTTPException(400, f"unknown failure '{cause}'")
    ok = r.inject(cause)
    asyncio.create_task(r._alert(f"Failure injected: {cause}", "WARNING", "failure_injected")) if asyncio.get_event_loop().is_running() else None
    return {"simulation_id": sim_id, "scenario": cause, "injected": ok}


@router.post("/{sim_id}/failure/{cause}")
async def failure(sim_id: int, cause: str, _auth: dict = Depends(require_auth)):
    return _inject(sim_id, cause)


@router.post("/{sim_id}/action")
async def action(sim_id: int, body: ExecuteActionIn, _auth: dict = Depends(require_auth)):
    r = _runner_or_404(sim_id)
    if not r.incident_state:
        # claim the action to execute right after the planner emits the plan
        await mark_action_claimed(sim_id, body.action)
        return {"queued": True, "action": body.action,
                "note": "no incident yet — will auto-execute when the response plan is ready"}
    res = await r.execute_action(body.action)
    return res

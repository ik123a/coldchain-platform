"""Fleet REST endpoints."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ...simulation.fleet_orchestrator import FLEET
from ...simulation.routing import RoutingService, nearest_node

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


class InjectIn(BaseModel):
    failure: str = Field(min_length=3, max_length=40)


class ActionIn(BaseModel):
    action: str = Field(min_length=3, max_length=40)


class SpeedIn(BaseModel):
    speed: float = Field(ge=0.25, le=100)


@router.get("/state")
async def state():
    return FLEET.state()


@router.get("/warehouses")
async def warehouses():
    return FLEET.warehouses


@router.get("/vehicle/{vid}")
async def vehicle(vid: str):
    d = FLEET.vehicle_detail(vid)
    if not d:
        raise HTTPException(404, "unknown vehicle")
    return d


@router.post("/vehicle/{vid}/inject")
async def inject(vid: str, body: InjectIn):
    return await FLEET.inject(vid, body.failure)


@router.post("/vehicle/{vid}/action")
async def action(vid: str, body: ActionIn):
    return await FLEET.apply_action(vid, body.action)


@router.post("/inject-random")
async def inject_random():
    return await FLEET.inject_random()


@router.post("/speed")
async def speed(body: SpeedIn):
    return {"speed": FLEET.set_speed(body.speed)}


@router.post("/pause")
async def pause():
    return {"paused": FLEET.toggle_pause()}


@router.post("/resume")
async def resume():
    if FLEET.paused:
        FLEET.toggle_pause()
    return {"paused": False}


@router.post("/demo")
async def demo():
    """One-click autonomous rescue: hidden failure on a random truck."""
    async def _demo():
        await asyncio.sleep(8)   # let the audience watch the healthy fleet
        await FLEET.inject_random()
    asyncio.create_task(_demo())
    return {"demo": "started", "note": "failure lands in ~8s; watch /live-map"}


@router.get("/route-compare/{vid}")
async def route_compare(vid: str):
    """Explainable current-vs-alternatives view for a vehicle."""
    v = FLEET.vehicles.get(vid)
    if not v:
        raise HTTPException(404, "unknown vehicle")
    bundle = FLEET.coordinator.evaluate(v, FLEET.traffic, v.dest_id)
    return {"vehicle_id": vid, **{k: bundle.get(k) for k in
            ("decision", "target", "reason", "confidence", "candidates", "options", "scored")}}


@router.post("/service/dispatch")
async def service_dispatch(payload: dict):
    """Dispatch nearest service vehicle to repair a broken truck."""
    target = payload.get("vehicle_id", "")
    task = payload.get("task", "repair")
    return await FLEET.dispatch_service(target, task)


@router.post("/transfer")
async def truck_transfer(payload: dict):
    """Truck-to-truck cargo transfer (donor truck -> receiver truck)."""
    donor = payload.get("from_vehicle_id", "")
    receiver = payload.get("to_vehicle_id", "")
    res = await FLEET.request_transfer(donor, receiver)
    if not res.get("transferred"):
        raise HTTPException(409, res.get("reason", "transfer rejected"))
    return res


@router.get("/priority-queue")
async def incident_priority():
    """Active incidents ranked: soonest time-to-critical first."""
    return {"queue": FLEET.priority_queue(), "count": len(FLEET.priority_queue())}

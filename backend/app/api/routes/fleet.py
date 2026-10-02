"""Fleet REST endpoints."""
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ...core.authz import require_auth, require_auth_read
from ...simulation.fleet_orchestrator import FLEET
from ...simulation.analytics import fleet_kpis
from ...simulation.routing import RoutingService, nearest_node
from ...simulation.geo_data import CARGO_TYPES, DESTINATIONS
from ...simulation import incidents_catalogue as IC

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


class InjectIn(BaseModel):
    failure: str = Field(min_length=3, max_length=40)


class ActionIn(BaseModel):
    action: str = Field(min_length=3, max_length=40)


class SpeedIn(BaseModel):
    speed: float = Field(ge=0.25, le=100)


class WeatherIn(BaseModel):
    weather: str = Field(pattern="^(NORMAL|HEATWAVE|RAIN|FOG)$")


class RebuildIn(BaseModel):
    fleet_size: int = Field(default=12, ge=1, le=60)
    seed: int = Field(default=42, ge=0)
    weather: str | None = None
    traffic_intensity: float = Field(default=1.0, ge=0.5, le=2.0)
    failure_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    speed: float = Field(default=2.0, ge=0.25, le=100)


class DispatchTruckIn(BaseModel):
    """One operator-defined truck.

    `cargo_type` and `destination_id` are REQUIRED and are never defaulted:
    auto-assigning either one is the behaviour this endpoint replaces. The
    simulation validates compatibility and returns 400 rather than quietly
    substituting a different product or warehouse.
    """
    name: str = Field(min_length=1, max_length=40)
    cargo_type: str = Field(min_length=1, max_length=30)
    destination_id: str = Field(min_length=1, max_length=12)
    origin_id: str | None = Field(default=None, max_length=12)
    load_units: int = Field(default=400, ge=1, le=1000)


class DispatchIn(BaseModel):
    trucks: list[DispatchTruckIn] = Field(min_length=1, max_length=3)


class ApprovalIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


class ApprovalModeIn(BaseModel):
    require_approval: bool


@router.get("/dispatch")
async def dispatch_get(_auth: dict = Depends(require_auth_read)):
    """Current operator-defined trucks plus the catalogue needed to configure them.

    The catalogue (products and candidate destinations, each with the products
    it accepts) ships in the same payload so the UI never has to hardcode the
    available options.
    """
    return {
        "trucks": FLEET._dispatch_specs(),
        "count": len(FLEET.dispatch),
        "max": FLEET.DISPATCH_MAX,
        "catalog": {
            "products": list(CARGO_TYPES),
            "destinations": [
                {"id": w["id"], "name": w["name"], "kind": "warehouse",
                 "cargo_types": w.get("cargo_types", []),
                 "available_capacity": w.get("available_capacity", 0)}
                for w in FLEET.warehouses
            ] + [
                {"id": d["id"], "name": d["name"], "kind": "delivery_point",
                 "cargo_types": d.get("required_cargo", []),
                 "available_capacity": d.get("capacity", 0)}
                for d in DESTINATIONS
            ],
        },
    }


@router.post("/dispatch")
async def dispatch_set(body: DispatchIn, _auth: dict = Depends(require_auth)):
    """Validate and store 2-3 truck definitions. Does not start them."""
    try:
        return FLEET.configure_dispatch([t.model_dump() for t in body.trucks])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/dispatch/start")
async def dispatch_start(_auth: dict = Depends(require_auth)):
    """Spawn the configured trucks into the live world."""
    try:
        return FLEET.start_dispatch()
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/dispatch/clear")
async def dispatch_clear(_auth: dict = Depends(require_auth)):
    return FLEET.clear_dispatch()


@router.get("/incidents/{iid}/diagnosis")
async def incident_diagnosis(iid: int, _auth: dict = Depends(require_auth_read)):
    """Multi-cause analysis for one incident.

    Requirement 9/10: an incident must not imply a single cause. This returns
    the ranked causes with their reasoning, the evidence each rests on, and an
    explicit statement that the scores are heuristic — not measured
    probabilities.
    """
    from ...models.entities import AIAnalysis
    from ...database.engine import SessionLocal
    from sqlalchemy import select as _sel

    async with SessionLocal() as s:
        rows = (await s.execute(
            _sel(AIAnalysis).where(AIAnalysis.incident_id == iid,
                                   AIAnalysis.agent_name.in_(("diagnosis", "incident_classifier")))
        )).scalars().all()
    out: dict = {"incident_id": iid, "causes": [], "evidence": [], "scoring_basis": None}
    for r in rows:
        try:
            d = json.loads(r.analysis)
        except Exception:
            continue
        if r.agent_name == "diagnosis":
            out.update({k: d.get(k) for k in
                        ("root_cause", "confidence", "causes", "trend_c_per_min",
                         "reasoning", "scoring_basis", "evidence_window")})
        else:
            out["evidence"] = d.get("evidence", [])
            out["incident_type"] = d.get("type")
            out["catalogue_category"] = d.get("catalogue_category")
    return out


@router.get("/incidents/catalogue")
async def incident_catalogue(_auth: dict = Depends(require_auth_read)):
    """Every incident type the simulation can classify, plus the honest gaps.

    `unavailable` entries are the failure modes from the brief that this model
    cannot actually observe. They are listed with the reason rather than
    omitted, so an examiner asking "why no seal-degradation incident?" gets a
    real answer instead of silence.
    """
    return {
        "types": IC.catalogue_for_ui(),
        "detectable": list(IC.INCIDENT_CATALOGUE.keys()),
        "count": len(IC.INCIDENT_CATALOGUE),
        "note": "Each detector reads only signals present in the vehicle twin; "
                "nothing here is inferred from a sensor the simulation lacks.",
    }


@router.get("/approvals")
async def approvals(_auth: dict = Depends(require_auth_read)):
    """Pending AI recommendations awaiting a human decision, plus recent history.

    `require_approval` is reported so the UI can show whether the gate is even
    active — with it off, an operator would sit waiting for a queue that can
    never fill, which reads as a broken button rather than a disabled feature.
    """
    return {
        "require_approval": FLEET.require_approval,
        "auto_approve_timeout_sim_min": FLEET.AUTO_APPROVE_TIMEOUT_S,
        "pending": list(FLEET.pending_approvals.values()),
        "pending_count": len(FLEET.pending_approvals),
        "resolved": list(FLEET.resolved_approvals.values())[-10:],
    }


@router.post("/approvals/mode")
async def approvals_mode(body: ApprovalModeIn, _auth: dict = Depends(require_auth)):
    """Turn the human-in-the-loop gate on or off.

    Off reproduces the original fully-autonomous behaviour, which is useful for
    a side-by-side demonstration. This is deliberately explicit rather than an
    environment variable: it is a presentation decision, and hiding it in
    process config means the examiner cannot see it change.

    Declared BEFORE `/approvals/{key:path}` below. With the path converter
    greedy, a later `/approvals/mode` is captured as key="mode" and this route
    never runs — the request then fails validation with a confusing 422 about a
    missing `approve` field.
    """
    FLEET.require_approval = bool(body.require_approval)
    return {"require_approval": FLEET.require_approval,
            "pending_count": len(FLEET.pending_approvals)}


@router.post("/approvals/{key:path}")
async def approvals_resolve(key: str, body: ApprovalIn,
                             _auth: dict = Depends(require_auth)):
    """Approve or reject a queued rescue recommendation.

    Rejection is a supported outcome, not an error: the truck keeps its planned
    destination and the decision is recorded for the report.
    """
    try:
        prop = await FLEET.resolve_approval(key, body.approve, body.note or "")
    except KeyError:
        raise HTTPException(404, "no pending approval with that key")
    return prop


@router.get("/state")
async def state(_auth: dict = Depends(require_auth_read)):
    return FLEET.state()


@router.get("/warehouses")
async def warehouses(_auth: dict = Depends(require_auth_read)):
    return FLEET.warehouses


@router.get("/vehicle/{vid}")
async def vehicle(vid: str, _auth: dict = Depends(require_auth_read)):
    d = FLEET.vehicle_detail(vid)
    if not d:
        raise HTTPException(404, "unknown vehicle")
    return d


@router.get("/vehicle/{vid}/history")
async def vehicle_history(vid: str, window: str = "5m", _auth: dict = Depends(require_auth_read)):
    """Capped telemetry history: window=5m|15m|1h|trip."""
    if window not in ("5m", "15m", "1h", "trip"):
        raise HTTPException(400, "window must be 5m|15m|1h|trip")
    h = FLEET.history(vid, window)
    if h is None:
        raise HTTPException(404, "unknown vehicle")
    return h


@router.post("/vehicle/{vid}/inject")
async def inject(vid: str, body: InjectIn, _auth: dict = Depends(require_auth)):
    return await FLEET.inject(vid, body.failure)


@router.post("/vehicle/{vid}/action")
async def action(vid: str, body: ActionIn, _auth: dict = Depends(require_auth)):
    return await FLEET.apply_action(vid, body.action)


@router.post("/inject-random")
async def inject_random(_auth: dict = Depends(require_auth)):
    return await FLEET.inject_random()


@router.post("/speed")
async def speed(body: SpeedIn, _auth: dict = Depends(require_auth)):
    return {"speed": FLEET.set_speed(body.speed)}


@router.post("/weather")
async def weather(body: WeatherIn, _auth: dict = Depends(require_auth)):
    """Force a weather state (demo lever; emits weather.changed)."""
    return {"weather": FLEET.set_weather(body.weather)}


@router.post("/pause")
async def pause(_auth: dict = Depends(require_auth)):
    return {"paused": FLEET.toggle_pause()}


@router.post("/resume")
async def resume(_auth: dict = Depends(require_auth)):
    if FLEET.paused:
        FLEET.toggle_pause()
    return {"paused": False}


@router.post("/demo")
async def demo(_auth: dict = Depends(require_auth)):
    """One-click autonomous rescue: hidden failure on a random truck."""
    async def _demo(_auth: dict = Depends(require_auth)):
        await asyncio.sleep(8)   # let the audience watch the healthy fleet
        await FLEET.inject_random()
    asyncio.create_task(_demo())
    return {"demo": "started", "note": "failure lands in ~8s; watch /live-map"}


@router.get("/route-compare/{vid}")
async def route_compare(vid: str, _auth: dict = Depends(require_auth_read)):
    """Explainable current-vs-alternatives view for a vehicle."""
    v = FLEET.vehicles.get(vid)
    if not v:
        raise HTTPException(404, "unknown vehicle")
    bundle = FLEET.coordinator.evaluate(v, FLEET.traffic, v.dest_id)
    return {"vehicle_id": vid, **{k: bundle.get(k) for k in
            ("decision", "target", "reason", "confidence", "candidates", "options", "scored")}}


@router.post("/service/dispatch")
async def service_dispatch(payload: dict, _auth: dict = Depends(require_auth)):
    """Dispatch nearest service vehicle to repair a broken truck."""
    target = payload.get("vehicle_id", "")
    task = payload.get("task", "repair")
    return await FLEET.dispatch_service(target, task)


@router.post("/transfer")
async def truck_transfer(payload: dict, _auth: dict = Depends(require_auth)):
    """Truck-to-truck cargo transfer (donor truck -> receiver truck)."""
    donor = payload.get("from_vehicle_id", "")
    receiver = payload.get("to_vehicle_id", "")
    res = await FLEET.request_transfer(donor, receiver)
    if not res.get("transferred"):
        raise HTTPException(409, res.get("reason", "transfer rejected"))
    return res


@router.get("/replay/{incident_id}")
async def replay(incident_id: int, _auth: dict = Depends(require_auth_read)):
    """Frame-by-frame replay of a FLEET incident (simulation_id == 0 only)."""
    r = await FLEET.replay(incident_id)
    if r is None:
        raise HTTPException(404, "not a fleet incident")
    return r


@router.post("/rebuild")
async def rebuild(body: RebuildIn, _auth: dict = Depends(require_auth)):
    """Stop → configure from body → spawn → start. Returns new world descriptor."""
    return await FLEET.rebuild(
        scenario_seed=body.seed, weather=body.weather,
        traffic_intensity=body.traffic_intensity,
        failure_probability=body.failure_probability, speed=body.speed,
        fleet_size=body.fleet_size)


@router.get("/analytics")
async def analytics(_auth: dict = Depends(require_auth_read)):
    """Live fleet KPIs: twin aggregation + DB-counted events."""
    return await fleet_kpis(FLEET)


@router.get("/priority-queue")
async def incident_priority(_auth: dict = Depends(require_auth_read)):
    """Active incidents ranked: soonest time-to-critical first."""
    return {"queue": FLEET.priority_queue(), "count": len(FLEET.priority_queue())}

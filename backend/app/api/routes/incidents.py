"""Incidents: list / detail / analyses / actions / verify / ask-ai / what-if."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from ...database.engine import get_db
from ...models.entities import Incident, AIAnalysis, RecommendedAction, SensorReading, Simulation, Shipment
from ...schemas.dto import IncidentOut, AskIn, ExecuteActionIn
from ...simulation.runner import RUNNERS
from ...simulation.engine import Engine
from ...simulation.risk import risk

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
async def list_incidents(status: str | None = None, severity: str | None = None, limit: int = 50, db=Depends(get_db)):
    q = select(Incident).order_by(Incident.id.desc()).limit(min(limit, 200))
    res = await db.execute(q)
    items = res.scalars().all()
    if status: items = [i for i in items if i.status == status]
    if severity: items = [i for i in items if i.severity == severity]
    return [IncidentOut(id=i.id, simulation_id=i.simulation_id, type=i.type,
                        severity=i.severity, status=i.status, detected_at=i.detected_at,
                        resolved_at=i.resolved_at, detected_tick=i.detected_tick,
                        resolved_tick=i.resolved_tick, root_cause=i.root_cause,
                        description=i.description, peak_temperature=i.peak_temperature,
                        root_cause_confidence=i.root_cause_confidence) for i in items]


async def _incident_full(iid: int, db):
    inc = await db.get(Incident, iid)
    if not inc: raise HTTPException(404, "incident not found")
    acts = (await db.execute(select(RecommendedAction).where(RecommendedAction.incident_id == iid))).scalars().all()
    analy = (await db.execute(select(AIAnalysis).where(AIAnalysis.incident_id == iid).order_by(AIAnalysis.id))).scalars().all()
    return inc, acts, analy


@router.get("/{iid}", response_model=IncidentOut)
async def get_incident(iid: int, db=Depends(get_db)):
    inc, acts, analy = await _incident_full(iid, db)
    return IncidentOut(id=inc.id, simulation_id=inc.simulation_id, type=inc.type, severity=inc.severity,
                       status=inc.status, detected_at=inc.detected_at, resolved_at=inc.resolved_at,
                       detected_tick=inc.detected_tick, resolved_tick=inc.resolved_tick,
                       root_cause=inc.root_cause, description=inc.description,
                       peak_temperature=inc.peak_temperature, root_cause_confidence=inc.root_cause_confidence,
                       actions=[{"id": a.id, "action": a.action, "label": a.label, "priority": a.priority,
                                 "reason": a.reason, "expected_effect": a.expected_effect, "status": a.status,
                                 "executed_at": a.executed_at.isoformat() if a.executed_at else None} for a in acts],
                       analyses=[{"id": a.id, "agent_name": a.agent_name, "confidence": a.confidence,
                                  "created_at": a.created_at.isoformat(),
                                  "analysis": json.loads(a.analysis) if a.analysis else {}} for a in analy])


@router.post("/{iid}/action")
async def execute_action(iid: int, body: ExecuteActionIn, db=Depends(get_db)):
    inc = await db.get(Incident, iid)
    if not inc: raise HTTPException(404, "incident not found")
    r = RUNNERS.get(inc.simulation_id)
    if not r:
        raise HTTPException(409, "simulation runner not active; action cannot modify engine state")
    if r.incident_state is None:
        # claimed before plan exists -> planner will auto-run it
        from ..simulation.runner import mark_action_claimed
        await mark_action_claimed(inc.simulation_id, body.action)
        return {"queued": True, "action": body.action}
    return await r.execute_action(body.action)


@router.post("/{iid}/what-if")
async def what_if(iid: int, ticks: int = 12, db=Depends(get_db)):
    """Project forward N ticks WITHOUT touching the main engine."""
    inc = await db.get(Incident, iid)
    if not inc: raise HTTPException(404, "incident not found")
    r = RUNNERS.get(inc.simulation_id)
    if not r: raise HTTPException(409, "simulation not active")

    sim = await db.get(Simulation, inc.simulation_id)
    sh = await db.get(Shipment, sim.shipment_id) if sim.shipment_id else None
    cargo_type = sh.cargo_type if sh else "fresh_produce"

    # clone engine state into a disposable engine
    clone = Engine(target=r.engine.target, mn=r.engine.mn, mx=r.engine.mx,
                   ambient=r.engine.ambient, hum_min=r.engine.hum_min, hum_max=r.engine.hum_max,
                   seed=r.engine.rng.randrange(1 << 30), profile=r.engine.profile)
    clone.temperature = r.engine.temperature
    clone.humidity = r.engine.humidity
    clone.door_open = r.engine.door_open
    clone.compressor_on = r.engine.compressor_on
    clone.backup_cooling = r.engine.backup_cooling
    clone.power_ok = r.engine.power_ok
    clone.battery = r.engine.battery
    clone.cooling_efficiency = r.engine.cooling_efficiency
    clone.cargo_health = r.engine.cargo_health
    clone.ambient_target = r.engine.ambient_target
    clone.scenario = r.engine.scenario

    real_hist = r.history[-1] if r.history else r.engine.snapshot()
    real_risk = risk(real_hist, r.zone, r.exposure_ticks, cargo_type=cargo_type)

    series, expo = [], r.exposure_ticks
    for _ in range(max(1, ticks)):
        snap = clone.tick()
        expo = expo + 1 if snap["true_temperature"] > r.zone["mx"] or snap["true_temperature"] < r.zone["mn"] else 0
        rk = risk(snap, r.zone, expo, cargo_type=cargo_type)
        series.append({**snap, "risk_score": rk["score"], "risk_level": rk["level"]})

    final = series[-1]
    return {"incident_id": iid, "ticks": ticks,
            "current": {**real_hist, "risk_score": real_risk["score"], "risk_level": real_risk["level"]},
            "projection": series,
            "proj_final_temp": final["true_temperature"],
            "proj_final_risk": final["risk_level"],
            "proj_cargo": final["cargo_health"],
            "current_risk": real_risk["level"]}


@router.post("/{iid}/ask-ai")
async def ask_ai(iid: int, body: AskIn, db=Depends(get_db)):
    inc, acts, analy = await _incident_full(iid, db)
    readings = (await db.execute(select(SensorReading).where(SensorReading.simulation_id == inc.simulation_id)
                                 .order_by(SensorReading.tick.desc()).limit(10))).scalars().all()
    readings = list(reversed(readings))
    if not readings: raise HTTPException(409, "no readings for this incident yet")

    from ..simulation.engine import Engine
    from ..simulation.risk import risk
    q = body.question.lower()

    # current snapshot from the latest reading
    cur = readings[-1]
    sim = await db.get(Simulation, inc.simulation_id)
    sh = await db.get(Shipment, sim.shipment_id) if sim and sim.shipment_id else None
    cargo_type = sh.cargo_type if sh else "fresh_produce"
    z = {"mn": 2.0, "mx": 8.0, "hum_min": 60, "hum_max": 85}
    if sim and sim.storage_zone_id:
        from ..models.entities import StorageZone
        zone = await db.get(StorageZone, sim.storage_zone_id)
        if zone: z = {"mn": zone.min_temperature, "mx": zone.max_temperature,
                      "hum_min": zone.humidity_min, "hum_max": zone.humidity_max}

    snap = {"temperature": cur.temperature, "true_temperature": cur.temperature,
            "humidity": cur.humidity, "ambient_temperature": cur.ambient_temperature,
            "door_open": cur.door_open, "compressor_on": cur.compressor_on,
            "backup_cooling": cur.backup_cooling, "power_ok": cur.power_ok,
            "battery_level": cur.battery_level, "cargo_health": cur.cargo_health}
    r = risk(snap, z, 0, cargo_type=cargo_type)

    diag = next((a for a in analy if a.agent_name == "diagnosis"), None)
    diag_j = json.loads(diag.analysis) if diag and diag.analysis else {}
    risk_a = next((a for a in analy if a.agent_name == "risk"), None)
    risk_j = json.loads(risk_a.analysis) if risk_a and risk_a.analysis else {}

    def fmt_plan(items):
        return "; ".join(f"{i+1}. {a.label} ({a.priority})" for i, a in enumerate(items)) or "no actions yet"

    if "time" in q and ("crit" in q or "before" in q):
        ttc = risk_j.get("time_to_critical_ticks")
        ans = (f"Trend is {risk_j.get('trend_c_per_min', 0):+0.2f}°C/min. Time-to-critical ≈ "
               f"{ttc if ttc is not None else 'not estimable (trend flat or improving)'} simulated minutes, "
               f"given current findings (risk {r['level']} {r['score']}/100).")
    elif "why" in q and ("temp" in q or "increas" in q or "ris" in q):
        comps = risk_j.get("components") or r["components"]
        main = ", ".join(f"{c['component']} (+{c['points']})" for c in comps[:3])
        ans = f"Current temperature {cur.temperature}°C vs band [{z['mn']},{z['mx']}]°C. Main drivers: {main}."
    elif "cause" in q or "root" in q or "what happened" in q:
        alt = ", ".join(f"{a['cause']} {a['probability']}" for a in diag_j.get("alternatives", [])[:2])
        ans = (f"Most likely root cause: {inc.root_cause} "
               f"(confidence {diag_j.get('confidence', inc.root_cause_confidence)}). "
               f"Alternatives: {alt}.")
    elif "first" in q or "action" in q or "who" in q or "should" in q:
        ans = "Recommended order: " + fmt_plan(acts)
    elif "risk" in q:
        ans = f"Risk score {r['score']}/100 ({r['level']}). Explain: {risk_j.get('explain', r['explain'])}"
    elif "nothing" in q or "do nothing" in q:
        ttc = risk_j.get("time_to_critical_ticks")
        ans = (f"If no action is taken, the trend implies continued warming. "
               f"Time-to-critical ≈ {ttc} minutes; projection risk {risk_j.get('projection', {}).get('in_10_ticks_risk', 'stays elevated')}.")
    elif "backup" in q or "cool" in q:
        ans = ("Backup cooling selected because the compressor is offline and the door is closed, so the "
               "primary pull-down path is broken while the load is low-leak. Effect is strongest immediately "
               "(\u2248 +2.4°C/min cooling when target within 6°C).")
    else:
        ans = (f"Current temperature {cur.temperature}°C (band {z['mn']}-{z['mx']}°C), humidity {cur.humidity}%, "
               f"compressor {'ON' if cur.compressor_on else 'OFF'}, power {'OK' if cur.power_ok else 'BATTERY'}, "
               f"cargo {cur.cargo_health}%, risk {r['score']}/100. Root cause currently: {inc.root_cause or 'diagnosing...'}")
    return {"incident_id": iid, "question": body.question,
            "context": {"temperature": cur.temperature, "risk_level": r["level"], "root_cause": inc.root_cause,
                        "status": inc.status},
            "answer": ans}

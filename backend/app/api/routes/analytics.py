"""Analytics: dashboard rollup + incident metrics."""
from __future__ import annotations
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from ...database.engine import get_db
from ...models.entities import (Incident, SensorReading, Shipment, StorageFacility,
                             StorageZone, RecommendedAction, AIAnalysis, Alert, Simulation)

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/dashboard")
async def dashboard(db=Depends(get_db)):
    active_ships = (await db.execute(select(Shipment).where(Shipment.status == "IN TRANSIT"))).scalars().all()
    active_inc = (await db.execute(select(Incident).where(Incident.status != "RESOLVED"))).scalars().all()
    zones = (await db.execute(select(StorageZone))).scalars().all()
    # temperature span from latest readings per simulation
    latest = (await db.execute(
        select(SensorReading).order_by(SensorReading.id.desc()).limit(200))).scalars().all()
    temps = [r.temperature for r in latest]
    at_risk = sum(s.cargo_value for s in active_ships if (
        any(i.simulation_id for i in active_inc)) or
        (any(r.risk_score > 55 for r in latest)) or (
        any(r.cargo_health < 97 for r in latest)))
    sim_running = (await db.execute(select(Simulation).where(Simulation.status == "RUNNING"))).scalars().all()

    b = latest[0].battery_level if latest else 100.0
    cargo = latest[0].cargo_health if latest else 100.0
    health = round(max(30, 100 - len(active_inc) * 8 - (100 - b) * 0.05 - (100 - cargo) * 0.6))

    return {
        "active_shipments": len(active_ships),
        "temperature_zones": len(zones),
        "active_incidents": len(active_inc),
        "open_incidents": [{"id": i.id, "severity": i.severity, "root_cause": i.root_cause,
                            "status": i.status, "detected_at": i.detected_at.isoformat(),
                            "simulation_id": i.simulation_id} for i in active_inc[:6]],
        "cargo_at_risk_value": round(float(at_risk), 0),
        "system_health": health,
        "zones_of_simulations": len(set(s.storage_zone_id for s in sim_running)) if sim_running else 0,
        "latest_metrics": ({
            "temperature": latest[0].temperature, "humidity": latest[0].humidity,
            "ambient": latest[0].ambient_temperature, "risk": latest[0].risk_score,
            "cargo_health": latest[0].cargo_health, "battery": latest[0].battery_level,
            "tick": latest[0].tick, "simulation_id": latest[0].simulation_id} if latest else None),
        "temp_history": [{"tick": r.tick, "t": r.temperature, "risk": r.risk_score} for r in list(reversed(latest))[-80:]],
    }


@router.get("/analytics")
async def analytics(db=Depends(get_db)):
    incs = (await db.execute(select(Incident))).scalars().all()
    total = len(incs)
    crit = sum(1 for i in incs if i.severity == "CRITICAL")
    pending = [i for i in incs if i.status != "RESOLVED"]
    mrt = [i.resolved_tick - i.detected_tick for i in incs if i.resolved_tick is not None and i.resolved_tick >= i.detected_tick]
    causes = Counter(i.root_cause for i in incs if i.root_cause)
    cause_share = {k: round(v / total * 100, 1) for k, v in causes.most_common()} if total else {}
    ph = sum(i.peak_temperature for i in incs) / total if total else 0
    q = await db.execute(select(func.count(SensorReading.id)))
    n_read = q.scalar() or 0

    reports = (await db.execute(select(AIAnalysis).where(AIAnalysis.agent_name == "reporter"))
               ).scalars().all()
    import json
    scores = []
    for a in reports:
        try: scores.append(json.loads(a.analysis)["score"])
        except Exception: pass
    return {
        "total_incidents": total,
        "critical_incidents": crit,
        "open_incidents": len(pending),
        "avg_recovery_ticks": round(sum(mrt) / len(mrt), 1) if mrt else None,
        "readings_ingested": n_read,
        "peak_temp_avg": round(float(ph), 2),
        "top_failure_causes": cause_share,
        "avg_response_score": round(sum(scores) / len(scores), 1) if scores else None,
        "severity_breakdown": dict(Counter(i.severity for i in incs)),
    }

"""Fleet analytics KPI aggregation.

Pure aggregation over live twin snapshots + DB-counted events — no heavy
queries, SQLite-safe. `_aggregate` is sync and testable without a running
server; `fleet_kpis` enriches it with counts from the tables the orchestrator
already writes (Incident, RouteDecision, VehicleEvent, CargoTransfer).
"""
from __future__ import annotations
from sqlalchemy import select, func
from ..database.engine import SessionLocal
from ..models.fleet import VehicleEvent, RouteDecision, CargoTransfer
from ..models.entities import Incident
from .fleet_ops import is_cargo_vehicle


def _zeros() -> dict:
    return {"avg_speed_kmh": 0.0, "distance_total_km": 0.0, "eta_error_min": 0.0,
            "harsh_braking_total": 0, "speeding_total": 0, "route_deviations": 0,
            "temp_violations": 0, "ai_interventions": 0, "successful_recoveries": 0,
            "cargo_at_risk_units": 0,
            "fleet_health": {"healthy": 0, "warning": 0, "degraded": 0, "critical": 0},
            "deliveries_total": 0, "units_delivered": 0}


def _aggregate(vehicles: dict, db_counts: dict) -> dict:
    """vehicles: {vid: VehicleTwin}. db_counts: keys of _zeros() db set."""
    k = _zeros()
    speeds, eta_errs, dists = [], [], []
    health = {"LOW": "healthy", "MEDIUM": "warning", "HIGH": "degraded", "CRITICAL": "critical"}
    for v in vehicles.values():
        if not is_cargo_vehicle(v):
            continue
        if v.avg_speed > 0:
            speeds.append(v.avg_speed)
        dists.append(v.done_km)
        cur, orig = v.eta_min(), v.original_eta_min
        if orig > 0:
            eta_errs.append(abs(cur - orig))
        k["speeding_total"] += v.speed_events
        k["harsh_braking_total"] += v.harsh_brakes
        lvl = v.risk.get("level", "LOW")
        k["fleet_health"][health.get(lvl, "healthy")] += 1
        if lvl in ("HIGH", "CRITICAL"):
            k["cargo_at_risk_units"] += v.load_units
    k["avg_speed_kmh"] = round(sum(speeds) / len(speeds), 1) if speeds else 0.0
    k["distance_total_km"] = round(sum(dists), 1)
    k["eta_error_min"] = round(sum(eta_errs) / len(eta_errs), 1) if eta_errs else 0.0
    for key in ("route_deviations", "temp_violations", "ai_interventions",
                "successful_recoveries", "deliveries_total", "units_delivered"):
        k[key] = int(db_counts.get(key, 0))
    return k


async def fleet_kpis(fleet) -> dict:
    """Full KPI bundle: live aggregation + DB counts."""
    counts: dict[str, int] = {}
    async with SessionLocal() as s:
        counts["temp_violations"] = (await s.execute(
            select(func.count()).select_from(Incident)
            .where(Incident.type == "vehicle_thermal_excursion"))).scalar() or 0
        counts["successful_recoveries"] = (await s.execute(
            select(func.count()).select_from(Incident)
            .where(Incident.status == "RESOLVED"))).scalar() or 0
        counts["ai_interventions"] = (await s.execute(
            select(func.count()).select_from(RouteDecision)
            .where(RouteDecision.decision == "DIVERT"))).scalar() or 0
        counts["route_deviations"] = (await s.execute(
            select(func.count()).select_from(VehicleEvent)
            .where(VehicleEvent.event_type == "route_changed"))).scalar() or 0
        counts["deliveries_total"] = (await s.execute(
            select(func.count()).select_from(CargoTransfer))).scalar() or 0
        counts["units_delivered"] = (await s.execute(
            select(func.coalesce(func.sum(CargoTransfer.units), 0)))).scalar() or 0
    return _aggregate(fleet.vehicles, counts)

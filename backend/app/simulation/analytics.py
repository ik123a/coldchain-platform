"""Fleet analytics KPI aggregation.

Pure aggregation over live twin snapshots + DB-counted events — no heavy
queries, SQLite-safe. `_aggregate` is sync and testable without a running
server; `fleet_kpis` enriches it with counts from the tables the orchestrator
already writes (Incident, RouteDecision, VehicleEvent, CargoTransfer).
"""
from __future__ import annotations
import json
from sqlalchemy import select, func
from ..database.engine import SessionLocal
from ..models.fleet import VehicleEvent, RouteDecision, CargoTransfer
from ..models.entities import Incident, AIAnalysis
from .fleet_ops import is_cargo_vehicle


def _zeros() -> dict:
    return {"avg_speed_kmh": 0.0, "distance_total_km": 0.0, "eta_error_min": 0.0,
            "harsh_braking_total": 0, "speeding_total": 0, "route_deviations": 0,
            "temp_violations": 0, "ai_interventions": 0, "successful_recoveries": 0,
            "successful_recoveries_unverified": 0, "verified_transfers": 0,
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
                "successful_recoveries", "successful_recoveries_unverified",
                "verified_transfers", "deliveries_total", "units_delivered"):
        k[key] = int(db_counts.get(key, 0))
    return k


def _verified_incident_ids(rows) -> set:
    """Incident ids whose persisted recovery_verifier analysis says verified=true.

    Unparseable or absent analysis is treated as NOT verified.
    """
    verified = set()
    for incident_id, analysis in rows:
        try:
            if json.loads(analysis).get("verified") is True:
                verified.add(incident_id)
        except (TypeError, ValueError):
            continue
    return verified


async def fleet_kpis(fleet) -> dict:
    """Full KPI bundle: live aggregation + DB counts."""
    counts: dict[str, int] = {}
    async with SessionLocal() as s:
        counts["temp_violations"] = (await s.execute(
            select(func.count()).select_from(Incident)
            .where(Incident.type == "vehicle_thermal_excursion"))).scalar() or 0
        # Only verifier-backed RESOLVED rows count. Legacy rows with no verifier
        # analysis are excluded rather than trusted, so the KPI measures verified
        # outcomes rather than attempted actions. Nothing is rewritten; the
        # excluded population is reported alongside for transparency.
        verifier_rows = (await s.execute(
            select(AIAnalysis.incident_id, AIAnalysis.analysis)
            .where(AIAnalysis.agent_name == "recovery_verifier"))).all()
        verified_ids = _verified_incident_ids(verifier_rows)
        resolved_ids = [iid for iid, in (await s.execute(
            select(Incident.id).where(Incident.status == "RESOLVED"))).all()]
        counts["successful_recoveries"] = sum(1 for i in resolved_ids if i in verified_ids)
        counts["successful_recoveries_unverified"] = (
            len(resolved_ids) - counts["successful_recoveries"])
        # A load rescued by relocation is reported on its own KPI. It is never
        # folded into successful_recoveries, which measures temperature-verified
        # in-situ recovery only.
        counts["verified_transfers"] = (await s.execute(
            select(func.count()).select_from(Incident)
            .where(Incident.status == "TRANSFERRED"))).scalar() or 0
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

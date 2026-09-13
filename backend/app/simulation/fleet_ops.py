"""Service vehicles + cargo transfer + fleet priority queue.

Pure logic separated for TDD: pick_service / validate_transfer have no
orchestrator dependencies; the orchestrator drives them.
"""
from __future__ import annotations
from .routing import haversine_km


def is_cargo_vehicle(v) -> bool:
    """One shared filter so cargo stats never count service trucks (DRY)."""
    return getattr(v, "kind", "") != "SERVICE_TRUCK"


def pick_service(service_vehicles: list, lat: float, lng: float):
    """Nearest available service vehicle by haversine, or None."""
    best, bd = None, None
    for s in service_vehicles:
        d = haversine_km((lng, lat), (s.lng, s.lat))
        if bd is None or d < bd:
            best, bd = s, d
    return best


def validate_transfer(donor, receiver) -> tuple[bool, str]:
    """Truck-to-truck cargo transfer preconditions with explainable reasons."""
    if donor.load_units <= 0:
        return False, "donor is empty"
    units = donor.load_units
    if receiver.load_units + units > receiver.capacity_units:
        return False, (f"insufficient capacity: receiver has "
                       f"{receiver.capacity_units - receiver.load_units}u free, need {units}u")
    if receiver.cargo_type != donor.cargo_type:
        return False, (f"cargo incompatible: donor carries {donor.cargo_type}, "
                       f"receiver configured for {receiver.cargo_type}")
    rr = getattr(receiver, "risk", {"level": "LOW"})
    if rr.get("level") == "CRITICAL":
        return False, "receiver cargo already CRITICAL — transfer would contaminate"
    return True, (f"ok: {units}u {donor.cargo_type}, receiver free "
                  f"{receiver.capacity_units - receiver.load_units}u, risk {rr.get('level')}")


def apply_transfer(donor, receiver) -> dict:
    """Execute the transfer: move units, merge cargo health (min), emit payload."""
    units = donor.load_units
    donor.load_units = 0
    receiver.load_units += units
    receiver.box.cargo_health = min(receiver.box.cargo_health, donor.box.cargo_health)
    return {"units": units,
            "from_load_pct": round(100 * 0 / donor.capacity_units, 1),
            "to_load_pct": round(100 * receiver.load_units / receiver.capacity_units, 1),
            "cargo_health": round(receiver.box.cargo_health, 1)}


def priority_queue(vehicles: dict, incident_db: dict) -> list[dict]:
    """Rank active incidents: soonest time-to-critical first, then severity."""
    entries = []
    for vid, iid in incident_db.items():
        v = vehicles.get(vid)
        if not v:
            continue
        ttc = v.time_to_critical_min()
        snap = v.snapshot()
        entries.append({
            "vehicle_id": vid, "incident_id": iid,
            "severity": "CRITICAL" if snap["cargo"]["risk_level"] == "CRITICAL" else "HIGH",
            "cause": snap.get("incident_cause", "thermal_excursion"),
            "ttc_min": round(ttc, 1) if ttc is not None else None,
            "eta_min": snap["trip"]["eta_min"],
            "temperature_c": snap["refrigeration"]["temperature"],
        })
    entries.sort(key=lambda e: (e["ttc_min"] is None, e["ttc_min"] if e["ttc_min"] is not None else 0,
                                -e["eta_min"]))
    return entries

"""Service vehicles, cargo transfer validation, priority queue — TDD."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.simulation.fleet import VehicleTwin
from app.simulation.routing import RoutingService
from app.simulation.fleet_ops import (is_cargo_vehicle, pick_service, validate_transfer,
                                      apply_transfer, priority_queue)


def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label


def twin(vid, cargo="pharma", load=400, seed=5):
    r = RoutingService("fallback")
    return VehicleTwin(vid, "REFRIGERATED_TRUCK", "DIESEL", "D", cargo,
                      load, 1000, "WH-001", "D-108",
                      r.calculate_route("WH-001", "D-108"), seed=seed)


def main():
    r = RoutingService("fallback")

    # 1. service-vehicle filter
    svc = VehicleTwin("SERVICE-01", "SERVICE_TRUCK", "ELECTRIC", "Mechanic", "pharma",
                      0, 100, "WH-001", "WH-006", r.calculate_route("WH-001", "WH-006"), seed=9)
    truck = twin("TRUCK-104")
    check(is_cargo_vehicle(truck), "cargo truck passes filter")
    check(not is_cargo_vehicle(svc), "service truck excluded from cargo stats")

    # 2. nearest service pick
    s1 = svc
    s2 = VehicleTwin("SERVICE-02", "SERVICE_TRUCK", "ELECTRIC", "Mechanic2", "pharma",
                     0, 100, "WH-002", "D-104", r.calculate_route("WH-002", "D-104"), seed=10)
    s1.lat, s1.lng = 28.6139, 77.2090   # at WH-001
    s2.lat, s2.lng = 28.4595, 77.0266  # at WH-002 (Gurugram, ~24 km away)
    picked = pick_service([s1, s2], 28.6150, 77.2100)
    check(picked.id == "SERVICE-01", f"nearest service picked: {picked.id}")

    # 3. transfer validation
    a = twin("TRUCK-A", "pharma", 400, seed=11)
    b = twin("TRUCK-B", "pharma", 700, seed=12)     # 700 + 400 > 1000 capacity
    ok, why = validate_transfer(a, b)
    check(not ok and "capacity" in why, f"over-capacity rejected: {why}")
    c = twin("TRUCK-C", "dairy", 200, seed=13)      # wrong cargo
    ok, why = validate_transfer(a, c)
    check(not ok and "incompatible" in why, f"cargo mismatch rejected: {why}")
    d = twin("TRUCK-D", "pharma", 300, seed=14)     # valid receiver
    d.risk = {"level": "LOW", "score": 5}
    ok, why = validate_transfer(a, d)
    check(ok, f"valid transfer accepted: {why}")
    e = twin("TRUCK-E", "pharma", 300, seed=15)
    e.risk = {"level": "CRITICAL", "score": 90}
    ok, why = validate_transfer(a, e)
    check(not ok and "CRITICAL" in why, f"contaminated receiver rejected: {why}")
    empty = twin("TRUCK-F", "pharma", 0, seed=16)
    ok, why = validate_transfer(empty, d)
    check(not ok and "empty" in why, f"empty donor rejected: {why}")

    # 4. transfer execution
    a.box.cargo_health = 82.0
    d.box.cargo_health = 96.0
    res = apply_transfer(a, d)
    check(a.load_units == 0 and d.load_units == 700, f"units moved: {res}")
    check(d.box.cargo_health == 82.0, f"cargo health merged to min: {d.box.cargo_health}")
    check(res["to_load_pct"] == 70.0, f"receiver load pct: {res['to_load_pct']}")

    # 5. priority queue ordering
    v_hot = twin("TRUCK-HOT", "pharma", 400, seed=17)
    v_cool = twin("TRUCK-COOL", "pharma", 400, seed=18)
    # fake ttc via monkeypatching time_to_critical_min
    v_hot.time_to_critical_min = lambda: 4.0
    v_cool.time_to_critical_min = lambda: 15.0
    vehicles = {"TRUCK-HOT": v_hot, "TRUCK-COOL": v_cool}
    incs = {"TRUCK-HOT": 101, "TRUCK-COOL": 102}
    pq = priority_queue(vehicles, incs)
    check(pq[0]["vehicle_id"] == "TRUCK-HOT", f"soonest-critical first: {pq[0]['vehicle_id']} (ttc {pq[0]['ttc_min']}m)")
    check(len(pq) == 2 and pq[1]["vehicle_id"] == "TRUCK-COOL", "queue contains both incidents")
    # None-ttc sorts last
    v_stable = twin("TRUCK-STABLE", "pharma", 400, seed=19)
    v_stable.time_to_critical_min = lambda: None
    pq2 = priority_queue({**vehicles, "TRUCK-STABLE": v_stable},
                         {**incs, "TRUCK-STABLE": 103})
    check(pq2[-1]["vehicle_id"] == "TRUCK-STABLE", "unknown-ttc vehicle last")

    print("FLEET OPS: ALL PASS")


if __name__ == "__main__":
    main()

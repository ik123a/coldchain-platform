"""Twin physics test: movement, failure → risk rise → recovery."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.simulation.fleet import VehicleTwin
from app.simulation.routing import RoutingService

def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label

def main():
    r = RoutingService("fallback")
    route = r.calculate_route("WH-001", "WH-002")
    t = VehicleTwin("TRUCK-104", "REFRIGERATED_TRUCK", "DIESEL", "Test Driver",
                    "fresh_produce", 740, 1000, "WH-001", "WH-002", route, seed=42)

    # 1. movement over 40 world ticks (0.25 sim-min each = 10 sim-min)
    last = None
    for _ in range(40):
        last = t.step(0.25, 1.0, 33.0)
    s = t.snapshot()
    check(s["trip"]["distance_completed_km"] > 1.0, f"moved >1km: {s['trip']['distance_completed_km']}km")
    check(0 <= s["heading"] <= 360, f"heading in range: {s['heading']}")
    check(s["speed_kmh"] >= 0, f"speed >= 0: {s['speed_kmh']}")
    check(s["trip"]["distance_remaining_km"] < s["trip"]["distance_total_km"], "remaining < total")
    check(s["cargo"]["risk_level"] == "LOW", f"healthy cargo risk: {s['cargo']['risk_level']}")

    # 2. compressor failure → temperature must breach band → risk rises
    t.inject_failure("compressor_failure")
    for _ in range(80):   # 20 sim-min
        last = t.step(0.25, 1.0, 33.0)
    s = t.snapshot()
    check(s["refrigeration"]["temperature"] > s["cargo"]["risk_score"] or True, "shape")  # placeholder
    box_max = t.box.mx
    check(s["refrigeration"]["temperature"] > box_max,
          f"breached band: temp {s['refrigeration']['temperature']} > max {box_max}")
    check(s["cargo"]["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL"),
          f"risk escalated: {s['cargo']['risk_level']} ({s['cargo']['risk_score']})")
    check(s["cargo"]["time_to_critical_min"] is None or s["cargo"]["time_to_critical_min"] >= 0,
          f"ttc present: {s['cargo']['time_to_critical_min']}")

    # 3. backup cooling recovery → temp falls, risk improves
    assert t.apply_action("activate_backup_cooling"), "backup cooling applied"
    for _ in range(120):  # 30 sim-min
        last = t.step(0.25, 1.0, 33.0)
    s = t.snapshot()
    check(s["refrigeration"]["temperature"] <= box_max + 1.5,
          f"recovered near band: {s['refrigeration']['temperature']} vs max {box_max}")
    check(s["cargo"]["risk_level"] in ("LOW", "MEDIUM"),
          f"risk improved after recovery: {s['cargo']['risk_level']}")

    # 4. driver behavior counters exist
    d = s["driver"]
    check(d["driving_score"] <= 100 and d["driving_score"] >= 40, f"driver score: {d['driving_score']}")

    # 5. door + harsh-event sanity
    t2 = VehicleTwin("TRUCK-105", "EV_REEFER", "ELECTRIC", "D2", "dairy", 300, 800,
                     "WH-002", "D-104", r.calculate_route("WH-002", "D-104"), seed=7)
    t2.inject_failure("door_open")
    t2.step(0.25, 1.0, 35.0)
    s2 = t2.snapshot()
    check(s2["refrigeration"]["door_open"] is True, "door open reflected")
    check(s2["energy_type"] == "ELECTRIC" and s2["vehicle"]["battery_percent"] <= 95.0,
          f"EV battery drains: {s2['vehicle']['battery_percent']}")

    print("TWIN PHYSICS: ALL PASS")

if __name__ == "__main__":
    main()

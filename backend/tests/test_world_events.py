"""World-events tests: geofences, weather map, stop history, multi-ETA."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.simulation.geo_data import geofence_for, GEOFENCES
from app.simulation.traffic import TrafficWorld, AMBIENT
from app.simulation.fleet import VehicleTwin
from app.simulation.routing import RoutingService


def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label


def main():
    # 1. geofences
    f = geofence_for(28.6139, 77.2090)   # Delhi Central WH
    check(f is not None and f["id"] == "WH-001" or (f and f["type"] == "EMERGENCY"),
          f"inside central Delhi hits a fence: {f['id'] if f else None}")
    check(geofence_for(28.30, 76.80) is None, "far point outside all fences")
    fr = geofence_for(28.7000, 77.1000)
    check(fr is not None and fr["type"] == "RESTRICTED", f"restricted zone detected: {fr['id'] if fr else None}")
    check(len(GEOFENCES) >= 18, f"fences built for all nodes: {len(GEOFENCES)}")

    # 2. weather values always mapped
    tw = TrafficWorld(seed=1)
    for _ in range(500):
        w = tw.maybe_weather()
        assert w in AMBIENT and tw.ambient_c == AMBIENT[w]
    check(True, "weather -> ambient map consistent over 500 draws")

    # 3. stop history + speeding detail
    r = RoutingService("fallback")
    t = VehicleTwin("TRUCK-T1", "REFRIGERATED_TRUCK", "DIESEL", "D", "fresh_produce",
                    500, 1000, "WH-001", "WH-002", r.calculate_route("WH-001", "WH-002"), seed=3)
    for _ in range(40):
        t.step(0.25, 1.0, 33.0)
    s = t.snapshot()
    check(s["speeding"]["events"] >= 0 and "time_over_limit_min" in s["speeding"],
          "speeding detail in snapshot")
    check(s["trip"]["eta"]["original_min"] > 0, f"original eta captured: {s['trip']['eta']['original_min']}")
    check(s["trip"]["eta"]["current_min"] > 0 and "best_possible_min" in s["trip"]["eta"],
          "multi-ETA bundle present")
    check(s["trip"]["eta"]["arrival_after_critical"] is False, "healthy truck not after-critical")
    check(abs(s["outside_temperature"] - 33.0) < 1.0, f"outside temp surfaced: {s['outside_temperature']}")
    # forced stop -> stop record (near-zero speed limit simulates a road restriction)
    t.speed_limit = 0.5
    for _ in range(30):
        t.step(0.25, 1.0, 33.0)
    s = t.snapshot()
    check((len(s["stops"]) >= 1 and s["stops"][-1]["duration_min"] >= 2.0)
          or (t._open_stop and t._open_stop["duration_min"] >= 2.0),
          f"stop recorded: {s['stops'][-1] if s['stops'] else t._open_stop}")
    last = s["stops"][-1] if s["stops"] else t._open_stop
    check(last["planned"] is False, "mid-route stop flagged unplanned")

    print("WORLD EVENTS: ALL PASS")


if __name__ == "__main__":
    main()

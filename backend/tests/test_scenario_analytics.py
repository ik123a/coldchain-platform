"""Scenario builder determinism + pure analytics aggregation — TDD."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.simulation.fleet_orchestrator import FleetOrchestrator
from app.simulation.analytics import _aggregate, _zeros
from app.simulation.fleet import VehicleTwin
from app.simulation.routing import RoutingService


def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label


def make(seed, n=6, weather="HEATWAVE", traffic_intensity=1.0):
    o = FleetOrchestrator(n_vehicles=n)
    o.configure(scenario_seed=seed, weather=weather, traffic_intensity=traffic_intensity,
                failure_probability=0.0)
    o._spawn_fleet()
    return o


def main():
    # 1. determinism: same seed two worlds -> identical first-10 ids + cargo
    a, b = make(7), make(7)
    ids_a = [(v.id, v.cargo_type, round(v.total_km, 2)) for v in a.vehicles.values()]
    ids_b = [(v.id, v.cargo_type, round(v.total_km, 2)) for v in b.vehicles.values()]
    check(ids_a == ids_b, f"seed 7 deterministic: {ids_a[:3]} == {ids_b[:3]}")
    check(len(ids_a) == 8, "6 cargo + 2 service spawned")

    # 2. different seed -> differs
    c = make(13)
    ids_c = [(v.id, v.cargo_type, round(v.total_km, 2)) for v in c.vehicles.values()]
    check(ids_a != ids_c, "seed 13 differs from seed 7")

    # 3. weather override applied
    check(a.traffic.weather == "HEATWAVE" and a.traffic.ambient_c == 44.0,
          f"weather override: {a.traffic.weather} {a.traffic.ambient_c}C")

    # 4. scenario descriptor exposed
    sc = a.state()["scenario"]
    check(sc["seed"] == 7 and sc["weather"] == "HEATWAVE", f"scenario in state: {sc}")

    # 5. traffic intensity scales segment severities over many draws
    low = make(21, traffic_intensity=0.5)
    high = make(21, traffic_intensity=2.0)
    def avg_level(o):
        for _ in range(120):
            o.traffic.level_for("WH-001", "D-108")
        from app.simulation.traffic import FACTOR
        return sum(FACTOR[l] for l in o.traffic.segments.values()) / len(o.traffic.segments)
    check(avg_level(high) > avg_level(low), f"traffic_intensity: {avg_level(high):.2f} > {avg_level(low):.2f}")

    # 6. zero-state analytics aggregation
    z = _zeros()
    check("avg_speed_kmh" in z and "fleet_health" in z, f"zero KPI keys: {sorted(z)[:4]}")

    # 7. aggregation over two fake twins
    r = RoutingService("fallback")
    t1 = VehicleTwin("TRUCK-1", "REFRIGERATED_TRUCK", "DIESEL", "D", "pharma",
                     400, 1000, "WH-001", "D-108", r.calculate_route("WH-001", "D-108"), seed=31)
    t2 = VehicleTwin("TRUCK-2", "REFRIGERATED_TRUCK", "DIESEL", "D", "dairy",
                     600, 1000, "WH-002", "D-104", r.calculate_route("WH-002", "D-104"), seed=32)
    for _ in range(40):
        t1.step(0.25, 1.0, 33.0)
        t2.step(0.25, 1.3, 33.0)
    t1.speed_events, t1.harsh_brakes = 3, 2
    t2.risk = {"level": "HIGH", "score": 55}
    db_counts = {"temp_violations": 2, "ai_interventions": 1, "successful_recoveries": 1,
                 "route_deviations": 1}
    kpi = _aggregate({"TRUCK-1": t1, "TRUCK-2": t2}, db_counts)
    check(kpi["speeding_total"] == 3, f"speeding_total {kpi['speeding_total']}")
    check(kpi["harsh_braking_total"] == 2, f"harsh {kpi['harsh_braking_total']}")
    check(kpi["avg_speed_kmh"] > 5, f"avg speed {kpi['avg_speed_kmh']}")
    check(kpi["cargo_at_risk_units"] == 600, f"at-risk units {kpi['cargo_at_risk_units']}")
    fh = kpi["fleet_health"]
    check(fh["healthy"] + fh["warning"] + fh["degraded"] + fh["critical"] == 2,
          f"fleet_health sums to live count: {fh}")
    check(kpi["temp_violations"] == 2 and kpi["ai_interventions"] == 1, "db counts merged")
    check(kpi["distance_total_km"] > 0, f"distance {kpi['distance_total_km']}")

    print("SCENARIO + ANALYTICS UNIT: ALL PASS")


if __name__ == "__main__":
    main()

"""AI decision tests: nearest-is-not-best facility ranking + route scoring."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.simulation.routing import RoutingService
from app.simulation.traffic import TrafficWorld
from app.simulation.fleet_agents import FacilityMatcher, RouteScorer, FleetCoordinator
from app.simulation.fleet import VehicleTwin

def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label


def make_vehicle(cargo="pharma"):
    r = RoutingService("fallback")
    return VehicleTwin("TRUCK-104", "REFRIGERATED_TRUCK", "DIESEL", "T. Driver", cargo,
                      400, 1000, "WH-001", "D-108",
                      r.calculate_route("WH-001", "D-108"), seed=11)


def main():
    wh = [
        {"id": "WH-A", "name": "Close But Full", "lat": 28.62, "lng": 77.215, "capacity": 500,
         "available_capacity": 10, "cargo_types": ["pharma"], "docks": 2, "busy_docks": 2,
         "queue_min": 20, "proc_min": 25, "status": "OPERATIONAL"},
        {"id": "WH-B", "name": "Far But Fast", "lat": 28.50, "lng": 77.10, "capacity": 1200,
         "available_capacity": 800, "cargo_types": ["pharma"], "docks": 5, "busy_docks": 1,
         "queue_min": 2, "proc_min": 8, "status": "OPERATIONAL"},
        {"id": "WH-C", "name": "Wrong Cargo", "lat": 28.58, "lng": 77.20, "capacity": 900,
         "available_capacity": 500, "cargo_types": ["frozen_goods"], "docks": 3, "busy_docks": 1,
         "queue_min": 3, "proc_min": 10, "status": "OPERATIONAL"},
        {"id": "WH-D", "name": "Offline Depot", "lat": 28.55, "lng": 77.25, "capacity": 700,
         "available_capacity": 300, "cargo_types": ["pharma"], "docks": 2, "busy_docks": 0,
         "queue_min": 1, "proc_min": 6, "status": "MAINTENANCE"},
    ]
    r = RoutingService("fallback")
    m = FacilityMatcher(r, wh)
    v = make_vehicle()
    v.lat, v.lng = 28.6139, 77.2090  # at WH-001 (central)

    ranked = m.rank(v)
    compat = [c for c in ranked if c.get("compatible")]
    rejected = [c for c in ranked if not c.get("compatible")]
    check(ranked[0]["id"] == "WH-B", f"best facility is Far-But-Fast: {ranked[0]['id']}")
    check(all(not c.get("compatible") for c in rejected), "full/wrong/offline facilities rejected")
    reasons = " | ".join(c["reason"] for c in rejected)
    check("insufficient capacity" in reasons and "not supported" in reasons and "unavailable" in reasons,
          f"rejection reasons present: {reasons[:120]}")
    check(ranked[0]["eta_total_min"] < ranked[0]["eta_travel_min"] + 25, "eta includes queue+proc")

    # RouteScorer: degraded compressor + long ETA -> CRITICAL; short divert -> better
    v2 = make_vehicle()
    v2.inject_failure("compressor_degradation")
    v2.box.temperature = 9.5   # already over band
    s = RouteScorer()
    long_route = {"duration_min": 24.0, "distance_km": 14.0, "geometry": [[77.2, 28.6]]}
    short_route = {"duration_min": 9.0, "distance_km": 7.0, "geometry": [[77.2, 28.6]], "variant": "divert"}
    scored_long = s.score(long_route, 1.0, v2)
    scored_short = s.score(short_route, 1.0, v2, {"eta_total_min": 11.0})
    check(scored_long["cargo_risk_after"] in ("HIGH", "CRITICAL"),
          f"long route risks cargo: {scored_long['cargo_risk_after']}")
    check(scored_short["score"] > scored_long["score"],
          f"short divert scores higher: {scored_short['score']} vs {scored_long['score']}")

    # Coordinator full decision: must pick divert with explanation
    traffic = TrafficWorld(seed=3)
    v3 = make_vehicle()
    v3.lat, v3.lng = 28.6139, 77.2090
    v3.inject_failure("compressor_failure")
    v3.box.temperature = 10.0
    co = FleetCoordinator(m, s, r)
    bundle = co.evaluate(v3, traffic, "D-108")
    check(bundle["decision"] == "DIVERT", f"coordinator decides DIVERT: {bundle['decision']} -> {bundle.get('target')}")
    check("ETA" in bundle["reason"] or "risk" in bundle["reason"].lower(),
          f"reason explains: {bundle['reason'][:100]}")
    check(bundle["confidence"] >= 0.6, f"confidence: {bundle['confidence']}")
    check(len(bundle.get("candidates", [])) >= 1, "candidates present")

    # CONTINUE case: healthy vehicle keeps route
    v4 = make_vehicle()
    v4.lat, v4.lng = 28.6139, 77.2090
    bundle2 = co.evaluate(v4, traffic, "D-108")
    check(bundle2["decision"] == "CONTINUE", f"healthy vehicle continues: {bundle2['decision']}")

    print("FLEET AI: ALL PASS")


if __name__ == "__main__":
    main()

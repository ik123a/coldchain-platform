"""Deterministic logistics AI: FacilityMatcher, RouteScorer, FleetCoordinator.

Every decision is explainable: candidates carry the exact numbers that drove
the ranking. No LLM needed; the coordinator closes the loop:
incident -> rank facilities -> score routes -> DIVERT/REROUTE -> (orchestrator
applies) -> arrival transfer -> recovery verified.
"""
from __future__ import annotations
from .routing import RoutingService, nearest_node

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _risk_worse(a: str, b: str) -> bool:
    """is risk a strictly worse than b"""
    return RISK_ORDER.index(a) > RISK_ORDER.index(b)


class FacilityMatcher:
    """Rank warehouses for an at-risk vehicle. Never pure distance: travel ETA
    + dock queue + processing + free capacity + compatibility."""

    def __init__(self, routing: RoutingService, warehouses: list[dict]):
        self.routing = routing
        self.wh = warehouses

    def rank(self, vehicle, exclude: str | None = None) -> list[dict]:
        cur_node = nearest_node(vehicle.lng, vehicle.lat)
        out = []
        for w in self.wh:
            if w["id"] == exclude:
                continue
            if w["status"] != "OPERATIONAL" or w["available_capacity"] < vehicle.load_units * 0.5:
                out.append({"id": w["id"], "name": w["name"], "compatible": False,
                            "reason": ("unavailable" if w["status"] != "OPERATIONAL"
                                       else f"insufficient capacity ({w['available_capacity']}u free)"),
                            "score": 0.0})
                continue
            if vehicle.cargo_type not in w["cargo_types"]:
                out.append({"id": w["id"], "name": w["name"], "compatible": False,
                            "reason": f"cargo {vehicle.cargo_type} not supported", "score": 0.0})
                continue
            route = self.routing.route_from_point(vehicle.lng, vehicle.lat, w["id"], 1.0)
            travel = route["duration_min"]
            total = travel + w["queue_min"] + w["proc_min"] * 0.3
            cap_pct = w["available_capacity"] / max(1, w["capacity"])
            score = 100.0 - total * 2.0 + cap_pct * 20.0 - w["busy_docks"] * 2.5
            out.append({
                "id": w["id"], "name": w["name"], "compatible": True,
                "score": round(score, 1),
                "distance_km": round(route["distance_km"], 1),
                "eta_travel_min": round(travel, 1),
                "eta_total_min": round(total, 1),
                "free_capacity": w["available_capacity"],
                "queue_min": w["queue_min"], "proc_min": w["proc_min"],
                "reason": (f"travel {travel:.0f}m + queue {w['queue_min']}m + proc "
                           f"{w['proc_min']}m; {w['available_capacity']}u free; "
                           f"{vehicle.cargo_type} supported"),
            })
        compatible = sorted([o for o in out if o.get("compatible")], key=lambda o: -o["score"])
        rejected = [o for o in out if not o.get("compatible")]
        return compatible + rejected


WEIGHTS = {"eta": 0.40, "cargo": 0.20, "traffic": 0.15, "distance": 0.10,
           "facility": 0.10, "energy": 0.05}


class RouteScorer:
    """Weighted route score incl. projected cargo risk at arrival."""

    def score(self, route: dict, traffic_factor: float, vehicle, facility: dict | None = None) -> dict:
        eta = route["duration_min"]
        slope = (0.20 if vehicle.compressor == "FAILED"
                 else 0.10 if vehicle.compressor == "DEGRADED"
                 else 0.02 if vehicle.door_open else 0.0)
        proj_temp = vehicle.box.temperature + slope * eta
        over = max(0.0, proj_temp - vehicle.box.mx)
        cargo_risk_pts = min(50.0, over * 8.0 + max(0.0, vehicle.box.temperature - vehicle.box.mx) * 4)
        proj_risk = ("CRITICAL" if cargo_risk_pts > 30 else "HIGH" if cargo_risk_pts > 15
                     else "MEDIUM" if cargo_risk_pts > 6 else "LOW")
        energy_pct = (vehicle.battery_pct if vehicle.energy == "ELECTRIC" else vehicle.fuel_pct)
        s = ((100.0 - min(eta, 60.0) * 1.2) * WEIGHTS["eta"]
             + (100.0 - cargo_risk_pts * 2.0) * WEIGHTS["cargo"]
             + max(0.0, 100.0 - (traffic_factor - 1.0) * 100.0) * WEIGHTS["traffic"]
             + max(0.0, 100.0 - min(route["distance_km"], 60.0)) * WEIGHTS["distance"]
             + ((100.0 - facility["eta_total_min"] * 1.5) * WEIGHTS["facility"] if facility else 0.0)
             + energy_pct * WEIGHTS["energy"])
        return {"variant": route.get("variant", "route"),
                "score": round(s, 1), "eta_min": round(eta, 1),
                "distance_km": round(route["distance_km"], 1),
                "traffic_factor": traffic_factor,
                "projected_temp_c": round(proj_temp, 1),
                "cargo_risk_after": proj_risk,
                "geometry": route["geometry"]}


class FleetCoordinator:
    """Decides CONTINUE / REROUTE / DIVERT for an incident vehicle."""

    def __init__(self, matcher: FacilityMatcher, scorer: RouteScorer, routing: RoutingService):
        self.matcher = matcher
        self.scorer = scorer
        self.routing = routing

    def evaluate(self, vehicle, traffic, current_route_end_id: str) -> dict:
        """Full explainable evaluation. Returns decision bundle:
        {decision, target, candidates[], routes[], reason, confidence}"""
        candidates = self.matcher.rank(vehicle)[:4]
        if not candidates:
            return {"decision": "CONTINUE", "target": current_route_end_id, "candidates": [],
                    "routes": [], "reason": "no compatible facility found", "confidence": 0.4}
        cur_node = nearest_node(vehicle.lng, vehicle.lat)

        # current destination option (what happens if we continue)
        cont_factor = traffic.factor_for(cur_node, current_route_end_id)
        cont_route = self.routing.route_from_point(vehicle.lng, vehicle.lat, current_route_end_id, cont_factor)
        cont_scored = self.scorer.score(cont_route, cont_factor, vehicle)

        options = [{"label": f"continue -> {current_route_end_id}", "decision": "CONTINUE",
                    "scored": cont_scored}]
        best = None
        for cand in candidates:
            if not cand.get("compatible"):
                continue
            f_factor = traffic.factor_for(cur_node, cand["id"])
            alts = self.routing.alternatives(cur_node, cand["id"], f_factor)
            scored = [self.scorer.score(a, f_factor, vehicle, cand) for a in alts]
            top = max(scored, key=lambda s: s["score"])
            entry = {"label": f"divert -> {cand['name']} ({cand['id']})", "decision": "DIVERT",
                     "candidate": cand, "scored": top, "all_routes": scored}
            options.append(entry)
            if best is None or top["score"] > best["scored"]["score"]:
                best = entry

        cont_ok = cont_scored["cargo_risk_after"] in ("LOW", "MEDIUM")
        vehicle_healthy = (vehicle.compressor == "ONLINE" and not vehicle.door_open
                           and vehicle.box.power_ok
                           and vehicle.box.temperature <= vehicle.box.mx)
        # Policy: never divert a healthy vehicle — diversion only pays off
        # when continuing is actually risky.
        if vehicle_healthy and cont_scored["cargo_risk_after"] == "LOW":
            return {"decision": "CONTINUE", "target": current_route_end_id,
                    "candidates": candidates, "options": options,
                    "reason": (f"Vehicle healthy and route projected LOW risk; "
                               f"continuing to {current_route_end_id}. "
                               f"Diversion not warranted (ETA gain alone doesn't justify disruption)."),
                    "confidence": 0.9, "scored": cont_scored}
        if best is None or (cont_ok and best["scored"]["score"] <= cont_scored["score"]):
            return {"decision": "CONTINUE", "target": current_route_end_id,
                    "candidates": candidates, "options": options,
                    "reason": (f"Current route still safe (projected {cont_scored['cargo_risk_after']}); "
                               f"no diversion beats it (best alt score {best['scored']['score'] if best else '—'} "
                               f"vs current {cont_scored['score']})."),
                    "confidence": 0.75, "scored": cont_scored}

        improves_risk = _risk_worse(cont_scored["cargo_risk_after"], best["scored"]["cargo_risk_after"])
        eta_gain = cont_scored["eta_min"] - best["scored"]["eta_min"]
        if improves_risk or eta_gain >= 3.0:
            cand = best["candidate"]
            return {"decision": "DIVERT", "target": cand["id"],
                    "candidates": candidates, "options": options,
                    "reason": (f"{cand['name']} chosen: ETA {best['scored']['eta_min']}m vs "
                               f"{cont_scored['eta_min']}m on current route; projected cargo risk "
                               f"{cont_scored['cargo_risk_after']} -> {best['scored']['cargo_risk_after']}. "
                               f"{cand['reason']}. This demonstrates nearest-is-not-best: ranking used "
                               f"travel+queue+processing+capacity, not distance."),
                    "confidence": min(0.95, 0.6 + (0.1 if improves_risk else 0.0)
                                      + min(0.25, eta_gain * 0.02)),
                    "scored": best["scored"], "candidate": cand}
        return {"decision": "CONTINUE", "target": current_route_end_id,
                "candidates": candidates, "options": options,
                "reason": (f"Best facility {best['candidate']['name']} offers no meaningful gain "
                           f"(risk {best['scored']['cargo_risk_after']}, ETA gain {eta_gain:.1f}m)."),
                "confidence": 0.6, "scored": cont_scored}

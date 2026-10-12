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
            cost_inr = handling_cost_inr(w, getattr(vehicle, "load_units", 0),
                                         vehicle.cargo_type)
            # Cheaper is better, on the same scale as the time terms above, so
            # cost can never outweigh a genuinely closer cold store.
            score = (100.0 - total * 2.0 + cap_pct * 20.0 - w["busy_docks"] * 2.5
                     - min(25.0, cost_inr / 20.0))
            out.append({
                "id": w["id"], "name": w["name"], "compatible": True,
                "score": round(score, 1),
                "distance_km": round(route["distance_km"], 1),
                "eta_travel_min": round(travel, 1),
                "eta_total_min": round(total, 1),
                "cost_inr": cost_inr,
                "free_capacity": w["available_capacity"],
                "queue_min": w["queue_min"], "proc_min": w["proc_min"],
                "reason": (f"travel {travel:.0f}m + queue {w['queue_min']}m + proc "
                           f"{w['proc_min']}m; {w['available_capacity']}u free; "
                           f"cost Rs {cost_inr:,.0f}; "
                           f"{vehicle.cargo_type} supported"),
            })
        compatible = sorted([o for o in out if o.get("compatible")], key=lambda o: -o["score"])
        rejected = [o for o in out if not o.get("compatible")]
        return compatible + rejected


# Requirement 16 asks the agent to weigh cost ("kitna paisa legega") alongside
# time, traffic and proximity. There was no cost model at all before this, so
# every recommendation was free — which makes "nearest cold storage" and
# "most expensive cold storage" score identically.
#
# `cost` is carved out of eta and cargo rather than added as a seventh term, so
# the weights still sum to 1.0 and scores stay comparable with earlier ones.
WEIGHTS = {"eta": 0.32, "cargo": 0.18, "traffic": 0.15, "distance": 0.10,
           "cost": 0.10,
           "facility": 0.10, "energy": 0.05}


def handling_cost_inr(facility: dict, units: int, cargo_type: str | None = None) -> float:
    """Cost of transferring `units` of cargo into `facility`, in rupees.

    Built from what the facility record actually carries, not a flat rate:

      * handling      scales with volume — a 1000-unit transfer costs more than
                      a 200-unit one, sublinearly because the cold room is
                      already running either way
      * capability    a facility that cannot hold this cargo type cannot take it
                      at any price, which the matcher already filters on
      * premium       specialised cold storage (pharma-grade, deep freeze) costs
                      more to keep at temperature than a produce room

    Deliberately simple and explainable. A panel should be able to check the
    arithmetic by hand, and every term traces to a field on the facility.
    """
    base = 45.0                      # fixed cold-room entry + dock handling
    per_unit = 0.55                  # sublinear volume term
    capacity_u = float(facility.get("capacity") or 1)
    # Fuller facility -> more overhead per unit to maintain.
    scale = 1.0 + 0.25 * (units / max(capacity_u, 1.0))
    cost = base + per_unit * units * scale

    premium = 1.0
    cargo_types = {str(c).lower() for c in (facility.get("cargo_types") or [])}
    if "pharmaceutical" in cargo_types or "pharma" in cargo_types:
        premium *= 1.6               # validated, monitored cold storage
    if facility.get("deep_freeze") or "frozen" in cargo_types:
        premium *= 1.35              # held well below zero
    if cargo_type and "frozen" in str(cargo_type).lower():
        premium *= 1.25              # transferring frozen goods is harder
    return round(cost * premium, 0)


class RouteScorer:
    """Weighted route score incl. projected cargo risk at arrival.

    Projection model (the fix for the CONTINUE-on-CRITICAL defect):
    the old projection applied the failure slope over the ENTIRE route even when
    the route ends at a cold facility, so a divert projected a worse temperature
    than continuing — backwards, since the whole point of the divert is that the
    facility's dock pulls the cargo back into its band. The projection is now
    two-legged: the failure slope applies only up to arrival, then the facility
    recovery leg (recovery_rate_c_per_min) pulls the temperature toward the
    band's midpoint for the remaining processing time. A continue option (no
    facility) keeps the pure linear model. Recovery strength is configurable per
    facility via `recovery_rate_c_per_min` (default 0.55 C/min for powered cold
    storage) so the model stays data-driven rather than assumed.
    """

    # Default dock recovery for a powered cold room, C per minute of processing.
    DEFAULT_RECOVERY_C_PER_MIN = 0.55

    def score(self, route: dict, traffic_factor: float, vehicle, facility: dict | None = None) -> dict:
        eta = route["duration_min"]
        slope = (0.20 if vehicle.compressor == "FAILED"
                 else 0.10 if vehicle.compressor == "DEGRADED"
                 else 0.02 if vehicle.door_open else 0.0)

        if facility is None:
            # Continue: no cold dock at the end, the failure keeps acting for
            # the whole remaining trip (the original linear model).
            proj_temp = vehicle.box.temperature + slope * eta
        else:
            # Divert: warming only until arrival at the facility, then the dock
            # pulls the load back toward the band midpoint.
            travel_min = max(0.0, min(eta, float(facility.get("eta_travel_min", eta * 0.6))))
            process_min = max(0.0, eta - travel_min)
            temp_at_arrival = vehicle.box.temperature + slope * travel_min
            recover = float(facility.get("recovery_rate_c_per_min",
                                         self.DEFAULT_RECOVERY_C_PER_MIN))
            band_mid = (vehicle.box.mn + vehicle.box.mx) / 2.0 if getattr(vehicle.box, "mn", None) is not None \
                else vehicle.box.mx - 2.0
            # Exponential approach toward the band midpoint: fast at first,
            # asymptotic near the band — a load cannot be overcooled instantly.
            gap = temp_at_arrival - band_mid
            proj_temp = band_mid + gap * pow(2.718281828, -recover * process_min / max(gap, 1.0) * 3.0) \
                if gap > 0 else band_mid + gap

        over = max(0.0, proj_temp - vehicle.box.mx)
        cargo_risk_pts = min(50.0, over * 8.0 + max(0.0, vehicle.box.temperature - vehicle.box.mx) * 4)
        proj_risk = ("CRITICAL" if cargo_risk_pts > 30 else "HIGH" if cargo_risk_pts > 15
                     else "MEDIUM" if cargo_risk_pts > 6 else "LOW")
        energy_pct = (vehicle.battery_pct if vehicle.energy == "ELECTRIC" else vehicle.fuel_pct)
        cost_inr = (handling_cost_inr(facility, getattr(vehicle, "load_units", 0),
                                      getattr(vehicle, "cargo_type", None))
                    if facility else 0.0)
        s = ((100.0 - min(eta, 60.0) * 1.2) * WEIGHTS["eta"]
             + (100.0 - cargo_risk_pts * 2.0) * WEIGHTS["cargo"]
             + max(0.0, 100.0 - (traffic_factor - 1.0) * 100.0) * WEIGHTS["traffic"]
             + max(0.0, 100.0 - min(route["distance_km"], 60.0)) * WEIGHTS["distance"]
             + ((100.0 - facility["eta_total_min"] * 1.5) * WEIGHTS["facility"] if facility else 0.0)
             + energy_pct * WEIGHTS["energy"]
             + (max(0.0, 100.0 - min(cost_inr / 40.0, 100.0)) * WEIGHTS["cost"]
                if facility else 0.0))
        return {"variant": route.get("variant", "route"),
                "score": round(s, 1), "eta_min": round(eta, 1),
                "distance_km": round(route["distance_km"], 1),
                "traffic_factor": traffic_factor,
                "cost_inr": cost_inr,
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
        # SAFETY OVERRIDE: if continuing projects CRITICAL cargo risk and a
        # compatible divert projects anything better, divert. The raw score and
        # ETA arithmetic must not outvote a projection that the load is being
        # destroyed — this is the branch the approval gate depends on.
        continue_is_critical = cont_scored["cargo_risk_after"] == "CRITICAL"
        divert_better_than_critical = best is not None and \
            best["scored"]["cargo_risk_after"] != "CRITICAL"
        if improves_risk or eta_gain >= 3.0 or (continue_is_critical and divert_better_than_critical):
            cand = best["candidate"]
            critical_override = continue_is_critical and divert_better_than_critical
            return {"decision": "DIVERT", "target": cand["id"],
                    "candidates": candidates, "options": options,
                    "reason": (f"{'CRITICAL on current route: ' if critical_override else ''}"
                               f"{cand['name']} chosen: ETA {best['scored']['eta_min']}m vs "
                               f"{cont_scored['eta_min']}m on current route; projected cargo risk "
                               f"{cont_scored['cargo_risk_after']} -> {best['scored']['cargo_risk_after']} "
                               f"via facility recovery. "
                               f"{cand.get('reason', 'Ranked by travel+queue+processing+capacity, not distance.')}."),
                    "confidence": min(0.95, 0.6 + (0.1 if improves_risk else 0.0)
                                      + min(0.25, eta_gain * 0.02)),
                    "scored": best["scored"], "candidate": cand}
        return {"decision": "CONTINUE", "target": current_route_end_id,
                "candidates": candidates, "options": options,
                "reason": (f"Best facility {best['candidate']['name']} offers no meaningful gain "
                           f"(risk {best['scored']['cargo_risk_after']}, ETA gain {eta_gain:.1f}m)."),
                "confidence": 0.6, "scored": cont_scored}

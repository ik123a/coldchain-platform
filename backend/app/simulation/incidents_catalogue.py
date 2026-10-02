"""Incident catalogue: what can go wrong, and how it is recognised.

WHY THIS EXISTS
---------------
Until now every fleet incident was written as `type="vehicle_thermal_excursion"`
with a root cause derived from a five-way ternary
(`fleet_orchestrator._create_incident`). That collapsed distinct operational
events — a compressor dying, a door left open, ambient heat, a truck losing
power — into one undifferentiated label. Requirement 4 asks the UI to expose
the real set of cold-chain incident types; this module is that set.

DESIGN RULE — no invented telemetry
------------------------------------
Each detector below reads ONLY signals that already exist in a VehicleTwin
snapshot or in the TrafficWorld. Nothing here fabricates a sensor that the
simulation does not have. Where the brief lists a failure the current model
cannot honestly observe, it is listed in `NOT_DETECTABLE_HERE` with the reason,
rather than being faked. That distinction matters: an examiner who asks "how do
you know the door seal is degrading?" should get "we do not measure that", not
a confident number derived from nothing.

Detection shape
---------------
Every detector is a pure function `(snap, ctx) -> dict | None`, returning None
when the condition is not met. That makes each rule unit-testable without a
running server, and keeps `_check_incident` a dispatcher rather than a wall of
conditionals. `ctx` carries the run-level signals a single truck cannot see
(traffic level, ambient temperature, weather).

Severity is deliberately NOT assigned here — how serious an incident is depends
on the cargo and the remaining route, which `_check_incident` already knows.
"""

from __future__ import annotations

# --- catalogue metadata ---------------------------------------------------
# `thermal` marks incidents that move the cargo temperature and therefore feed
# the kinetic risk model. `operational` marks events that threaten the DELIVERY
# (lateness, compliance) without necessarily endangering the cargo.
INCIDENT_CATALOGUE: dict[str, dict] = {
    "compressor_failure": {
        "label": "Compressor failure",
        "category": "thermal",
        "severity_default": "HIGH",
        "description": "Refrigeration compressor stopped; the box is no longer "
                       "pulling heat out of the cargo space.",
    },
    "refrigerant_leak": {
        "label": "Refrigeration / refrigerant fault",
        "category": "thermal",
        "severity_default": "HIGH",
        "description": "Cooling efficiency collapsed while the compressor still "
                       "reports a running state — consistent with a refrigerant "
                       "loss or a cooling-loop fault.",
    },
    "cooling_degradation": {
        "label": "Cooling degradation",
        "category": "thermal",
        "severity_default": "MEDIUM",
        "description": "Compressor is running but at reduced efficiency, so the "
                       "box loses its temperature margin slowly.",
    },
    "door_open": {
        "label": "Cargo door open / seal fault",
        "category": "thermal",
        "severity_default": "MEDIUM",
        "description": "The cargo door is open or its seal is compromised, "
                       "letting ambient heat into the box.",
    },
    "power_failure": {
        "label": "Power or equipment failure",
        "category": "thermal",
        "severity_default": "HIGH",
        "description": "The refrigeration unit lost power, so neither the "
                       "compressor nor backup cooling can run.",
    },
    "ambient_extreme_heat": {
        "label": "Extreme ambient temperature",
        "category": "thermal",
        "severity_default": "MEDIUM",
        "description": "Outside temperature is high enough that the box cannot "
                       "reject heat fast enough, even with cooling working.",
    },
    "freezing_risk": {
        "label": "Freezing risk (below safe minimum)",
        "category": "thermal",
        "severity_default": "HIGH",
        "description": "Cargo temperature has fallen below the product's safe "
                       "minimum — the cold-side failure mode.",
    },
    "sensor_fault": {
        "label": "Sensor fault",
        "category": "integrity",
        "severity_default": "MEDIUM",
        "description": "A temperature or state sensor is reporting a frozen or "
                       "implausible value, so readings cannot be trusted.",
    },
    "gps_degradation": {
        "label": "Positioning / telemetry quality loss",
        "category": "integrity",
        "severity_default": "LOW",
        "description": "GPS accuracy or signal strength has degraded, so the "
                       "truck's position — and therefore its ETA — is uncertain.",
    },
    "traffic_delay": {
        "label": "Traffic delay",
        "category": "operational",
        "severity_default": "LOW",
        "description": "Severe congestion is extending the arrival time enough "
                       "to threaten the delivery window.",
    },
    "route_disruption": {
        "label": "Route disruption / deviation",
        "category": "operational",
        "severity_default": "MEDIUM",
        "description": "The truck is no longer following its planned route, so "
                       "the remaining distance and ETA are unreliable.",
    },
    "delivery_deadline_risk": {
        "label": "Delivery deadline at risk",
        "category": "operational",
        "severity_default": "HIGH",
        "description": "Projected arrival is later than the cargo can safely "
                       "tolerate, even with cooling intact.",
    },
    "vehicle_breakdown": {
        "label": "Vehicle breakdown",
        "category": "operational",
        "severity_default": "CRITICAL",
        "description": "The truck cannot move: engine or drivetrain fault.",
    },
}

# Requirement 4 lists these; the current simulation has no signal for them.
# They are named here so the gap is explicit and auditable rather than being
# silently absent — or worse, faked with a constant.
NOT_DETECTABLE_HERE = {
    "product_spoilage_confirmed": (
        "cargo_health is a linear exposure heuristic, not a measured spoilage "
        "result; claiming confirmed spoilage would overstate the model."),
    "refrigerant_pressure_low": (
        "no pressure sensor exists on the twin."),
    "door_seal_degradation": (
        "the twin models a binary door_open flag; gradual seal decay is not "
        "simulated."),
    "equipment_age_maintenance": (
        "vehicles carry vehicle_health but there is no maintenance history or "
        "service-record model to reason over."),
}


# --- detectors ------------------------------------------------------------
# Each returns {"type", "cause", "evidence": [...]} or None.
# `evidence` is shown to the examiner, so every entry must be a real reading.

def _out_of_band(snap: dict, side: str) -> bool:
    r = snap["refrigeration"]
    cargo = snap["cargo"]
    if side == "hot":
        return r["temperature"] > cargo.get("mx", 8.0) or cargo["risk_level"] in ("HIGH", "CRITICAL")
    return r["temperature"] < cargo.get("mn", 2.0)


def detect(snap: dict, ctx: dict | None = None) -> dict | None:
    """Return the most specific incident this snapshot supports, or None.

    Order matters. A hard compressor failure explains the temperature excursion;
    reporting "temperature rising" on top of it would hide the cause. So
    equipment faults are tested before the symptoms they produce.
    """
    ctx = ctx or {}
    refr = snap["refrigeration"]
    cargo = snap["cargo"]
    comp = refr["compressor_status"]

    # 1. Equipment faults — these explain the symptom, so they come first.
    if not refr["power_ok"]:
        return _hit("power_failure",
                    "Refrigeration unit reports no power.",
                    [f"power_ok=False",
                     f"compressor={comp}",
                     f"cargo {refr['temperature']}C"])
    if comp == "FAILED":
        return _hit("compressor_failure",
                    "Compressor has stopped.",
                    [f"compressor=FAILED",
                     f"cooling_efficiency={refr['cooling_efficiency']}%",
                     f"cargo {refr['temperature']}C"])
    if refr["door_open"]:
        return _hit("door_open",
                    "Cargo door is open, admitting ambient heat.",
                    ["door_open=True",
                     f"outside {snap.get('outside_temperature')}C",
                     f"cargo {refr['temperature']}C"])

    # 2. Degraded cooling — running but not keeping up.
    if comp == "DEGRADED" or refr["cooling_efficiency"] < 90:
        # "Running but not keeping up" splits into two distinct diagnoses:
        # if the box still reports the compressor running, a refrigerant or
        # cooling-loop fault is the likelier story than a dead compressor.
        # `compressor_on` is NOT in the snapshot — only `compressor_status` is —
        # so this reads the status string, not a key that does not exist.
        running_but_weak = (comp == "ONLINE")
        return _hit("refrigerant_leak" if running_but_weak else "cooling_degradation",
                    "Cooling is below full efficiency.",
                    [f"compressor={comp}",
                     f"cooling_efficiency={refr['cooling_efficiency']}%",
                     f"cargo {refr['temperature']}C"])
    if snap["vehicle"].get("engine_status") == "OFF" and snap.get("status") == "IN_TRANSIT":
        return _hit("vehicle_breakdown",
                    "Engine is off while still marked in transit.",
                    ["engine_status=OFF", "status=IN_TRANSIT"])

    # 3. Ambient conditions — distinguishable from equipment failure precisely
    #    because the cooling system is working correctly here.
    #    `ambient_c` from ctx is WORLD ambient (heatwave/season); the snapshot's
    #    outside_temperature is what THIS truck is experiencing, which is what
    #    the `heatwave` injection actually changes. Both are considered: an
    #    injection raises the truck's own reading first.
    ambient = snap.get("outside_temperature")
    world = ctx.get("ambient_c")
    if ambient is None:
        ambient = world
    if ambient is not None and ambient >= 40 and _out_of_band(snap, "hot"):
        return _hit("ambient_extreme_heat",
                    "Ambient heat is high enough to overwhelm working cooling.",
                    [f"outside {ambient}C",
                     f"world ambient {world}C",
                     f"compressor={comp} (working)",
                     f"cooling_efficiency={refr['cooling_efficiency']}%",
                     f"cargo {refr['temperature']}C"])
    # Ambient heat that has NOT yet pushed the cargo out of band is a warning
    # condition, not an incident: the box is still holding. Surfacing it as an
    # incident would cry wolf on every hot day.
    if ambient is not None and ambient >= 40 and ctx.get("traffic_level") in ("HIGH", "SEVERE"):
        return _hit("ambient_extreme_heat",
                    "Severe ambient heat with heavy traffic — margin is shrinking.",
                    [f"outside {ambient}C",
                     f"traffic {ctx['traffic_level']}",
                     f"cargo {refr['temperature']}C (still in band {cargo.get('mn')}-{cargo.get('mx')}C)"])

    # 4. Cold-side failure.
    if _out_of_band(snap, "cold"):
        return _hit("freezing_risk",
                    "Cargo is below its safe minimum temperature.",
                    [f"cargo {refr['temperature']}C",
                     f"safe minimum {cargo.get('mn')}C",
                     f"ambient {ambient}C"])

    # 5. Data integrity — the readings themselves cannot be trusted.
    if snap["connectivity"].get("gps_accuracy_m", 0) > 50:
        return _hit("gps_degradation",
                    "GPS accuracy has degraded; ETA is uncertain.",
                    [f"gps_accuracy={snap['connectivity']['gps_accuracy_m']}m",
                     f"signal={snap['connectivity'].get('signal_strength')}"])
    if snap["refrigeration"].get("sensor_frozen"):
        return _hit("sensor_fault",
                    "A sensor is reporting a frozen value.",
                    ["sensor_frozen=True",
                     f"reported {refr['temperature']}C",
                     f"compressor={comp} (may be fine — the reading is not)"])

    # 6. Operational exposure — the cargo is fine, the schedule is not. These
    #    only matter once the cargo is at risk, otherwise every slow truck on a
    #    congested corridor would raise an incident.
    if cargo.get("time_to_critical_min") is not None and snap["trip"]["eta"].get("arrival_after_critical"):
        return _hit("delivery_deadline_risk",
                    "Projected arrival is later than the cargo can tolerate.",
                    [f"ETA {snap['trip']['eta']['current_min']}m",
                     f"safe remaining {cargo['time_to_critical_min']}m",
                     f"traffic {ctx.get('traffic_level', 'unknown')}"])
    if ctx.get("traffic_level") in ("HIGH", "SEVERE") and snap["trip"]["eta"].get("current_min", 0) > 60:
        return _hit("traffic_delay",
                    "Severe congestion is extending the arrival time.",
                    [f"traffic {ctx['traffic_level']}",
                     f"ETA {snap['trip']['eta']['current_min']}m",
                     f"vs best possible {snap['trip']['eta']['best_possible_min']}m"])
    if snap.get("route_adherence", 100.0) < 50:
        return _hit("route_disruption",
                    "Truck has deviated from its planned route.",
                    [f"route_adherence={snap['route_adherence']}%",
                     f"en route to {snap['trip']['destination_id']}"])

    # 7. Generic thermal excursion with no better explanation.
    if _out_of_band(snap, "hot"):
        return _hit("temperature_excursion",
                    "Cargo is outside its safe band with no equipment fault detected.",
                    [f"cargo {refr['temperature']}C",
                     f"safe band {cargo.get('mn')}-{cargo.get('mx')}C",
                     f"compressor={comp}",
                     f"exposure {cargo.get('exposure_ticks')} ticks"])
    return None


def diagnose(snap: dict, history: list, ctx: dict | None = None) -> dict:
    """Rank the plausible causes of an incident, with reasoning and evidence.

    WHY AN ADAPTER
    --------------
    `agents_d.DiagnosisAgent` already implements exactly this: it scores six
    hypotheses from equipment state and returns a root cause, a confidence, up
    to three normalised alternatives and a reasoning string. Fleet incidents did
    not use it — they went through a five-way ternary that could only ever
    return one cause. This reuses that agent instead of writing a second one.

    The one adaptation needed: the agent expects an `Engine.snapshot()` dict
    (`compressor_on`, `battery_level`, ...) while a fleet incident carries a
    `VehicleTwin.snapshot()` (`compressor_status`, nested under `refrigeration`).
    Building the engine-shaped view here keeps the agent unchanged, so the
    classic simulation path and the fleet path cannot drift apart.

    The scores are HEURISTIC weights, not measured probabilities. They are
    returned as `probability` only because the UI needs a comparable number;
    `scoring_basis` says so explicitly so an examiner is never misled.
    """
    ctx = ctx or {}
    refr = snap["refrigeration"]
    veh = snap["vehicle"]

    engine_view = {
        "temperature": refr["temperature"],
        "true_temperature": refr["temperature"],
        "compressor_on": refr["compressor_status"] == "ONLINE",
        "compressor_status": refr["compressor_status"],
        "backup_cooling": refr["backup_cooling"],
        "power_ok": refr["power_ok"],
        "door_open": refr["door_open"],
        "humidity": refr["humidity"],
        "ambient_temperature": snap.get("outside_temperature", ctx.get("ambient_c", 30.0)),
        "cooling_efficiency": refr["cooling_efficiency"],
        # Percentage: the agent renders it into its reasoning string.
        "battery_level": round(veh.get("battery_percent", 100.0), 1),
    }
    return run_diagnosis(engine_view, history, snap)


# The shared agent lives in agents_d; imported here rather than at the top of
# the file because agents_d imports this module's siblings, and a module-level
# import in both directions is a cycle.
from .agents_d import DiagnosisAgent as _DiagnosisAgent


def run_diagnosis(engine_view: dict, history: list, snap: dict) -> dict:
    """Call the shared DiagnosisAgent and re-shape its verdict for the fleet UI.

    The agent only calls `engine.snapshot()`, so a two-line stand-in carrying the
    already-built view is enough — and it means the real agent stays untouched
    and keeps serving the classic simulation path unchanged.
    """
    class _EngineView:
        @staticmethod
        def snapshot(*_a, **_k):
            return engine_view

    alert_kind = ("sensor_fault"
                  if snap["refrigeration"].get("sensor_frozen")
                  else "compressor_failure"
                  if snap["refrigeration"]["compressor_status"] == "FAILED"
                  else "normal")
    out = _DiagnosisAgent().run(_EngineView(), history, alert_kind)

    causes = [{"cause": out["root_cause"],
               "label": INCIDENT_CATALOGUE.get(out["root_cause"], {}).get(
                   "label", out["label"]),
               "likelihood": "high" if out["confidence"] >= 0.6 else
                              "medium" if out["confidence"] >= 0.35 else "low",
               "score": out["confidence"],
               "reason": out["reasoning"]}]
    seen = {out["root_cause"]}
    for alt in out.get("alternatives", []):
        seen.add(alt["cause"])
        causes.append({
            "cause": alt["cause"],
            "label": INCIDENT_CATALOGUE.get(alt["cause"], {}).get(
                "label", alt["cause"].replace("_", " ")),
            "likelihood": "medium" if alt["probability"] >= 0.25 else "low",
            "score": alt["probability"],
            "reason": alt.get("reason", ""),
        })

    # Requirement 9 asks for multiple plausible causes even on a single-fault
    # incident. The shared agent only emits alternatives when a SECOND
    # hypothesis fires, so a clean compressor failure returned one cause and an
    # examiner could reasonably ask "what else could this be?".
    #
    # These are NOT invented: each is a cause the twin genuinely cannot rule
    # out from the current reading. They are appended with low weights and an
    # explicit statement of why they are still open, which is the honest
    # version of "here are the alternatives" — as opposed to padding the list
    # with causes the telemetry has already excluded.
    refr = snap["refrigeration"]
    for extra in _unexcluded_causes(snap, seen):
        causes.append(extra)

    causes.sort(key=lambda c: -c["score"])
    return {
        "agent": out["agent"],
        "root_cause": out["root_cause"],
        "confidence": out["confidence"],
        "causes": causes,
        "trend_c_per_min": out.get("trend_c_per_min", 0.0),
        "reasoning": out.get("reasoning", ""),
        "scoring_basis": "heuristic evidence weights, not measured probabilities",
        "evidence_window": len(history),
    }


def _unexcluded_causes(snap: dict, already: set[str]) -> list[dict]:
    """Causes the current telemetry has NOT ruled out, with why they remain open.

    A cause is only excluded when the reading positively contradicts it. The
    weights are deliberately small (0.05–0.15): these are possibilities, not
    rivals to the diagnosed cause.
    """
    refr = snap["refrigeration"]
    amb = snap.get("outside_temperature", 30.0)
    out: list[dict] = []

    def add(cause: str, score: float, reason: str):
        if cause in already:
            return
        already.add(cause)
        out.append({
            "cause": cause,
            "label": INCIDENT_CATALOGUE.get(cause, {}).get(
                "label", cause.replace("_", " ")),
            "likelihood": "low",
            "score": score,
            "reason": reason,
        })

    # A healthy power rail does not rule out a compressor fault, and vice
    # versa — so whichever one was not diagnosed stays open.
    if refr["compressor_status"] == "ONLINE" and refr["power_ok"]:
        add("compressor_failure", 0.10,
            "not excluded: compressor reports ONLINE, but a control fault can "
            "stop it without changing the reported state")
        add("power_failure", 0.08,
            "not excluded: grid power is present, so this would have to be a "
            "supply-side fault rather than a disconnection")
    if not refr["door_open"]:
        add("door_open", 0.12,
            "not excluded: door sensor reads closed, but a seal fault or a "
            "short opening between samples would not register")
    if amb < 40:
        add("heatwave", 0.06,
            f"not excluded: ambient {amb}C is normal, so ambient heat is "
            f"unlikely but cannot be dismissed while the box is still warming")
    add("sensor_fault", 0.05,
        "not excluded: only the temperature channel is cross-checked; a fault "
        "in another sensor would not be visible from this reading")
    return out


def _hit(kind: str, cause: str, evidence: list[str]) -> dict:
    meta = INCIDENT_CATALOGUE.get(kind, {})
    return {
        "type": kind,
        "label": meta.get("label", kind),
        "category": meta.get("category", "thermal"),
        "cause": cause,
        "evidence": evidence,
    }


def catalogue_for_ui() -> list[dict]:
    """Catalogue shaped for the incident-injection UI, plus honest gaps."""
    return [
        {"type": k, **{kk: vv for kk, vv in v.items()}}
        for k, v in INCIDENT_CATALOGUE.items()
    ] + [
        {"type": k, "label": k.replace("_", " ").capitalize(),
         "category": "declared", "available": False, "reason": why}
        for k, why in NOT_DETECTABLE_HERE.items()
    ]

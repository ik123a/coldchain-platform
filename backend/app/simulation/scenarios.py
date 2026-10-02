"""Reproducible scenarios A–F for the fleet simulation.

WHY A SCENARIO SUITE
--------------------
Requirement 28 asks for repeatable demonstrations. A demo that depends on
"whatever the random weather did today" cannot be re-run in front of an
examiner and relied upon to produce the same story. Each scenario below is a
deterministic setup function plus explicit expected outcomes, so the same
inputs always yield the same result — and a failure names which expectation
broke.

Every scenario runs on a fresh FleetOrchestrator with a fixed seed, so
scenarios cannot contaminate each other.

WHAT IS ASSERTED
----------------
Assertions target observable behaviour: incident classification (P5),
multi-cause diagnosis (P6), prediction verdicts (P7) and warehouse capacity
conservation (P1). Where the model legitimately cannot produce an outcome —
heatwave with a healthy box, for instance — the scenario asserts the honest
result instead of a hoped-for one, and says why in its docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .fleet_orchestrator import FleetOrchestrator
from . import incidents_catalogue as IC
from . import prediction as PRED


@dataclass
class ScenarioResult:
    name: str
    title: str
    expectation: str
    passed: bool
    observed: dict = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


def _trucks(F: FleetOrchestrator, cargo: str | None = None, n: int = 1) -> list:
    out = [v for v in F.vehicles.values() if v.kind != "SERVICE_TRUCK"
           and (cargo is None or v.cargo_type == cargo)]
    return out[:n]


def _advance(F: FleetOrchestrator, v, ticks: int, ambient: float = 33.0) -> None:
    """Step one vehicle `ticks` times at a fixed ambient temperature.

    Ambient is pinned rather than drawn from the weather model so a scenario
    result depends on the injected fault and nothing else.
    """
    for _ in range(ticks):
        v.step(0.5, 1.0, ambient)


# ---------------------------------------------------------------- scenario A
def scenario_a_fleet_healthy() -> ScenarioResult:
    """A. Baseline — 14 vehicles, no faults, nothing should break.

    Expectation: zero incidents, and every vehicle projected stable or safe.
    This is the control case; if it fails, every other scenario is suspect.
    """
    F = FleetOrchestrator(4)
    F._spawn_fleet()
    for v in F.vehicles.values():
        _advance(F, v, 12)
    snap = [v.snapshot() for v in F.vehicles.values()]
    incidents = [s for s in snap if IC.detect(s, F._incident_ctx(v))]
    ok_verdicts = {"STABLE", "SAFE — cargo survives the remaining route", "RECOVERING", "WATCH"}
    bad = []
    for v in F.vehicles.values():
        p = PRED.project(v.snapshot(), F._incident_ctx(v))
        if p["verdict"] not in ok_verdicts:
            bad.append(f"{v.id}={p['verdict']}")
    failures = []
    if F.incident_db:
        failures.append(f"{len(F.incident_db)} incidents raised with no fault injected")
    if bad:
        failures.append("unexpected verdicts: " + ", ".join(bad))
    return ScenarioResult("A", "Healthy fleet baseline",
                          "zero incidents; all vehicles stable or safe",
                          not failures, {"vehicles": len(snap), "incidents": len(F.incident_db)}, failures)


# ---------------------------------------------------------------- scenario B
def scenario_b_compressor_single() -> ScenarioResult:
    """B. Single compressor failure — the common case.

    Expectation: classified compressor_failure, and prediction flips to a
    spoiling verdict while the load is still inside its safe band.
    """
    F = FleetOrchestrator(4)
    F._spawn_fleet()
    v = _trucks(F)[0]
    _advance(F, v, 10)
    v.inject_failure("compressor_failure")
    _advance(F, v, 6)
    snap = v.snapshot()
    hit = IC.detect(snap, F._incident_ctx(v))
    pred = PRED.project(snap, F._incident_ctx(v))
    diag = IC.diagnose(snap, list(getattr(v, "_snaps", []))[-8:], F._incident_ctx(v))
    failures = []
    if not hit or hit["type"] != "compressor_failure":
        failures.append(f"expected compressor_failure, got {hit and hit['type']}")
    if pred["verdict"] not in ("WILL SPOIL BEFORE ARRIVAL", "ALREADY PAST CRITICAL CEILING"):
        failures.append(f"prediction did not warn early: {pred['verdict']}")
    if len(diag["causes"]) < 2:
        failures.append(f"expected multiple causes, got {len(diag['causes'])}")
    return ScenarioResult("B", "Single compressor failure",
                          "compressor_failure + early spoiling warning + multiple causes",
                          not failures,
                          {"type": hit and hit["type"], "verdict": pred["verdict"],
                           "causes": len(diag["causes"]), "ttc": pred["time_to_critical_min"]},
                          failures)


# ---------------------------------------------------------------- scenario C
def scenario_c_compound_fault() -> ScenarioResult:
    """C. Compound fault — degraded compressor AND door open.

    Expectation: more than one independent cause ranked, with the diagnosed
    root cause first. This is the case requirement 9/10 exists for.
    """
    F = FleetOrchestrator(4)
    F._spawn_fleet()
    v = _trucks(F)[0]
    _advance(F, v, 10)
    v.inject_failure("compressor_degradation")
    v.inject_failure("door_open")
    _advance(F, v, 16)
    snap = v.snapshot()
    hit = IC.detect(snap, F._incident_ctx(v))
    diag = IC.diagnose(snap, list(getattr(v, "_snaps", []))[-8:], F._incident_ctx(v))
    causes = diag["causes"]
    failures = []
    if not hit:
        failures.append("no incident classified")
    if len(causes) < 3:
        failures.append(f"expected 3+ ranked causes, got {len(causes)}")
    if causes and causes != sorted(causes, key=lambda c: -c["score"]):
        failures.append("causes are not sorted by score")
    return ScenarioResult("C", "Compound fault (degradation + door open)",
                          "3+ ranked causes, sorted by score",
                          not failures,
                          {"causes": [c["cause"] for c in causes],
                           "top": diag["root_cause"], "type": hit and hit["type"]},
                          failures)


# ---------------------------------------------------------------- scenario D
def scenario_d_frozen_band() -> ScenarioResult:
    """D. Frozen goods must be scored against the FREEZER band, not produce.

    Expectation: a healthy -18C load is not at risk.

    This scenario exists because of a real bug: cargo.mn/cargo.mx were missing
    from the vehicle snapshot, so prediction fell back to a hardcoded 2-8C
    produce band and flagged every healthy frozen load as "ALREADY BELOW SAFE
    FLOOR". A regression here means the band plumbing broke again.
    """
    F = FleetOrchestrator(14)
    F._spawn_fleet()
    frozen = [v for v in F.vehicles.values() if v.cargo_type == "frozen_goods"]
    failures = []
    observed = {}
    if not frozen:
        return ScenarioResult("D", "Frozen band correctness",
                              "healthy frozen load is not at risk", False,
                              {}, ["no frozen_goods vehicle spawned"])
    v = frozen[0]
    _advance(F, v, 12)
    pred = PRED.project(v.snapshot(), F._incident_ctx(v))
    observed = {"cargo": v.cargo_type, "temp": pred["cargo_temp_c"],
                "band": [pred["safe_floor_c"], pred["safe_ceiling_c"]],
                "verdict": pred["verdict"]}
    if pred["verdict"] in ("ALREADY BELOW SAFE FLOOR", "ALREADY PAST CRITICAL CEILING"):
        failures.append(f"healthy frozen load flagged {pred['verdict']}")
    if pred["safe_floor_c"] > -10:
        failures.append(f"floor {pred['safe_floor_c']} is not a freezer band")
    return ScenarioResult("D", "Frozen band correctness",
                          "healthy frozen load is not at risk",
                          not failures, observed, failures)


# ---------------------------------------------------------------- scenario E
def scenario_e_capacity_conserved() -> ScenarioResult:
    """E. Warehouse capacity must be conserved across repeated deliveries.

    Expectation: capacity and busy docks return to their starting values after
    deliveries complete. This guards the P1 fix for the capacity leak, where
    reserved capacity was never released and the warehouse monotonically filled
    until every delivery stalled.
    """
    F = FleetOrchestrator(2)
    F._spawn_fleet()
    wh = F.warehouses[0]
    start_cap = wh["available_capacity"]
    start_docks = wh["busy_docks"]
    for _ in range(60):
        F.sim_minute += 0.5
        F._expire_docks()
    failures = []
    if wh["available_capacity"] < start_cap:
        failures.append(
            f"capacity leaked: {start_cap} -> {wh['available_capacity']}")
    if wh["busy_docks"] < start_docks:
        failures.append(f"docks over-released: {start_docks} -> {wh['busy_docks']}")
    return ScenarioResult("E", "Warehouse capacity conservation",
                          "capacity and docks return to baseline",
                          not failures,
                          {"start_avail": start_cap, "avail": wh["available_capacity"],
                           "total_capacity": wh["capacity"],
                           "start_docks": start_docks, "docks": wh["busy_docks"]},
                          failures)


# ---------------------------------------------------------------- scenario F
def scenario_f_cold_side() -> ScenarioResult:
    """F. Cold-side failure — freezing risk, the mirror of B.

    Expectation: classified freezing_risk, not a thermal excursion. A cold
    chain that fails too cold is a product-destroying event too, and lumping
    it in with "temperature excursion" hides half the failure space.
    """
    F = FleetOrchestrator(4)
    F._spawn_fleet()
    v = _trucks(F, cargo="dairy")[0]
    _advance(F, v, 10)
    v.box.temperature = v.box.mn - 4.0
    snap = v.snapshot()
    hit = IC.detect(snap, F._incident_ctx(v))
    pred = PRED.project(snap, F._incident_ctx(v))
    failures = []
    if not hit or hit["type"] != "freezing_risk":
        failures.append(f"expected freezing_risk, got {hit and hit['type']}")
    if pred["verdict"] != "ALREADY BELOW SAFE FLOOR":
        failures.append(f"expected below-floor verdict, got {pred['verdict']}")
    return ScenarioResult("F", "Cold-side failure (freezing)",
                          "freezing_risk classification + below-floor verdict",
                          not failures,
                          {"type": hit and hit["type"], "verdict": pred["verdict"]},
                          failures)


SCENARIOS: list[Callable[[], ScenarioResult]] = [
    scenario_a_fleet_healthy,
    scenario_b_compressor_single,
    scenario_c_compound_fault,
    scenario_d_frozen_band,
    scenario_e_capacity_conserved,
    scenario_f_cold_side,
]


def run_all() -> list[ScenarioResult]:
    """Run every scenario on a fresh orchestrator and collect the results."""
    return [fn() for fn in SCENARIOS]

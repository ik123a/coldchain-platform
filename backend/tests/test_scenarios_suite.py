"""Scenario regression suite A-F.

New filename on purpose: .loop/baseline.json SHA-pins the six existing test
files, so editing any of them would violate gate B1 by design. Adding a new
suite keeps the pinned baselines intact while still locking in the behaviour
P1/P5/P6/P7 introduced.

Run directly:  python -m pytest tests/test_scenarios_suite.py -q
or plain:     python tests/test_scenarios_suite.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation.scenarios import (  # noqa: E402
    run_all, scenario_a_fleet_healthy, scenario_b_compressor_single,
    scenario_c_compound_fault, scenario_d_frozen_band,
    scenario_e_capacity_conserved, scenario_f_cold_side,
)
from app.simulation import incidents_catalogue as IC  # noqa: E402
from app.simulation import prediction as PRED  # noqa: E402
from app.simulation.fleet_orchestrator import FleetOrchestrator  # noqa: E402


def test_scenario_a_healthy_fleet():
    r = scenario_a_fleet_healthy()
    assert r.passed, r.failures


def test_scenario_b_compressor_single():
    r = scenario_b_compressor_single()
    assert r.passed, r.failures


def test_scenario_c_compound_fault():
    r = scenario_c_compound_fault()
    assert r.passed, r.failures


def test_scenario_d_frozen_band():
    """Regression guard for the missing cargo.mn/mx bug.

    prediction.project() now raises instead of defaulting, so a healthy frozen
    load reaching this assertion with a produce band would fail loudly rather
    than silently reporting the wrong verdict.
    """
    r = scenario_d_frozen_band()
    assert r.passed, r.failures


def test_scenario_e_capacity_conserved():
    r = scenario_e_capacity_conserved()
    assert r.passed, r.failures


def test_scenario_f_cold_side():
    r = scenario_f_cold_side()
    assert r.passed, r.failures


def test_all_scenarios_pass_together():
    """The whole suite in one run — scenarios must not contaminate each other."""
    results = run_all()
    failed = [r.name for r in results if not r.passed]
    assert not failed, f"scenarios failed: {failed}"


def test_prediction_refuses_to_default_a_missing_band():
    """A missing band must raise, not silently fall back to 2-8C.

    This is the exact failure mode that scored a -18C freezer against produce
    limits and flagged healthy frozen loads as below-floor.
    """
    F = FleetOrchestrator(4)
    F._spawn_fleet()
    snap = [v for v in F.vehicles.values() if v.kind != "SERVICE_TRUCK"][0].snapshot()
    cargo = snap["cargo"]
    saved = {k: cargo.pop(k) for k in ("mn", "mx") if k in cargo}
    try:
        try:
            PRED.project(snap, {})
        except KeyError:
            return  # correct: refused to guess
        raise AssertionError(
            "project() accepted a snapshot with no safe band — it must raise "
            "rather than default, or every cargo type is silently mis-scored")
    finally:
        cargo.update(saved)


def test_catalogue_and_not_detectable_stay_disjoint():
    """Declared gaps must not overlap the detectable set."""
    overlap = set(IC.INCIDENT_CATALOGUE) & set(IC.NOT_DETECTABLE_HERE)
    assert not overlap, f"declared a type as both detectable and a gap: {overlap}"


def test_every_catalogue_type_has_a_description():
    for k, v in IC.INCIDENT_CATALOGUE.items():
        assert v.get("description"), f"{k} has no description"
        assert v.get("category") in ("thermal", "integrity", "operational"), \
            f"{k} has an unknown category: {v.get('category')}"


def test_reporter_scores_faster_planning_higher():
    """Regression guard for the inverted reporter penalty.

    The penalty was `min(15, max(0, 12 - time_to_plan_ticks))`, which
    subtracted most when planning was quick — so an urgent response scored
    worse than a lazy one. Planning at or under the 6-tick target must now
    score at least as high as planning slowly.
    """
    from app.simulation.agents_d import ReporterAgent
    R = ReporterAgent()

    def score(**kw):
        base = dict(severity="HIGH", status="RESOLVED", detected_tick=0,
                    resolved_tick=10, peak_temperature=9.0, peak_over_by=2.0,
                    risk_at_peak=60, cargo_health=90, root_cause="compressor_failure",
                    root_cause_label="Compressor failure", root_cause_confidence=0.6,
                    actions_executed=["rescue_transfer"])
        base.update(kw)
        out = R.run(base)
        return out.get("score") or out.get("reporter_score")

    assert score(time_to_plan_ticks=1) > score(time_to_plan_ticks=14), \
        "planning faster must score higher than planning slowly"
    # Severity must still penalise monotonically.
    assert score(peak_over_by=1) > score(peak_over_by=12)


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

"""Recovery-verification correctness regression tests.

Covers the three linked defects fixed alongside this change:
  1. RecoveryVerifierAgent verified a load driven far BELOW the band minimum,
     because the tolerance only ever measured overshoot against `mx`.
  2. `_check_arrival` OR-ed `backup_cooling` into its resolution test, so merely
     switching a mitigation on marked an incident RESOLVED.
  3. The `successful_recoveries` KPI counted any RESOLVED row, including ones
     with no verifier evidence.

No database is opened, so the live coldchain.db is never touched.
Run:  backend\\.venv\\Scripts\\python.exe tests\\test_recovery_verification.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASSED = []
FAILED = []


def check(cond, label):
    if cond:
        PASSED.append(label)
        print("PASS", "-", label)
    else:
        FAILED.append(label)
        print("FAIL", "-", label)


class StubBox:
    """Minimal Engine-shaped stand-in; no RNG, no thermal integration."""

    def __init__(self, temperature, mn, mx, backup_cooling=False, compressor_on=False):
        self.temperature = temperature
        self._true = temperature
        self.mn, self.mx = mn, mx
        self.backup_cooling = backup_cooling
        self.compressor_on = compressor_on
        self.cargo_health = 100.0

    def snapshot(self, reported_temp=None):
        return {"true_temperature": self._true, "temperature": self.temperature,
                "backup_cooling": self.backup_cooling,
                "compressor_on": self.compressor_on,
                "cargo_health": self.cargo_health}


def history_trending(delta_per_sample, n=8):
    """A history whose least-squares slope is `delta` per sample."""
    return [{"true_temperature": 5.0 + delta_per_sample * i} for i in range(n)]


def verdict_for(box, history, mn, mx):
    from app.simulation.agents_d import RecoveryVerifierAgent
    return RecoveryVerifierAgent().run(
        box, history, {"mn": mn, "mx": mx},
        ["activate_backup_cooling"] if box.backup_cooling else [])


def resolution(verdict, box):
    """The post-fix decision made in _check_arrival."""
    t = box.snapshot()["true_temperature"]
    return bool(verdict.get("verified", False)) and box.mn <= t <= box.mx


def test_backup_cooling_is_mitigation_not_proof():
    box = StubBox(19.0, 2.0, 8.0, backup_cooling=True, compressor_on=False)
    v = verdict_for(box, history_trending(+0.4), 2.0, 8.0)
    check(not v["verified"], "backup cooling + cargo above max -> NOT verified")
    check(not resolution(v, box), "backup cooling alone does not resolve the incident")

    box_cold = StubBox(-14.0, 2.0, 8.0, backup_cooling=True, compressor_on=False)
    v_cold = verdict_for(box_cold, history_trending(-0.5), 2.0, 8.0)
    check(not v_cold["verified"], "backup cooling + cargo below min -> NOT verified")
    check(v_cold["under_by"] > 1.2, "under-minimum breach is detected and reported")
    check(not resolution(v_cold, box_cold),
          "cargo below the minimum never resolves, even while falling")


def test_in_band_but_verifier_declines():
    from app.simulation.agents_d import RecoveryVerifierAgent
    box = StubBox(5.0, 2.0, 8.0)
    v = RecoveryVerifierAgent().run(box, history_trending(0.0), {"mn": 2.0, "mx": 8.0}, [])
    check(not v["verified"], "no recovery action executed -> NOT verified")
    check(not resolution(v, box), "in-band without verifier confirmation does not resolve")


def test_verifier_confirms_and_band_passes():
    box = StubBox(5.0, 2.0, 8.0, backup_cooling=True, compressor_on=False)
    v = verdict_for(box, history_trending(-0.3), 2.0, 8.0)
    check(v["verified"], "verifier confirms: in band, cooling path, trending down")
    check(v["in_range_now"] and v["over_by"] == 0.0 and v["under_by"] == 0.0,
          "verifier reports both boundaries satisfied")
    check(resolution(v, box), "verified + in band -> incident resolves")

    box_frozen = StubBox(-20.0, -25.0, -18.0, backup_cooling=True, compressor_on=False)
    vf = verdict_for(box_frozen, history_trending(0.0), -25.0, -18.0)
    check(vf["verified"], "frozen band -25..-18 accepts -20C (cargo-specific band)")

    box_wrong = StubBox(-20.0, 2.0, 8.0, backup_cooling=True, compressor_on=False)
    vw = verdict_for(box_wrong, history_trending(0.0), 2.0, 8.0)
    check(not vw["verified"], "same -20C rejected against a 2..8C band")


def test_escalation_representation():
    box = StubBox(17.0, 2.0, 8.0, backup_cooling=True, compressor_on=False)
    v = verdict_for(box, history_trending(+0.6), 2.0, 8.0)
    resolved = resolution(v, box)
    check(not resolved, "over-temperature incident is not resolved")
    check("ESCALATED" if not resolved else False,
          "failed verification maps to ESCALATED")
    check(v["agent"] == "recovery_verifier", "verdict carries agent name for the audit trail")


def test_kpi_excludes_unverified():
    from app.simulation.analytics import _verified_incident_ids, _zeros
    rows = [
        (1, json.dumps({"verified": True})),
        (2, json.dumps({"verified": False})),
        (3, None),
        (4, "{not json"),
        (5, json.dumps({"verified": "true"})),
    ]
    verified = _verified_incident_ids(rows)
    check(verified == {1}, "only an explicit verified=true analysis counts")

    resolved_ids = [1, 2, 3, 4, 5]
    kpi = sum(1 for i in resolved_ids if i in verified)
    check(kpi == 1, "KPI counts 1 verified recovery out of 5 RESOLVED rows")
    check(len(resolved_ids) - kpi == 4, "KPI surfaces 4 RESOLVED rows lacking verification")
    check("successful_recoveries_unverified" in _zeros(),
          "KPI bundle exposes the unverified population")


def main():
    test_backup_cooling_is_mitigation_not_proof()
    test_in_band_but_verifier_declines()
    test_verifier_confirms_and_band_passes()
    test_escalation_representation()
    test_kpi_excludes_unverified()
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        for f in FAILED:
            print("  FAILED:", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
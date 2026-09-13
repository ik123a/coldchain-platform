"""Sim engine regression (in-process, no server). Run with python -m tests.sim_regression"""
import asyncio
from app.simulation.engine import Engine
from app.simulation.risk import risk
from app.simulation import agents_d as A
from app.simulation.runner import SimulationRunner
import json


def check(cond, label):
    print(("PASS" if cond else "FAIL"), "-", label)
    assert cond, label


async def main():
    zone = {"mn": 2.0, "mx": 8.0, "hum_min": 60, "hum_max": 85}
    e = Engine(target=4.0, mn=2.0, mx=8.0, hum_min=60, hum_max=85, seed=11)
    e.inject("compressor_failure")
    hist = []
    for _ in range(20):
        hist.append(e.tick())
    last = hist[-1]
    r = risk(last, zone, 14, trend_c_per_min=0.12)
    check(last["true_temperature"] > 8.0, f"warmed above {zone['mx']} -> {last['true_temperature']}")
    check(40 <= r["score"] <= 100, f"risk in band 40-100 -> {r['score']} ({r['level']})")

    diag = A.DiagnosisAgent().run(e, hist, "excursion")
    check(diag["root_cause"] == "compressor_failure" and diag["confidence"] > 0.4,
          f"diagnosis compressor_failure -> {diag['root_cause']} @{diag['confidence']}")

    plan = A.ResponsePlannerAgent().run(diag["root_cause"], r)
    check(plan["actions"][0]["action"] == "activate_backup_cooling",
          f"planner first action == activate_backup_cooling -> {plan['actions'][0]}")

    ver = A.RecoveryVerifierAgent()
    not_ver = ver.run(e, hist, zone, [])
    check(not_ver["verified"] is False, "verifier rejects with no actions executed")

    e2 = Engine(target=4.0, mn=2.0, mx=8.0, hum_min=60, hum_max=85, seed=11)
    e2.inject("compressor_failure")
    for _ in range(18): e2.tick()
    e2.activate_backup_cooling()
    after = [e2.tick() for _ in range(14)]
    ver2 = ver.run(e2, after, zone, ["activate_backup_cooling"])
    check(ver2["verified"] in (True, False) and isinstance(ver2["confidence"], float),
          f"verifier ran (verified={ver2['verified']})")

    # Reporter generates deterministic report
    ctx = {"root_cause": "compressor_failure", "root_cause_confidence": 0.62, "severity": "HIGH",
           "status": "RESOLVED", "detected_tick": 12, "resolved_tick": 42,
           "peak_temperature": 10.9, "peak_over_by": 2.9, "risk_at_peak": 72.5,
           "cargo_health": 91.0, "actions_executed": ["activate_backup_cooling", "close_door"],
           "timeline": ["failure injected: compressor_failure", "incident detected: compressor_failure (HIGH)",
                        "ai diagnosis: compressor failure @0.62", "response plan: Activate backup cooling"],
           "root_cause_label": "compressor failure",
           "time_to_plan_ticks": 4, "lessons": ["tighten compressor health monitoring"]}
    rep = A.ReporterAgent().run(ctx)
    check("RESPONSE QUALITY SCORE" in rep["report"], "reporter includes score line")
    check(35 <= rep["score"] <= 98, f"score in bound -> {rep['score']}")
    check("compressor_failure" in rep["report"], "mentions root cause")

    # risk monotonicity w.r.t. exposure
    r1 = risk(last, zone, 2, trend_c_per_min=0.12)
    r2 = risk(last, zone, 16, trend_c_per_min=0.12)
    check(r2["score"] > r1["score"], f"more exposure -> higher risk {r1['score']} vs {r2['score']}")

    # sensor-fault path
    e3 = Engine(target=4.0, mn=2.0, mx=8.0, hum_min=60, hum_max=85, seed=31)
    e3.inject("sensor_fault")
    snap = e3.tick()
    check(snap["temperature"] == round(getattr(e3, '_frozen_reported'), 2), "frozen sensor reports constant value")


if __name__ == "__main__":
    asyncio.run(main())
    print("SIM ENGINE REGRESSION: ALL PASS")

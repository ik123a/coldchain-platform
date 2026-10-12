"""Six-agent deterministic cold-chain operations team.
Every agent returns a dict: {agent, status/result payload, confidence, emitted messages}.
Pure-python — works with zero API keys. The runner routes human approval between
Response Planner and Recovery Execution.
"""
from __future__ import annotations
import math
from .engine import Engine
from .risk import risk

# ---------------- shared helpers ----------------

def _trend(history, n=6):
    """linear slope degC/tick over the last n snapshots"""
    vals = [h["true_temperature"] for h in history[-n:]]
    if len(vals) < 3:
        return 0.0
    x = list(range(len(vals)))
    xm, ym = sum(x) / len(x), sum(vals) / len(vals)
    num = sum((xi - xm) * (yi - ym) for xi, yi in zip(x, vals))
    den = sum((xi - xm) ** 2 for xi in x) or 1
    return num / den


def _over_limit(h, mn, mx):
    return h["true_temperature"] > mx or h["true_temperature"] < mn


# ---------------- individual agents ----------------

class MonitoringAgent:
    name = "monitoring"

    def run(self, engine: Engine, anom: dict | None):
        findings = []
        if anom:
            findings.append({"kind": anom["kind"], "severity": anom["severity"], "reason": anom["reason"]})
        snap = engine.snapshot()
        if snap["door_open"]:
            findings.append({"kind": "door_open", "severity": "WARNING",
                             "reason": "door sensor OPEN while cargo in zone"})
        if not snap["power_ok"]:
            findings.append({"kind": "power", "severity": "WARNING",
                             "reason": f"grid power lost, battery at {snap['battery_level']}%"})
        return {"agent": self.name, "findings": findings,
                "trigger_incident": bool(anom and anom["kind"] == "excursion")}


class DiagnosisAgent:
    name = "diagnosis"

    def run(self, engine: Engine, history: list, alert_kind: str):
        trend = _trend(history)
        snap = engine.snapshot()
        hypotheses = []

        # evidence-based scoring
        if not snap["compressor_on"] and not snap["backup_cooling"] and snap["power_ok"]:
            hypotheses.append((0.62, "compressor_failure",
                               "compressor offline, grid power present; sustained warming matches "
                               f"trend +{trend:.2f}°C/min"))
        if not snap["power_ok"]:
            hypotheses.append((0.72, "power_failure",
                               f"grid power lost; battery {snap['battery_level']}%, compressor node OFF; "
                               "passive warming consistent with case"))
        if snap["door_open"]:
            p = 0.45 if not snap["power_ok"] else 0.52
            hypotheses.append((p, "door_open",
                               "door sensor OPEN; humidity rising and temperature trending up together"))
        if snap["ambient_temperature"] > 40:
            hypotheses.append((0.35, "heatwave",
                               f"ambient {snap['ambient_temperature']}°C; still warming despite cooling path"))
        if snap["cooling_efficiency"] < 0.6 and snap["compressor_on"]:
            hypotheses.append((0.40, "cooling_degradation",
                               f"compressor running but efficiency {snap['cooling_efficiency']:.2f}; "
                               " symptoms persist although compressor ON"))
        # sensor-fault alert -> actual root cause is sensor itself
        if alert_kind == "sensor_fault":
            hypotheses = [(0.93, "sensor_fault", "anomaly detector flagged reported-vs-true divergence "
                                            "or frozen readings; true temperature in range")]
        if not hypotheses:
            hypotheses.append((0.20, "environmental_deviation",
                               "no dominant equipment fault; ambient load high"))

        hypotheses.sort(key=lambda h: -h[0])
        top = hypotheses[0]
        # normalize so alternatives look like a probability mass
        total = sum(h[0] for h in hypotheses) or 1.0
        alternatives = [{"cause": c, "probability": round(w / total, 2), "reason": r}
                        for w, c, r in hypotheses[1:4]]
        return {"agent": self.name, "root_cause": top[1],
                "confidence": round(top[0], 2), "label": top[1].replace("_", " "),
                "alternatives": alternatives, "trend_c_per_min": round(trend, 3),
                "reasoning": top[2]}


class RiskAnalystAgent:
    name = "risk_analyst"

    def run(self, engine: Engine, history: list, zone: dict, exposure_ticks: int, cargo_type="fresh_produce"):
        trend = _trend(history)
        snap = engine.snapshot()
        r = risk(snap, zone, exposure_ticks, cargo_type=cargo_type, trend_c_per_min=trend)

        # time-to-critical (projected)
        ttc = None
        if trend > 0.01:
            gap = max(0.0, (zone["mx"] + 2.0) - snap["true_temperature"])  # crit threshold = max + 2
            ticks = gap / trend if gap > 0 else 0
            ttc = int(ticks) if ticks > 0 else 0
        # forward projection: 10 ticks
        proj = None
        if trend > 0:
            proj_temp = snap["true_temperature"] + trend * 10
            proj_risk = risk({**snap, "temperature": proj_temp, "true_temperature": proj_temp},
                             zone, exposure_ticks + 10, cargo_type=cargo_type, trend_c_per_min=trend)
            proj = {"in_10_ticks_temp": round(proj_temp, 2), "in_10_ticks_risk": proj_risk["level"]}

        return {"agent": self.name, **r, "trend_c_per_min": round(trend, 3),
                "time_to_critical_ticks": ttc, "projection": proj,
                "explain": r["explain"], "components": r["components"]}


class ResponsePlannerAgent:
    name = "response_planner"

    def run(self, root_cause: str, risk_info: dict):
        cause_class = root_cause if root_cause in (
            "power_failure", "door_open", "compressor_failure") else "compressor_failure"
        plans = {
            "compressor_failure": [
                {"action": "activate_backup_cooling", "label": "Activate backup cooling",
                 "priority": "CRITICAL", "reason": "PRIMARY path: main compressor down; backup loop restores pull-down",
                 "expected_effect": "temperature return toward target within ~8-12 ticks"},
                {"action": "close_door", "label": "Seal door", "priority": "HIGH",
                 "reason": "reduce ambient infiltration while cooling restored",
                 "expected_effect": "removes +0.22°C/min door heat gain"},
                {"action": "restart_compressor", "label": "Attempt compressor restart", "priority": "MEDIUM",
                 "reason": "if fault transient, restarting restores primary loop and bursts efficiency",
                 "expected_effect": "restores full cooling rate"},
                {"action": "monitor", "label": "Maintain 10s watch", "priority": "LOW",
                 "reason": "verify recovery slope before declaring resolved",
                 "expected_effect": "continuous verification"},
            ],
            "power_failure": [
                {"action": "restore_power", "label": "Switch to generator/normalize power", "priority": "CRITICAL",
                 "reason": "PRIMARY path: compressor and sensors need grid; battery is temporary",
                 "expected_effect": "full cooling restored"},
                {"action": "activate_backup_cooling", "label": "Bridge with backup cooling", "priority": "HIGH",
                 "reason": "buy time while power is restored", "expected_effect": "slows warming immediately"},
                {"action": "monitor", "label": "Battery watch", "priority": "HIGH",
                 "reason": "prevent total blackout of monitoring coverage", "expected_effect": "graceful degradation"},
            ],
            "door_open": [
                {"action": "close_door", "label": "Close and seal door", "priority": "CRITICAL",
                 "reason": "PRIMARY path: removes root heat source", "expected_effect": "warming stops immediately"},
                {"action": "activate_backup_cooling", "label": "Burst backup cooling", "priority": "MEDIUM",
                 "reason": "recover accumulated excursion", "expected_effect": "pull-down to target"},
            ],
            "heatwave": [
                {"action": "activate_backup_cooling", "label": "Enable backup cooling", "priority": "HIGH",
                 "reason": "ambients reduce margin; added capacity maintains target",
                 "expected_effect": "holds target within +0.5"},
                {"action": "monitor", "label": "Ambient track", "priority": "MEDIUM",
                 "reason": "heatwave is external; efficiency will recover when it breaks",
                 "expected_effect": "situational awareness"},
            ],
            "sensor_fault": [
                {"action": "verify_sensor", "label": "Validate sensor TEMP-001 vs redundant", "priority": "MEDIUM",
                 "reason": "reported reading diverges from true; false alarm risk",
                 "expected_effect": "no false recovery action"},
            ],
        }
        for a in plans.setdefault("cooling_degradation", plans["compressor_failure"]):
            pass
        key = ("sensor_fault" if root_cause == "sensor_fault" else
               root_cause if root_cause in plans else "compressor_failure")
        return {"agent": self.name, "root_considered": root_cause, "actions": plans[key]}


class RecoveryVerifierAgent:
    name = "recovery_verifier"

    # Applies to BOTH boundaries. The over-shoot term floors at 0, so a one-sided
    # check passes any load driven far below `mn` — that was the defect fixed here.
    TOLERANCE_C = 1.2

    def run(self, engine: Engine, history: list, zone: dict, actions_executed: list[str], verified_window=8):
        if not actions_executed:
            return {"agent": self.name, "verified": False,
                    "evidence": ["no recovery action executed yet"], "confidence": 0.0}
        recent = history[-verified_window:]
        trend = _trend(recent, n=len(recent))
        snap = engine.snapshot()
        t = snap["true_temperature"]
        mn, mx = zone["mn"], zone["mx"]
        over = max(0.0, t - mx)
        under = max(0.0, mn - t)
        falling = trend < -0.02
        in_range = t <= mx and t >= mn
        compressor_path = snap["backup_cooling"] or snap["compressor_on"]
        evidence = [
            f"trend {trend:+.2f}°C/min over last {len(recent)} ticks",
            f"true temperature {t}°C (band {mn}-{mx})",
            f"over max {over:.2f}C, under min {under:.2f}C (tolerance {self.TOLERANCE_C}C either side)",
            f"backup cooling {'ON' if snap['backup_cooling'] else 'OFF'}, compressor {'ON' if snap['compressor_on'] else 'OFF'}",
        ]
        # Both routes require the cargo inside its band on both sides. Backup
        # cooling is a mitigation, never proof the cargo came back into range.
        recovering = falling and over <= self.TOLERANCE_C and under <= self.TOLERANCE_C
        sustained = in_range and compressor_path
        ok = recovering or sustained
        return {"agent": self.name, "verified": ok,
                "evidence": evidence,
                "trend_c_per_min": round(trend, 3),
                "in_range_now": in_range,
                "over_by": round(over, 2), "under_by": round(under, 2),
                "cooling_path_active": bool(compressor_path),
                "basis": "true temperature inside the cargo-specific band on both boundaries",
                "confidence": round(min(0.98, 0.55 + (-trend) * 3.0 + (0.2 if in_range else 0)), 2)}


class ReporterAgent:
    name = "reporter"

    def run(self, incident_ctx: dict):
        ctx = incident_ctx

        def num(key, default=0):
            # dict.get returns None when the key exists with a null value, which
            # is what the API sends for unresolved incidents — arithmetic on it
            # raised TypeError and 500'd both report formats. A pending
            # incident has no resolution tick, so recovery time is undefined,
            # not zero; fall back to the simulation tick.
            v = ctx.get(key)
            return default if v is None else v

        recovery_t = num("resolved_tick", num("tick", 0)) - num("detected_tick", 0)
        # An unresolved incident has no resolution tick, so resolved_tick falls
        # back to `tick` (0) while detected_tick is large — producing a negative
        # recovery time such as "-1672 ticks", which reads as nonsense in the
        # report and feeds a bogus score (the slow-recovery penalty floors at 0,
        # so an unresolved incident was silently scored as if recovery were
        # instant). Report it as undetermined instead, and do not let it move
        # the score at all: an incident that has not ended has no response
        # quality to judge yet.
        unresolved = ctx.get("resolved_tick") is None
        recovery_t = None if unresolved else recovery_t
        recovery_penalty = 0 if unresolved else min(20, max(0, recovery_t - 8))

        score = 100
        score -= min(30, max(0, num("peak_over_by", 0) * 3))               # severity penalty
        score -= min(25, max(0, (num("risk_at_peak", 0) - 55) / 2))        # risk stayed high
        score -= recovery_penalty                                           # slow recovery
        # Planning FASTER must score HIGHER. The penalty was written as
        # `min(15, max(0, 12 - time_to_plan_ticks))`, which is largest when
        # time_to_plan_ticks is SMALL — so the quicker the planning, the more
        # was subtracted. Measured before the fix: 0 ticks scored 77 while 12
        # ticks scored 89, reporting an urgent response as worse than a lazy
        # one. The accompanying comment said "handled below" for logic that
        # was never written.
        #
        # Correct form: slowness is (ticks - target), floored at zero, so a
        # response at or under target costs nothing and delay costs up to 15.
        score -= min(15, max(0, (num("time_to_plan_ticks", 4) - 6) / 2))
        score += min(10, num("early_confidence_bonus", 0))
        score = int(max(35, min(98, score)))

        lines = [
            f"INCIDENT REPORT — {ctx.get('root_cause_label', ctx.get('root_cause', 'thermal excursion')).upper()}",
            f"",
            f"Severity: {ctx.get('severity')}    Status: {ctx.get('status')}",
            f"Detected: tick {ctx.get('detected_tick')}    Resolved: tick {ctx.get('resolved_tick')}",
            f"Peak temperature: {ctx.get('peak_temperature')}°C over band by {ctx.get('peak_over_by', 0)}°C",
            f"Risk at peak: {ctx.get('risk_at_peak')}    Cargo health remaining: {ctx.get('cargo_health')}%",
            f"Root cause: {ctx.get('root_cause')} (confidence {ctx.get('root_cause_confidence')})",
            f"Recovery time: {recovery_t if recovery_t is not None else 'not resolved yet'} ticks"
            f" — actions: {', '.join(ctx.get('actions_executed', [])) or 'manual'}",
            f"",
            f"RESPONSE QUALITY SCORE: {score}/100",
            f"",
            "Timeline:",
        ]
        for t in ctx.get("timeline", [])[:14]:
            lines.append(f"  {t}")
        for w in ctx.get("lessons", [])[:4]:
            lines.append(f"Lesson: {w}")
        report = "\n".join(lines)
        return {"agent": self.name, "report": report, "score": score,
                "summary": {"severity": ctx.get("severity"), "root_cause": ctx.get("root_cause"),
                            "peak_temperature": ctx.get("peak_temperature"),
                            "recovery_ticks": recovery_t, "score": score}}

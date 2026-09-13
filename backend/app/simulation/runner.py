"""SimulationRunner — per-simulation asyncio loop.

Drives: Engine.tick() -> persist reading -> anomaly detect -> agent orchestration ->
recover (human-approved) -> verify -> resolve -> report -> broadcast WS events.
"""
from __future__ import annotations
import asyncio, json, logging
from datetime import datetime
from sqlalchemy import select
from ..database.engine import SessionLocal
from ..models.entities import (SensorReading, Incident, AIAnalysis, RecommendedAction, Alert, Simulation)
from .engine import Engine, CAUSES
from .risk import risk as risk_score_fn
from .anomaly import AnomalyDetector
from . import agents_d as A

log = logging.getLogger("sim-eng")


class Broadcast:
    """In-process broadcast hub: simulation event -> all websocket subscribers."""
    def __init__(self):
        self.subs = set()

    def add(self, q): self.subs.add(q)
    def discard(self, q): self.subs.discard(q)
    async def emit(self, sim_id: int, etype: str, payload: dict):
        msg = json.dumps({"type": etype, "simulation_id": sim_id, "ts": datetime.utcnow().isoformat(), **payload})
        for q in list(self.subs):
            try:
                q.put_nowait(msg)
            except Exception:
                self.discard(q)


BROADCAST = Broadcast()
RUNNERS: dict[int, "SimulationRunner"] = {}
_PENDING: dict[int, set[str]] = {}   # sim_id -> action ids claimed by operator (execute when plan exists)


PENDING_EXECUTE = _PENDING

ACTIVE_HANDLER = {}

async def mark_action_claimed(sim_id: int, action_key: str):
    _PENDING.setdefault(sim_id, set()).add(action_key)


class Timeline:
    def __init__(self):
        self.items: list[str] = []

    def add(self, label, detail=""):
        self.items.append(f"{label}: {detail}" if detail else label)


class SimulationRunner:
    def __init__(self, sim_id: int, engine: Engine, speed: int = 10, tick_seconds: int = 1,
                 zone: dict | None = None, cargo_type: str = "fresh_produce"):
        self.sim_id = sim_id
        self.engine = engine
        self.speed = speed                  # simulated minutes per tick-second
        self.tick_seconds = tick_seconds    # wall seconds per engine tick
        self.zone = zone or {"mn": engine.mn, "mx": engine.mx, "hum_min": engine.hum_min, "hum_max": engine.hum_max}
        self.cargo_type = cargo_type
        self.tick_n = 0
        self.status = "RUNNING"             # RUNNING / PAUSED / COMPLETED
        self.history: list[dict] = []
        self.detector = AnomalyDetector()
        self.agents = {k.name: k for k in (A.MonitoringAgent(), A.DiagnosisAgent(), A.RiskAnalystAgent(),
                                           A.ResponsePlannerAgent(), A.RecoveryVerifierAgent(), A.ReporterAgent())}
        self.exposure_ticks = 0
        self.peak_temp = engine.target
        self.incident_db_id: int | None = None
        self.incident_state: dict | None = None
        self._task: asyncio.Task | None = None
        self.timeline = Timeline()

    # -------- public controls --------
    def pause(self): self.status = "PAUSED"
    def resume(self):
        if self.status in ("PAUSED", "RUNNING"):
            self.status = "RUNNING"
            self._ensure_task()
    def stop(self):
        self.status = "COMPLETED"
        if self._task: self._task.cancel()

    def inject(self, cause: str) -> bool:
        if cause not in CAUSES: return False
        self.engine.inject(cause)
        self.timeline.add("failure injected", cause)
        return True

    def set_speed(self, s: int):
        self.speed = max(1, min(100, int(s)))

    # -------- agent event wrapper --------
    async def _agent_emit(self, agent: str, kind: str, payload: dict):
        await BROADCAST.emit(self.sim_id, "agent_event", {"agent": agent, "kind": kind, **payload})

    async def _alert(self, text: str, severity="INFO", etype="alert"):
        async with SessionLocal() as s:
            a = Alert(simulation_id=self.sim_id, type=etype, severity=severity, message=text, tick=self.tick_n)
            s.add(a); await s.commit()
        await BROADCAST.emit(self.sim_id, "alert", {"severity": severity, "message": text, "tick": self.tick_n})

    # -------- incident lifecycle --------
    async def _create_incident(self, anom: dict, anom_kind: str):
        # deterministic root-cause mapping from LOW-LEVEL state (injected scenario),
        # never read from UI. If anom_kind is sensor_fault, supersede.
        e = self.engine
        base = (anom_kind if anom_kind == "sensor_fault" else
                "power_failure" if not e.power_ok else
                "door_open" if (e.door_open and e.scenario == "door_open") else
                "power_failure" if e.scenario == "power_failure" else
                "compressor_failure" if not e.compressor_on or e.scenario == "compressor_failure" else
                "heatwave" if e.scenario == "heatwave" else
                "cooling_degradation" if e.scenario == "cooling_degradation" else
                "multiple_failure" if e.scenario == "multiple_failure" else
                "environmental_deviation")
        if anom_kind == "sensor_fault":
            base = "sensor_fault"
        ctx = {"root_cause": base, "detected_tick": self.tick_n, "detected_at": datetime.utcnow(),
               "severity": anom["severity"], "status": "DETECTED",
               "alert_kind": anom_kind, "timeline": [], "actions_executed": [],
               "peak_temperature": self.peak_temp, "resolved_tick": None}
        self.incident_state = ctx
        async with SessionLocal() as s:
            inc = Incident(simulation_id=self.sim_id,
                           type=("sensor_fault" if base == "sensor_fault" else "temperature_excursion"),
                           severity=anom["severity"], status="DETECTED",
                           detected_tick=self.tick_n, root_cause=base,
                           description=anom["reason"], peak_temperature=self.peak_temp)
            s.add(inc)
            await s.commit()
            self.incident_db_id = inc.id
        self.timeline.add("incident detected", f"{base} ({anom['severity']})")
        await self._alert(f"Incident detected: {base} — {anom['reason']}", anom["severity"], "incident_detected")
        await self._agent_emit("monitoring", "incident_detected", {"root_cause": base, "severity": anom["severity"]})
        await self._run_diagnosis()

    async def _run_diagnosis(self):
        if not self.incident_state: return
        d = self.agents[A.DiagnosisAgent.name].run(self.engine, self.history, self.incident_state["alert_kind"])
        self.incident_state["root_cause"] = d["root_cause"]
        self.incident_state["root_cause_confidence"] = d["confidence"]
        self.incident_state["diag"] = d
        label = d.get("label", d["root_cause"])
        async with SessionLocal() as s:
            s.add(AIAnalysis(incident_id=self.incident_db_id, agent_name="diagnosis",
                            analysis=json.dumps({k: d[k] for k in ("root_cause", "confidence", "alternatives", "reasoning", "label", "trend_c_per_min")}),
                            confidence=d["confidence"]))
            if self.incident_db_id:
                inc = await s.get(Incident, self.incident_db_id)
                if inc:
                    inc.root_cause = d["root_cause"]; inc.root_cause_confidence = d["confidence"]; inc.status = "DIAGNOSED"
            if self.incident_state.get("root_cause") == "sensor_fault":
                pass  # let's not clutter the incident severity, but persist
            await s.commit()
        await self._agent_emit("diagnosis", "diagnosis_complete",
                               {"root_cause": d["root_cause"], "confidence": d["confidence"],
                                "alternatives": d["alternatives"], "reasoning": d["reasoning"],
                                "label": label})
        self.timeline.add("ai diagnosis", f"{label} @{d['confidence']}")
        await self._run_risk()

    async def _run_risk(self):
        if not self.incident_state: return
        r = self.agents[A.RiskAnalystAgent.name].run(self.engine, self.history, self.zone,
                                                            self.exposure_ticks, self.cargo_type)
        self.incident_state["risk"] = r
        async with SessionLocal() as s:
            s.add(AIAnalysis(incident_id=self.incident_db_id, agent_name="risk",
                            analysis=json.dumps({k: r[k] for k in ("score", "level", "components", "trend_c_per_min",
                                                                    "time_to_critical_ticks", "projection", "explain")}),
                            confidence=0.95))
            await s.commit()
        self.timeline.add("risk analysis", f"{r['level']} {r['score']}/100")
        await self._agent_emit("risk_analyst", "risk_assessed",
                               {"score": r["score"], "level": r["level"], "components": r["components"],
                                "time_to_critical_ticks": r["time_to_critical_ticks"], "projection": r["projection"]})
        await self._run_planner()

    async def _run_planner(self):
        if not self.incident_state: return
        plan = self.agents[A.ResponsePlannerAgent.name].run(self.incident_state["root_cause"], self.incident_state["risk"])
        acts = self.incident_state.setdefault("actions", plan["actions"])
        claimed = _PENDING.get(self.sim_id, set())
        async with SessionLocal() as s:
            for a in plan["actions"]:
                s.add(RecommendedAction(incident_id=self.incident_db_id, action=a["action"],
                                       label=a["label"], priority=a["priority"], reason=a["reason"],
                                       expected_effect=a["expected_effect"]),
                )
            if self.incident_db_id:
                inc = await s.get(Incident, self.incident_db_id)
                if inc: inc.status = "PLANNED"
            await s.commit()
        self.timeline.add("response plan", ", ".join(a["label"] for a in plan["actions"]))
        await self._agent_emit("response_planner", "plan_ready",
                               {"root_considered": plan["root_considered"], "actions": plan["actions"]})
        # execute operator-claimed actions immediately after plan exists
        if claimed:
            for key in list(claimed):
                if any(a["action"] == key for a in plan["actions"]):
                    claimed.discard(key)
                    await self.execute_action(key)

    # -------- operator action execution --------
    async def execute_action(self, action_key: str):
        e = self.engine
        applied = False
        if action_key == "activate_backup_cooling": applied = e.activate_backup_cooling()
        elif action_key == "close_door": e.close_door(); applied = True
        elif action_key == "restart_compressor": applied = e.restart_compressor()
        elif action_key == "restore_power": e.restore_power(); applied = True
        elif action_key == "transfer_cargo":
            e.cargo_health = max(20.0, e.cargo_health - 5.0)   # transfer cost
            applied = True
        elif action_key == "monitor": applied = True
        elif action_key == "verify_sensor": applied = True
        if not applied:
            await self._alert(f"Action '{action_key}' could not be applied (state preconditions unmet)", "WARNING", "action_failed")
            return {"applied": False, "reason": "preconditions unmet"}
        self.incident_state.setdefault("actions_executed", []).append(action_key)
        async with SessionLocal() as s:
            res = await s.execute(select(RecommendedAction).where(RecommendedAction.incident_id == self.incident_db_id,
                                                                  RecommendedAction.action == action_key))
            for ra in res.scalars().all():
                ra.status = "EXECUTED"; ra.executed_at = datetime.utcnow()
            await s.commit()
        self.timeline.add("action executed", action_key)
        await self._alert(f"Recovery action executed: {action_key}", "INFO", "action_executed")
        await self._agent_emit("response_planner", "action_executed", {"action": action_key})
        if self.incident_db_id:
            async with SessionLocal() as s:
                inc = await s.get(Incident, self.incident_db_id)
                if inc and inc.status in ("PLANNED", "DIAGNOSED", "DETECTED"):
                    inc.status = "RECOVERING"
        return {"applied": True, "action": action_key}

    async def _verify_recovery(self):
        if not self.incident_state: return
        v = self.agents[A.RecoveryVerifierAgent.name].run(self.engine, self.history, self.zone,
                                                                  self.incident_state["actions_executed"])
        await self._agent_emit("recovery_verifier", "verification",
                               {"verified": v["verified"], "evidence": v["evidence"],
                                "confidence": v["confidence"]})
        if not v["verified"]:
            self.timeline.add("verification failed", "waiting — conditions not yet met")
            return

        # RESOLVE
        st = self.incident_state
        st["resolved_tick"] = self.tick_n
        st["resolved_at"] = datetime.utcnow()
        st["status"] = "RESOLVED"
        st["peak_temperature"] = self.peak_temp
        st["risk_at_peak"] = st.get("risk", {}).get("score", 0)
        st["cargo_health"] = self.engine.cargo_health
        st["peak_over_by"] = round(max(0.0, self.peak_temp - self.zone["mx"]), 2)
        st["timeline"] = list(self.timeline.items)
        st["root_cause_label"] = st.get("diag", {}).get("label", st["root_cause"])
        st["score_bonus"] = 0.0 if st.get("alert_kind") == "sensor_fault" else 6.0
        st["time_to_plan_ticks"] = len([x for x in self.timeline.items if "action executed" in x])

        # lesson rule-of-thumb additions
        if st["root_cause"] == "compressor_failure":
            st["lessons"] = ["router to auto-activate backup within 2 ticks of compressor offline signal",
                             "periodic compressor health self-test at low-load windows",
                             "review door-open policy while cooling offline"]
        elif st["root_cause"] == "power_failure":
            st["lessons"] = ["monitor battery SOC during transfers",
                             "rehearse generator switchover quarterly"]
        else:
            st["lessons"] = ["insert advisory warning at ambient > 35°C", "practice door discipline drills"]

        rep = A.ReporterAgent().run(st)
        st["final_report"] = rep["report"]
        st["response_score"] = rep["score"]

        async with SessionLocal() as s:
            if self.incident_db_id:
                inc = await s.get(Incident, self.incident_db_id)
                if inc:
                    inc.status = "RESOLVED"; inc.resolved_at = datetime.utcnow(); inc.resolved_tick = self.tick_n
            s.add(AIAnalysis(incident_id=self.incident_db_id, agent_name="reporter",
                            analysis=json.dumps({"report": rep["report"], "score": rep["score"],
                                                 "summary": rep["summary"]})))
            await s.commit()
        self.timeline.add("incident resolved", f"root={st['root_cause']}, score={rep['score']}")
        await self._alert(f"Incident resolved: {st['root_cause']} — quality score {rep['score']}/100", "INFO", "recovery_verified")
        await self._agent_emit("recovery_verifier", "recovery_verified",
                               {"verified": True, "score": rep["score"], "evidence": v["evidence"],
                                "peak_temperature": st["peak_temperature"],
                                "resolved_tick": st["resolved_tick"],
                                "root_cause": st["root_cause"]})
        await self._agent_emit("reporter", "report_ready",
                               {"score": rep["score"], "summary": rep["summary"], "report": rep["report"]})
        self.incident_state = None   # allow next incident, clear state

    # -------- main loop --------
    def _ensure_task(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            log.info("runner %d loop started", self.sim_id)

    async def _loop(self):
        try:
            while self.status == "RUNNING":
                await asyncio.sleep(self.tick_seconds)
                if self.status != "RUNNING":
                    continue
                snapshot = self.engine.tick()
                self.tick_n += 1
                self.history.append(snapshot)
                if len(self.history) > 600:
                    self.history = self.history[-600:]
                true_t = snapshot["true_temperature"]

                # risk score (continuous)
                from .risk import risk as risk_fn
                r = risk_fn(snapshot, self.zone, self.exposure_ticks, cargo_type=self.cargo_type,
                            trend_c_per_min=0.0)
                self._risk_state = r

                over = max(0.0, true_t - self.zone["mx"])
                under = max(0.0, self.zone["mn"] - true_t)
                self.exposure_ticks = (self.exposure_ticks + 1) if (over > 0 or under > 0) else 0
                self.peak_temp = max(self.peak_temp, true_t)

                # persist reading
                async with SessionLocal() as s:
                    s.add(SensorReading(simulation_id=self.sim_id, tick=self.tick_n,
                                       temperature=snapshot["temperature"], humidity=snapshot["humidity"],
                                       ambient_temperature=snapshot["ambient_temperature"],
                                       door_open=snapshot["door_open"], compressor_on=snapshot["compressor_on"],
                                       backup_cooling=snapshot["backup_cooling"], power_ok=snapshot["power_ok"],
                                       battery_level=snapshot["battery_level"],
                                       cargo_health=snapshot["cargo_health"],
                                       risk_score=r["score"]))
                    await s.commit()

                # anomaly + monitoring agent
                anom = self.detector.update(self.engine)
                mon = self.agents[A.MonitoringAgent.name].run(self.engine, anom)

                # broadcast reading
                await BROADCAST.emit(self.sim_id, "sensor_update",
                                     {"tick": self.tick_n, **snapshot,
                                      "risk_score": r["score"], "risk_level": r["level"],
                                      "exposure_ticks": self.exposure_ticks,
                                      "peak_temperature": self.peak_temp,
                                      "zone": self.zone, "cargo_type": self.cargo_type,
                                      "incident_status": (self.incident_state or {}).get("status")})

                if mon["findings"]:
                    for f in mon["findings"]:
                        if f["severity"] in ("WARNING", "INFO"):
                            pass

                # incident lifecycle
                if anom and anom["kind"] == "excursion" and not self.incident_state:
                    sev = anom["severity"]
                    if true_t - self.zone["mx"] > 2.5 or self.zone["mn"] - true_t > 2.5:
                        sev = "CRITICAL"
                    await self._create_incident({**anom, "severity": sev}, anom["kind"])
                elif anom and anom["kind"] == "sensor_fault":
                    # raise alert-style incident once
                    if not self.incident_state or self.incident_state.get("alert_kind") != "sensor_fault":
                        await self._create_incident({**anom, "severity": "MEDIUM"}, "sensor_fault")

                # after actions were executed, keep verifying
                if self.incident_state and self.incident_state["actions_executed"]:
                    await self._verify_recovery()

            log.info("runner %d loop ended", self.sim_id)
        except asyncio.CancelledError:
            log.info("runner %d cancelled", self.sim_id)

    # -------- introspection --------
    def live(self) -> dict:
        """For REST state endpoint (frontend initial load + /api/simulations/{id})."""
        last = self.history[-1] if self.history else self.engine.snapshot()
        r = getattr(self, "_risk_state", risk_score_fn(last, self.zone, 0))
        return {"simulation_id": self.sim_id, "status": self.status, "speed": self.speed,
                "tick": self.tick_n, "scenario": self.engine.scenario, **last,
                "zone": self.zone, "cargo_type": self.cargo_type,
                "risk_score": r["score"], "risk_level": r["level"],
                "exposure_ticks": self.exposure_ticks, "peak_temperature": self.peak_temp,
                "history": self.history[-120:]}

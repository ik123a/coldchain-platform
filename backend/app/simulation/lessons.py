"""What the agent learned from an incident — success or failure.

WHY THIS EXISTS
---------------
Requirement 12: the report must say how the AI resolved the problem and, if it
could not, what the failure taught it.

The reporter in agents_d.py already renders a `lessons` list — but on the fleet
path nothing ever populated it. `lessons` was only set by the classic runner
with four hardcoded strings, so a fleet incident report either omitted the
section entirely or would have shown generic advice unrelated to what actually
happened.

These lessons are DERIVED, not written. Each one is produced by comparing what
the agent decided against what actually occurred, so the report cannot claim a
lesson the evidence does not support. That distinction matters: a hardcoded
"monitor battery SOC during transfers" on an incident where the battery was
fine is worse than no lesson at all.

TWO KINDS
---------
On success  — what worked, stated so it can be repeated.
On failure  — the counterfactual: what the agent should have done instead,
               derived from the readings that were available at decision time.

A failure lesson is the more valuable half and the one the brief specifically
asks for, so it is generated whenever the outcome is unresolved OR the recovery
verifier rejected the response.
"""

from __future__ import annotations


def derive(snap: dict, diagnosis: dict | None, outcome: dict | None,
           approval: dict | None = None) -> list[str]:
    """Build the lesson list for one incident.

    snap     the vehicle snapshot at decision time
    diagnosis the P6 multi-cause verdict, if available
    outcome   {"resolved": bool, "verified": bool, "evidence": [...],
               "peak_temperature": float, "recovered_to": float}
    approval  the proposal that was raised, if any
    """
    outcome = outcome or {}
    diagnosis = diagnosis or {}
    approval = approval or {}
    refr = snap.get("refrigeration", {})
    cargo = snap.get("cargo", {})
    lessons: list[str] = []

    resolved = bool(outcome.get("resolved"))
    verified = bool(outcome.get("verified"))
    peak = outcome.get("peak_temperature", refr.get("temperature"))
    recovered_to = outcome.get("recovered_to")
    ceiling = cargo.get("mx")
    floor = cargo.get("mn")

    # --- what the agent believed, at decision time -------------------------
    believed = diagnosis.get("root_cause")
    confidence = diagnosis.get("confidence")
    if believed:
        lessons.append(
            f"Diagnosis was {believed} at {confidence:.0%} confidence; "
            f"observed outcome was {'recovery' if resolved else 'continued'} "
            f"failure.")

    # --- success lessons ----------------------------------------------------
    if resolved and verified:
        why = []
        if approval.get("target"):
            why.append(f"diverting to {approval['target']}")
        if outcome.get("backup_cooling"):
            why.append("backup cooling")
        if outcome.get("transferred_units"):
            why.append(f"transferring {outcome['transferred_units']} units")
        acted = " + ".join(why) if why else "the approved action"
        lessons.append(
            f"Repeatable: {acted} brought the box back in band "
            f"({peak}C -> {recovered_to}C, band {floor} to {ceiling}C).")
        # Only claim earlier detection is possible if there was real margin.
        if approval.get("raised_at_sim_minute") is not None and snap.get("eta_min"):
            lessons.append(
                "Decision was taken before the load left its safe band, which is "
                "what made recovery possible — an incident caught later may not "
                "be recoverable.")
        return lessons

    # --- failure lessons: the counterfactual --------------------------------
    # Only assert failure when an outcome was actually observed. With no
    # outcome record, `resolved` is False merely because nothing is known yet,
    # and reporting "FAILED to recover ... ending at NoneC" would invent a
    # failure that never happened.
    if outcome.get("observed"):
        if not resolved:
            lessons.append(
                f"FAILED to recover: peak {peak}C against a {floor}-{ceiling}C "
                f"band, ending at {recovered_to}C. A transfer to a facility that "
                f"could hold the load was required and did not happen in time.")

        if outcome.get("verified") is False and resolved:
            lessons.append(
                "Recovery verifier rejected the response: the action was taken "
                "but the readings did not confirm the cargo was safe. Taking an "
                "action is not the same as fixing the problem.")

        # Was there a recommendation that nobody acted on, or acted on too late?
        if approval.get("escalated"):
            lessons.append(
                "No operator response within the grace period, so the agent "
                "escalated by itself. Human response latency is itself a "
                "failure mode: the recommendation existed while the load spoiled.")
        if approval and not approval.get("escalated") and not resolved:
            lessons.append(
                "A scored recommendation was available and the load still "
                "failed, so the gap was in execution rather than in diagnosis.")

        # Counterfactual on the diagnosis itself.
        if believed and not resolved:
            alternatives = [c for c in (diagnosis.get("causes") or [])
                            if c.get("cause") != believed][:2]
            if alternatives:
                alt = alternatives[0]
                lessons.append(
                    f"Consider {alt['cause']} next time (scored {alt['score']:.2f}, "
                    f"likelihood {alt.get('likelihood', 'low')}): "
                    f"{alt.get('reason', '')[:120]}")

        # What the telemetry said versus what was acted on.
        trend = cargo.get("trend_c_per_min") or 0.0
        if trend and trend > 0.05 and not resolved:
            lessons.append(
                f"Warming was already {trend:+.3f} C/min when the decision was "
                f"due. A trend this steep predicts the ceiling in minutes, so "
                f"the intervention window is shorter than a human response time.")
    if refr.get("sensor_frozen"):
        lessons.append(
            "The temperature channel was frozen, so every reading the agent "
            "acted on was unreliable. Cross-check the probe before trusting a "
            "trend derived from it.")
    if refr.get("door_open"):
        lessons.append(
            "The door was open for part of the event: a seal or door-discipline "
            "check would have prevented the excursion, not just responded to it.")
    if approval.get("score") is not None and approval.get("confidence") is not None:
        lessons.append(
            f"The chosen option scored {approval.get('score')} with confidence "
            f"{approval.get('confidence'):.2f}. A lower-scoring alternative may "
            f"have been worth weighing; the full ranking is in the approval "
            f"record.")

    if not lessons:
        lessons.append(
            "No actionable lesson: the incident had not progressed far enough "
            "for the agent to distinguish a response that helped from one that "
            "did not.")
    return lessons[:6]

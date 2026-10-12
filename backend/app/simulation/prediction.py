"""Predictive safe-remaining-time: how long until this load is in trouble.

WHAT THIS IS — AND WHAT IT IS NOT
---------------------------------
Requirement 7/25 asks for predictive warnings about remaining safe time. This
module provides that, built entirely from telemetry the twin already produces:
the measured warming trend and the distance still to run.

It is explicitly NOT an Arrhenius / shelf-life kinetics model. No such model
exists anywhere in this codebase — the phrase appears only in Gemini
image-generation prompts (app/services/gemini/prompts.py), where it describes
a picture of a dashboard, not a calculation. Shipping a curve labelled
"Arrhenius degradation projection" off a linear trend would be a fabricated
result wearing the name of real kinetics, which is worse than not claiming it.

So this is an interpretable projection, and it says so in every payload:
`model: "linear_trend_projection"` and `kinetics_modelled: False`.

THE MODEL
---------
Three pieces, each a real reading:

  safe_margin_c   how far the cargo is from its critical ceiling RIGHT NOW
  trend_c_per_min measured warming rate, from a least-squares fit over the
                  last 8 samples (the twin already computes this)
  eta_min         minutes of driving still ahead, from the remaining distance

  time_to_critical = safe_margin_c / trend_c_per_min
  margin_vs_eta    = time_to_critical - eta_min

`margin_vs_eta` is the number that matters operationally: it is the slack
between "when the cargo goes bad" and "when the truck arrives". Negative means
the load will spoil before it is delivered, and no amount of driving faster
fixes it — the only remedy is cooling (rescue transfer) or rerouting to a
nearer cold store.

WHY LINEAR, AND WHERE IT BREAKS
-------------------------------
A straight line is the honest shape for a short horizon: over 20-40 minutes of
simulated driving, box warming under a failed compressor is close to linear.
It breaks down over long horizons, and the breakdown is the interesting part —
as the box warms, the driving force for heat ingress FALLS (the gap to ambient
shrinks), so real warming is concave and this projection is optimistic.

That is why `projection_confidence` falls with horizon length, and why a
long-horizon figure is never presented as precise.

SENSOR FAULT HANDLING
---------------------
The trend is fitted on `true_temperature` — the value the physics actually
produced — NOT the value the sensor reports. A frozen probe reports a
plausible, unchanging number, so a trend fitted on the reported value would be
approximately zero for exactly the incident where a trend matters most.
Fitting on truth is also the reason this can warn about a load that is
*reported* as fine but is not.
"""

from __future__ import annotations

# A trend below this is treated as "not warming" rather than integrated into an
# enormous time-to-critical. 0.005 C/min is ~0.1 C over 20 minutes: below the
# resolution of the box model, so projecting from it would be false precision.
TREND_FLOOR_C_PER_MIN = 0.005

# Horizon over which confidence decays to its floor. Past this the linear model
# is doing too much work to be worth quoting.
CONFIDENCE_HORIZON_MIN = 90.0


def project(snap: dict, ctx: dict | None = None) -> dict:
    """Project safe remaining time for one truck from its current telemetry."""
    ctx = ctx or {}
    cargo = snap["cargo"]
    trip = snap["trip"]
    eta = trip.get("eta", {}) or {}
    refr = snap["refrigeration"]

    temp = float(refr["temperature"])
    # The safe band MUST come from the vehicle. Falling back to a hardcoded
    # 2-8C here is what previously scored a -18C freezer against produce limits
    # and flagged healthy frozen loads as "below safe floor" — a silent,
    # plausible, completely wrong answer. Bands differ per cargo type, so there
    # is no safe default: raise instead of guessing.
    if cargo.get("mn") is None or cargo.get("mx") is None:
        raise KeyError(
            "cargo.mn/cargo.mx missing from vehicle snapshot: safe-remaining-"
            "time cannot be projected without the product's real temperature "
            "band, and defaulting would silently mis-score every cargo type.")
    ceiling = float(cargo["mx"])
    floor = float(cargo["mn"])
    # trend_c_per_min and true_temperature live under "cargo", not at the top
    # level — reading them from the wrong dict silently yields None, which then
    # reads as "not warming" and projects every truck as STABLE.
    trend = float(cargo.get("trend_c_per_min") or 0.0)

    # Prefer the true value for margin. If the sensor is frozen the reported
    # reading is fiction, and margin computed from it is the most dangerous
    # possible number on the screen: a healthy-looking load with no warning.
    truth = cargo.get("true_temperature")
    sensor_frozen = bool(refr.get("sensor_frozen"))
    basis_temp = float(truth) if (sensor_frozen and truth is not None) else temp

    safe_margin_c = ceiling + 2.0 - basis_temp
    below_margin_c = basis_temp - floor

    eta_min = float(eta.get("current_min") or 0.0)
    warming = trend > TREND_FLOOR_C_PER_MIN
    cooling = trend < -TREND_FLOOR_C_PER_MIN

    if cooling:
        # Falling: the box is recovering. Quote a time-to-critical of None and
        # say why, rather than dividing by a negative trend and printing a
        # positive-looking number that means nothing.
        ttc = None
        basis = "not warming (trend negative)"
    elif warming:
        ttc = max(0.0, safe_margin_c / trend)
        basis = "linear extrapolation of measured trend"
    else:
        ttc = None
        basis = "trend below measurement floor; projection withheld"

    margin_vs_eta = None
    if ttc is not None:
        margin_vs_eta = ttc - eta_min

    horizon = ttc if ttc is not None else eta_min
    confidence = _confidence(horizon, sensor_frozen, trend)

    return {
        "model": "linear_trend_projection",
        "kinetics_modelled": False,
        "assumption": (
            "Box warming is near-linear over the projected horizon. Real "
            "warming is concave (heat ingress falls as the box approaches "
            "ambient), so this projection is optimistic beyond ~30 minutes."
        ),
        "cargo_temp_c": round(basis_temp, 2),
        "reported_temp_c": round(temp, 2),
        "sensor_frozen": sensor_frozen,
        "safe_ceiling_c": ceiling,
        "safe_floor_c": floor,
        "safe_margin_c": round(safe_margin_c, 2),
        "below_floor_margin_c": round(below_margin_c, 2),
        "trend_c_per_min": round(trend, 4),
        "warming": warming,
        "eta_min": round(eta_min, 1),
        "time_to_critical_min": None if ttc is None else round(ttc, 1),
        "margin_vs_eta_min": None if margin_vs_eta is None else round(margin_vs_eta, 1),
        "projection_confidence": confidence,
        "basis": basis,
        "verdict": _verdict(ttc, eta_min, margin_vs_eta, warming, cooling,
                           safe_margin_c, below_margin_c),
        "traffic_level": ctx.get("traffic_level"),
        "remediable_by_speed": (
            margin_vs_eta is not None and margin_vs_eta < 0
        ),
        "remedy": _remedy(ttc, eta_min, margin_vs_eta, warming, cooling,
                             safe_margin_c, below_margin_c),
    }


def _confidence(horizon_min: float, sensor_frozen: bool, trend: float) -> str:
    # A frozen probe makes every number on this panel uncertain, so it caps
    # confidence regardless of horizon.
    if sensor_frozen:
        return "LOW (temperature channel unreliable)"
    if horizon_min > CONFIDENCE_HORIZON_MIN:
        return "LOW (linear model unreliable past 90 min)"
    if horizon_min > 30:
        return "MEDIUM"
    if abs(trend) > TREND_FLOOR_C_PER_MIN * 10:
        return "MEDIUM"
    return "HIGH (short horizon, clear trend)"


def _verdict(ttc, eta_min, margin_vs_eta, warming: bool, cooling: bool,
             safe_margin_c: float = 0.0, below_margin_c: float = 0.0) -> str:
    # A load that is ALREADY past its limit is not stable under any reading.
    # This case has to be checked before the trend logic, because once the box
    # is far out of band the warming trend flattens (it is approaching ambient),
    # ttc becomes None, and the verdict would otherwise read "STABLE" for a
    # load that is spoiling right now.
    if safe_margin_c <= 0:
        return "ALREADY PAST CRITICAL CEILING"
    if below_margin_c <= 0:
        return "ALREADY BELOW SAFE FLOOR"
    if cooling:
        return "RECOVERING"
    if ttc is None:
        return "STABLE"
    if margin_vs_eta is None:
        # In band but no usable trend to project from. Healthy and warming
        # cannot be told apart here, so this is a watch state, not a safe one.
        return "WATCH" if warming else "STABLE"
    if margin_vs_eta < 0:
        return "WILL SPOIL BEFORE ARRIVAL"
    if margin_vs_eta < 10:
        return "CRITICAL — margin under 10 minutes"
    if margin_vs_eta < 25:
        return "AT RISK — little slack for traffic"
    return "SAFE — cargo survives the remaining route"


def _remedy(ttc, eta_min, margin_vs_eta, warming: bool, cooling: bool,
            safe_margin_c: float = 0.0, below_margin_c: float = 0.0) -> str:
    """What to actually do. These map onto the approval-gated rescue actions."""
    if safe_margin_c <= 0:
        return ("Immediate: the load is already past its critical ceiling. A "
                "rescue cold-store transfer is the only remedy that works — "
                "needs approval.")
    if below_margin_c <= 0:
        return ("Immediate: the load is below its safe floor. Restore heating or "
                "transfer to a facility that can hold it — needs approval.")
    if cooling:
        return "No action — the box is recovering. Keep monitoring."
    if ttc is None:
        return "No action — cargo is holding. Continue the route."
    if margin_vs_eta is not None and margin_vs_eta < 0:
        return ("Speed alone cannot fix this: the load goes critical before the "
                "truck arrives. Options are a rescue cold-store transfer or "
                "rerouting to the nearest facility — both need approval.")
    if margin_vs_eta is not None and margin_vs_eta < 10:
        return ("Thin margin. Re-check traffic before committing to the rest of "
                "the route; a rescue transfer is worth considering and needs "
                "approval.")
    return "Continue the route. Re-evaluate if the warming trend increases."

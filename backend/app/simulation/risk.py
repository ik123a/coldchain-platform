"""Risk engine — deterministic, explainable. Score 0-100 with component breakdown."""
from __future__ import annotations

CARGO_SENSITIVITY = {
    "fresh_produce": 1.0,
    "dairy": 1.1,
    "frozen_goods": 0.7,
    "pharmaceutical": 1.4,
}


def risk(r: dict, zone: dict, exposure_ticks: int, cargo_type="fresh_produce", trend_c_per_min=0.0) -> dict:
    """r = one engine snapshot dict."""
    mn, mx = zone["mn"], zone["mx"]
    temp = r["temperature"]
    over = max(0.0, temp - mx)
    # extent of excursion (dominant driver), severity escalates non-linearly
    extent = min(38.0, over * 9.5 + (6.0 if over > 2 else 0) + (10.0 if over > 4 else 0))
    # exposure duration
    duration = min(28.0, exposure_ticks * 0.9) if over > 0 else 0.0
    # humidity deviation beyond band
    hmn, hmx = zone.get("hum_min", 60), zone.get("hum_max", 85)
    hum_dev = max(hmn - r["humidity"], 0, r["humidity"] - hmx)
    humidity = min(12.0, hum_dev * 0.5)
    # equipment: door open
    door = 8.0 if r.get("door_open") else 0.0
    # equipment: compressor offline
    compressor = 12.0 if not r.get("compressor_on") else 0.0
    # backup power state
    power = 6.0 if not r.get("power_ok") else 0.0
    # warming trend (c per min)
    trend = min(10.0, max(0.0, trend_c_per_min) * 30.0)
    # cargo already degraded
    cargo = max(0.0, (100.0 - r.get("cargo_health", 100.0)) * 0.15)

    sensitivity = CARGO_SENSITIVITY.get(cargo_type, 1.0)
    score = (extent + duration + humidity + door + compressor + power + trend + cargo) * sensitivity
    score = round(min(100.0, score), 1)

    level = ("LOW" if score < 30 else "MEDIUM" if score < 55 else "HIGH" if score < 78 else "CRITICAL")

    driven = [
        {"component": "temperature excursion", "points": round(extent * sensitivity, 1)},
        {"component": "exposure duration", "points": round(duration * sensitivity, 1)},
        {"component": "compressor offline", "points": round(compressor * sensitivity, 1)},
        {"component": "door open", "points": round(door * sensitivity, 1)},
        {"component": "warming trend", "points": round(trend * sensitivity, 1)},
        {"component": "humidity deviation", "points": round(humidity * sensitivity, 1)},
        {"component": "power failure", "points": round(power * sensitivity, 1)},
        {"component": "cargo decay", "points": round(cargo * sensitivity, 1)},
    ]
    driven = [d for d in driven if d["points"] >= 0.5]
    driven.sort(key=lambda d: -d["points"])

    return {
        "score": score, "level": level, "sensitivity": sensitivity,
        "components": driven,
        "explain": " + ".join(f"{d['points']} {d['component']}" for d in driven[:4]),
    }

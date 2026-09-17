"""Acceptance sweep — end-to-end verification against a RUNNING backend.

Run with the backend up (uvicorn app.main:app --port 8000), then:
    PYTHONPATH=. python tests/acceptance_sweep.py

Drives: POST /api/fleet/rebuild (seed 7) -> 60s WS listen while firing
targeted injections (compressor_failure, service dispatch, truck-to-truck
transfer) -> asserts the full observable event vocabulary appeared:
fleet.incident.created, ai.route.decision, vehicle.route.changed,
cargo.transferred, vehicle.idling|vehicle.stopped, geofence.entered,
weather.changed, service.completed, cargo.transfer.progress.
"""
import asyncio, json, sys, urllib.request

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws"
WINDOW = 60.0  # seconds of live event collection

REQUIRED = [
    "fleet.incident.created", "ai.route.decision", "vehicle.route.changed",
    "cargo.transferred", "weather.changed", "geofence.entered",
    "service.completed", "cargo.transfer.progress",
]
ALT = [["vehicle.idling", "vehicle.stopped"]]  # either/or


def check(cond, label):
    print(("PASS - " if cond else "FAIL - ") + label)
    if not cond:
        sys.exit(1)


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def find_pair():
    """A valid truck-to-truck transfer pair: same cargo_type, donor has load,
    receiver not CRITICAL (the API revalidates capacity)."""
    st = call("/api/fleet/state")
    trucks = [v for v in st["vehicles"] if v["type"] != "SERVICE_TRUCK"]
    for donor in trucks:
        if donor["cargo"]["load_units"] <= 0:
            continue
        for receiver in trucks:
            if donor["vehicle_id"] == receiver["vehicle_id"]:
                continue
            if donor["cargo"]["cargo_type"] != receiver["cargo"]["cargo_type"]:
                continue
            if receiver["cargo"]["risk_level"] == "CRITICAL":
                continue
            return donor, receiver, trucks
    return None, None, trucks


async def collect_events(stop_at: float, sink: list[dict]) -> None:
    import websockets
    async with websockets.connect(WS, max_size=None) as ws:
        loop = asyncio.get_event_loop()
        end = loop.time() + stop_at
        while loop.time() < end:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(2.0, max(0.1, end - loop.time())))
                sink.append(json.loads(raw))
            except asyncio.TimeoutError:
                continue


async def main():
    import websockets  # noqa: F401  (fail fast if missing)

    # 1. start the 60s WS collector FIRST so spawn-time geofence.entered
    #    events (vehicles materialize inside warehouse zones) are captured
    seen: list[dict] = []
    task = asyncio.create_task(collect_events(WINDOW, seen))
    await asyncio.sleep(0.5)

    # 2. rebuild the world with seed 7 (deterministic scenario)
    res = call("/api/fleet/rebuild", "POST", {"fleet_size": 10, "seed": 7,
                                              "traffic_intensity": 1.0,
                                              "failure_probability": 0.0})
    check(res["world_id"] == 7 and res["vehicles"] == 12, f"rebuild seed 7 -> 12 vehicles ({res['vehicles']})")

    donor_t, receiver_t, trucks = find_pair()
    if donor_t is None:
        check(False, "no valid transfer pair found in state")
    donor, receiver = donor_t["vehicle_id"], receiver_t["vehicle_id"]
    print(f"transfer pair: {donor} -> {receiver} ({donor_t['cargo']['cargo_type']})")

    # truck-to-truck transfer FIRST on the healthy matched pair (progress 0->100
    # then completion), then failure on a DIFFERENT truck so the transfer and
    # the incident chain don't race each other
    other = next(t["vehicle_id"] for t in trucks
                 if t["vehicle_id"] not in (donor, receiver))
    call("/api/fleet/transfer", "POST", {"from_vehicle_id": donor, "to_vehicle_id": receiver})
    # targeted failure -> incident -> AI divert -> route change -> warehouse transfer
    call(f"/api/fleet/vehicle/{other}/inject", "POST", {"failure": "compressor_failure"})
    # service dispatch to repair the failed truck
    call("/api/fleet/service/dispatch", "POST", {"vehicle_id": other, "task": "repair"})

    # escalate deterministically: the AI may judge CONTINUE on the first
    # truck, so inject up to 3 more cargo trucks spaced out until a DIVERT
    # (vehicle.route.changed) is observed on the wire
    injected: set[str] = {other}
    for _ in range(3):
        await asyncio.sleep(12)
        if any(e.get("type") == "vehicle.route.changed" for e in seen):
            break
        try:
            vid2 = next(t["vehicle_id"] for t in find_pair()[2]
                        if t["vehicle_id"] not in (donor, receiver) and t["vehicle_id"] not in injected)
        except StopIteration:
            break
        injected.add(vid2)
        call(f"/api/fleet/vehicle/{vid2}/inject", "POST", {"failure": "compressor_failure"})
    # deterministic weather change mid-window (demo lever)
    await asyncio.sleep(3)
    call("/api/fleet/weather", "POST", {"weather": "HEATWAVE"})
    # let the incident chain (created -> decision -> reroute -> arrival ->
    # warehouse transfer) finish, then spawn a fresh world at the END of the
    # window: geofence.entered fires on a world's first tick while vehicles
    # materialize inside zones — a second subscriber-connected rebuild makes
    # those entries land on the wire deterministically.
    await asyncio.sleep(38)
    call("/api/fleet/rebuild", "POST", {"fleet_size": 10, "seed": 13,
                                        "traffic_intensity": 1.0,
                                        "failure_probability": 0.0})

    await task
    events = seen
    print(f"\ncollected {len(events)} events in {WINDOW:.0f}s")

    # 3. assert the required vocabulary appeared on the wire
    types = [e.get("type") for e in events]
    for et in REQUIRED:
        check(et in types, f"event observed: {et}")
    for alts in ALT:
        check(any(a in types for a in alts), f"event observed: {' | '.join(alts)}")

    # 4. spot-check the chain ordering on the injected truck: incident -> decision -> reroute
    chain = [(e.get("type"), e.get("vehicle_id")) for e in events
             if e.get("type") in ("fleet.incident.created", "ai.route.decision",
                                  "vehicle.route.changed")]
    idx = {t: next((i for i, (tt, _) in enumerate(chain) if tt == t), None) for t, _ in chain}
    got = [t for t, _ in chain]
    ok_order = ("fleet.incident.created" in got and "ai.route.decision" in got
                and "vehicle.route.changed" in got
                and got.index("fleet.incident.created") < got.index("ai.route.decision")
                <= got.index("vehicle.route.changed"))
    check(ok_order, f"chain ordered incident->decision->reroute {got}")

    # 5. progress events actually ramp 0->100
    prog = [e.get("progress_pct") for e in events if e.get("type") == "cargo.transfer.progress"]
    check(prog and prog[0] == 0 and prog[-1] == 100, f"transfer progress ramps 0->100 {prog[:7]}")

    # 6. KPI endpoint still coherent post-sweep
    kpi = call("/api/fleet/analytics")
    fh = kpi["fleet_health"]
    n_cargo = sum(1 for v in call("/api/fleet/state")["vehicles"] if v["type"] != "SERVICE_TRUCK")
    check(fh["healthy"] + fh["warning"] + fh["degraded"] + fh["critical"] == n_cargo,
          f"analytics fleet_health sums to cargo count ({n_cargo})")

    print("\nACCEPTANCE SWEEP: ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())

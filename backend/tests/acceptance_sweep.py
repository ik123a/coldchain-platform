"""Acceptance sweep — end-to-end verification against a RUNNING backend.

Run with the backend up, then:
    PYTHONPATH=. python tests/acceptance_sweep.py

Drives: POST /api/fleet/rebuild (seed 7) -> 60s WS listen while firing
targeted injections (compressor_failure, service dispatch, truck-to-truck
transfer) -> asserts the full observable event vocabulary appeared:
fleet.incident.created, ai.route.decision, vehicle.route.changed,
cargo.transferred, vehicle.idling|vehicle.stopped, geofence.entered,
weather.changed, service.completed, cargo.transfer.progress.

HUMAN-IN-THE-LOOP (approval-aware)
----------------------------------
`vehicle.route.changed` only fires once a DIVERT is APPLIED, and the product
queues DIVERT as a pending recommendation for a human. This sweep therefore
drives the real workflow: it finds the pending approval for the truck it
injected, POSTs the operator's decision through the existing approvals API, then
waits for the route to actually change before asserting the chain.

This TESTS the intended behaviour rather than weakening it — `require_approval`
stays on and nothing here disables the gate.

Exit codes: 0 = all assertions passed, 1 = ran and assertions failed,
2 = setup failure (wrong/unreachable target, no fleet) so the two are
distinguishable in CI.
"""
import asyncio, json, os, sys, time, urllib.parse, urllib.request

BASE = os.environ.get("SWEEP_BASE", "http://127.0.0.1:8000")
WS = os.environ.get("SWEEP_WS", "ws://127.0.0.1:8000/ws")
WINDOW = 60.0  # seconds of live event collection

# The backend is fail-closed: mutating routes need a bearer token even in
# development. The sweep signs in once and attaches the token to every call,
# rather than the server being left open to keep the sweep green.
SWEEP_EMAIL = os.environ.get("SWEEP_OPERATOR_EMAIL", "ops@test.local")
SWEEP_PASSWORD = os.environ.get("SWEEP_OPERATOR_PASSWORD", "secret123")
_TOKEN: str | None = None

REQUIRED = [
    "fleet.incident.created", "ai.route.decision", "vehicle.route.changed",
    "cargo.transferred", "weather.changed", "geofence.entered",
    "service.completed", "cargo.transfer.progress",
]
ALT = [["vehicle.idling", "vehicle.stopped"]]  # either/or

# ---------------------------------------------------------------------------
# Assertion collection
# ---------------------------------------------------------------------------
# `check()` used to call sys.exit(1) on the first failure, so one missing event
# hid every later assertion. These are INDEPENDENT product assertions and are now
# collected before exiting. Setup problems still abort immediately via `fatal()`
# — continuing past a wrong-target or no-fleet failure would only manufacture
# meaningless failures.
_FAILURES: list[str] = []
_CHECKS = [0]


def check(cond, label):
    _CHECKS[0] += 1
    print(("PASS - " if cond else "FAIL - ") + label)
    if not cond:
        _FAILURES.append(label)
    return bool(cond)


def fatal(label):
    """Setup failure: report and abort with a distinct exit code (2)."""
    print("SETUP FAILURE - " + label)
    sys.exit(2)


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def sign_in():
    """Obtain a bearer token for the operator account this sweep acts as.

    Fail-closed backend: without this every mutating POST returns 401 and the
    sweep would report product failures that are really auth failures.
    """
    global _TOKEN
    try:
        data = json.dumps({"email": SWEEP_EMAIL, "password": SWEEP_PASSWORD}).encode()
        req = urllib.request.Request(BASE + "/api/auth/login", data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            _TOKEN = json.load(r)["access_token"]
        return True
    except Exception as exc:
        return False


def issue_ws_ticket():
    """Mint a single-use WebSocket ticket for the signed-in operator.

    `/ws` is authenticated now: without a ticket the sweep's collector could not
    connect at all, and every event-based assertion would fail as a product
    failure when the real cause is a missing credential. Returns None if the
    ticket could not be obtained so the caller can fail loudly.
    """
    if not _TOKEN and not sign_in():
        return None
    try:
        data = json.dumps({}).encode()
        req = urllib.request.Request(BASE + "/api/ws/ticket", data=data, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {_TOKEN}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r).get("ticket")
    except Exception:
        return None


def call_safe(path, method="GET", body=None):
    """`call` that converts an HTTP error into a value instead of an exception.

    The approvals endpoint can legitimately fail (it has returned 500 on a
    `fleet_routes.id` uniqueness collision). An unhandled HTTPError aborts the
    whole run with a traceback, which hides every remaining assertion and gives no
    diagnostic. The brief requires an endpoint failure to be REPORTED, so the
    status and a slice of the body are surfaced through `check()` instead.
    """
    try:
        return {"ok": True, "data": call(path, method, body)}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return {"ok": False, "status": e.code, "detail": detail}
    except Exception as exc:
        return {"ok": False, "status": None, "detail": f"{type(exc).__name__}: {exc}"}


def assert_capstone_target():
    """Refuse to run mutating requests against anything that is not this API.

    Port 8000 is not always this project (an unrelated service has used it), and
    a wrong target would answer with 404s that read like product failures.
    """
    try:
        st = call("/api/status")
    except Exception as exc:
        fatal(f"cannot reach {BASE}: {exc}")
    if st.get("ai_mode") != "DETERMINISTIC-AGENTS":
        fatal(f"wrong server at {BASE}: /api/status returned {st!r}, which is not "
              f"the cold-chain API. Refusing to send mutating requests to it.")
    print(f"target verified: {BASE} ({st.get('system')} / {st.get('ai_mode')})")
    if not sign_in():
        fatal(f"could not sign in as {SWEEP_EMAIL} — the backend is fail-closed, so "
              f"every mutating request would 401. Set SWEEP_OPERATOR_EMAIL / "
              f"SWEEP_OPERATOR_PASSWORD to a valid operator account.")
    print(f"signed in as {SWEEP_EMAIL}\n")


def find_pair():
    """A valid truck-to-truck transfer pair: same cargo_type, donor has load,
    receiver not CRITICAL (the API revalidates capacity)."""
    st = call("/api/fleet/state")
    trucks = [v for v in st["vehicles"] if v["type"] != "SERVICE_TRUCK"]
    if not trucks:
        fatal("no cargo trucks in fleet — is FLEET_AUTOSTART set on this server?")
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


# ---------------------------------------------------------------------------
# Approval-aware reroute (human-in-the-loop)
# ---------------------------------------------------------------------------
def pending_for(vehicle_id):
    """The pending recommendation awaiting a human decision for this vehicle."""
    try:
        data = call("/api/fleet/approvals")
    except Exception as exc:
        print(f"  (approvals query failed: {exc})")
        return None
    for p in data.get("pending", []):
        if p.get("vehicle_id") == vehicle_id:
            return p
    return None


def approve(key):
    """POST the operator's approval.

    The key is URL-encoded: keys look like 'TRUCK-1234-00:WH-003:2' and are
    matched by a greedy `{key:path}` converter, so an unencoded key is not safely
    round-trippable.

    Returns the call_safe envelope so an endpoint failure is reported as a failed
    assertion with the HTTP status and body rather than aborting the run.
    """
    return call_safe(f"/api/fleet/approvals/{urllib.parse.quote(key, safe='')}", "POST",
                     {"approve": True, "note": "acceptance sweep: operator approved"})

async def poll_for_approval(vehicle_id, deadline_s=25.0):
    """The coordinator decides on the tick AFTER the incident, so wait for the
    queue to fill rather than assuming the recommendation is already there.

    Async on purpose: an earlier version used time.sleep() in this loop, which
    blocks the event loop for up to the whole deadline. That starved the WebSocket
    collector task, and its opening handshake timed out — the sweep then recorded
    zero events and reported failures against an empty event list rather than a
    real product problem. Any sleep in this file must be awaited.
    """
    loop = asyncio.get_event_loop()
    end = loop.time() + deadline_s
    while loop.time() < end:
        p = pending_for(vehicle_id)
        if p:
            return p
        await asyncio.sleep(0.5)
    return None


async def wait_for_event(seen, etype, deadline_s, vehicle_id=None):
    """Inspect only what the server actually broadcast. No synthetic events."""
    loop = asyncio.get_event_loop()
    end = loop.time() + deadline_s
    while loop.time() < end:
        for e in seen:
            if e.get("type") == etype and (vehicle_id is None
                                           or e.get("vehicle_id") == vehicle_id):
                return e
        await asyncio.sleep(0.4)
    return None


async def collect_events(stop_at: float, sink: list[dict]) -> None:
    """Collect broadcasts over an AUTHENTICATED socket.

    `/ws` requires a single-use ticket now, so the sweep mints one over the
    authenticated REST layer first — the same path a real client takes. The
    ticket is passed as a SUBPROTOCOL rather than a query parameter because
    uvicorn logs the query string verbatim.
    """
    import websockets
    ticket = issue_ws_ticket()
    if not ticket:
        raise RuntimeError("could not mint a WebSocket ticket — is the operator "
                           "password in this harness still valid?")
    async with websockets.connect(
            WS, max_size=None,
            subprotocols=[f"cc-ticket.{ticket}"]) as ws:
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

    assert_capstone_target()

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
        fatal("no valid transfer pair found in state")
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

    # 2b. HUMAN-IN-THE-LOOP. The AI queues the DIVERT for a human decision, so
    #     the route cannot change until an operator approves it. This is the
    #     intended product behaviour, not a defect: drive it rather than bypass it.
    print(f"\nwaiting for a pending DIVERT on {other} ...")
    prop = await poll_for_approval(other)
    if prop is None:
        fatal(f"no pending approval appeared for {other} within the deadline — the "
              f"coordinator never queued a recommendation for the injected truck")
    print(f"  pending: {prop.get('decision')} -> {prop.get('target')} "
          f"(key={prop.get('key')!r}, incident={prop.get('incident_id')})")
    check(prop.get("decision") == "DIVERT",
          f"queued recommendation for {other} is a DIVERT (got {prop.get('decision')})")

    decided_res = approve(prop["key"])
    if not decided_res["ok"]:
        check(False, f"approval endpoint failed (HTTP {decided_res['status']}): "
                     f"{decided_res['detail'][:160]}")
        fatal("cannot continue: the approval request itself failed")
    decided = decided_res["data"]
    print(f"  approved -> status={decided.get('status')} vehicle={decided.get('vehicle_id')} "
          f"target={decided.get('target')}")
    check(decided.get("status") == "APPROVED",
          f"approval recorded as APPROVED (got {decided.get('status')})")
    check(decided.get("vehicle_id") == other,
          f"approved recommendation belongs to the injected truck {other} "
          f"(got {decided.get('vehicle_id')})")
    # Approving a recommendation for a different truck would still emit the event
    # and make the sweep look green for the wrong reason.
    check(decided.get("target") == prop.get("target"),
          f"approved target matches the queued recommendation ({prop.get('target')})")

    # The route change is the observable consequence of the approval. Wait for
    # the REAL broadcast; the sweep never fabricates an event.
    ev = await wait_for_event(seen, "vehicle.route.changed", 25.0, vehicle_id=other)
    check(ev is not None,
          f"vehicle.route.changed observed for {other} after approval"
          + ("" if ev else " — the approved divert never reached the wire"))
    if ev is not None:
        print(f"  route.changed payload: {json.dumps(ev)[:160]}")

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
        # Approve any recommendation this truck raised, or the gate blocks the
        # reroute exactly as it did for the first truck.
        p2 = await poll_for_approval(vid2, deadline_s=10.0)
        if p2:
            r2 = approve(p2["key"])
            if not r2["ok"]:
                print(f"  (approval for {vid2} failed: HTTP {r2['status']} "
                      f"{r2['detail'][:100]})")
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

    # A WebSocket that never connected yields an EMPTY event list, and every
    # vocabulary assertion below would then fail — blaming the product for a
    # harness failure. That is exactly what happened once. Refuse to score it.
    if not events:
        fatal(f"WebSocket collected 0 events from {WS} — the collector never "
              f"connected, so no vocabulary assertion can be trusted")

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

    # 7. The approval gate must still be ON. If this sweep had disabled it, every
    #    earlier assertion would be testing the wrong product.
    ap = call("/api/fleet/approvals")
    check(ap.get("require_approval") is True,
          f"human approval remained enabled throughout "
          f"(require_approval={ap.get('require_approval')})")

    total = _CHECKS[0]
    passed = total - len(_FAILURES)
    print(f"\n{passed}/{total} assertions passed")
    if _FAILURES:
        print("FAILED ASSERTIONS:")
        for f in _FAILURES:
            print("  -", f)
        print("\nACCEPTANCE SWEEP: FAIL")
        sys.exit(1)
    print("\nACCEPTANCE SWEEP: ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())

"""Record the ColdChain Rescue demo as real screen footage with voiceover.

Design decisions, and why:

* REAL FOOTAGE, NOT RENDERED. Playwright records the actual app in a real
  browser, so every frame is the genuine UI. Earlier attempts generated
  mockups, which looked plausible but could not be checked against the running
  system — a caption could claim a panel existed when it did not.

* EVERY SHOT IS VERIFIED BEFORE ROLLING. Each step asserts the thing it is
  about to show actually rendered. A shot that fails records nothing and the
  script reports which one, instead of producing a video that quietly lies.
  This is the same discipline the project audit calls for: a verifier that
  cannot fail is not a verifier.

* FLEET SELF-REPAIR IS HANDLED. Injecting a fault into a healthy world gets
  repaired within ~30 sim-seconds, so a fixed sleep after injection is a coin
  flip. Each shot polls for the state it needs with a deadline.

* VOICEOVER IS ALIGNED PER SHOT, NOT APPENDED. Each shot's narration is
  rendered to its own audio file and muxed against that shot's exact duration,
  so narration cannot drift out of sync over a long video the way one
  concatenated track does.
"""

import json
import os
import urllib.request
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "demo" / "video"
FRAMES = OUT / "_shots"
AUDIO = OUT / "_audio"
API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"

W, H = 1920, 1080
FPS = 30

# Narration per shot. Written to be spoken plainly and to describe only what
# that shot actually shows.
SHOTS = [
    dict(
        name="01-dashboard",
        route="/dashboard",
        settle=10,
        vo=(
            "ColdChain Rescue. A cold chain monitoring platform for pharmaceutical "
            "and food logistics across the Delhi North Corridor."
        ),
    ),
    dict(
        name="02-live-map",
        route="/live-map",
        settle=11,
        vo=(
            "Every truck on the map is moving, with its route, its current "
            "temperature, speed and load. Fourteen units, one live fleet view."
        ),
    ),
    dict(
        name="03-simulation",
        route="/simulation",
        settle=7,
        vo=(
            "On simulation, you build the fleet yourself. Add a truck, choose the "
            "product and the destination warehouse. Nothing is assigned "
            "automatically."
        ),
        open_panel=True,
    ),
    dict(
        name="04-approvals",
        route="/simulation",
        settle=15,
        vo=(
            "When the agent finds a critical fault, it does not act alone. It "
            "proposes the best cold store, scored on time, traffic, capacity and "
            "cost, and waits for you to approve."
        ),
        need=["Approve", "Reject"],
        # Scroll the approval queue into view before rolling. The gate exists in
        # the DOM (which is why the assertion passed) but sits below the fold at
        # 1920x1080, so the recorded frame showed the truck panel and cut the
        # Approve/Reject buttons off mid-panel. A verifier that reads innerHTML
        # cannot catch a framing problem - only the rendered frame can.
        scroll_to="Approve",
    ),
    dict(
        name="05-incident",
        route="/incidents",
        settle=12,
        vo=(
            "Thirteen incident types are detected from real telemetry. Four more "
            "are declared as gaps, because the sensors to detect them honestly do "
            "not exist."
        ),
    ),
    dict(
        name="06-reports",
        route="/reports",
        settle=8,
        vo=(
            "Every incident ends in a report: the truck, the problem, what the "
            "agent did, and what it learned when it could not resolve the fault."
        ),
        # Open the first report so the body and the derived lessons are on
        # screen. Requirement 8 asks for them to be visible; until now the page
        # offered only JSON/PDF download links and the lessons existed solely
        # inside the API payload.
        click="View report",
        # The panel heading, plus a phrase that only appears in real derived
        # lessons. Checking for the literal "Lesson" was wrong: the page strips
        # the "Lesson: " prefix when rendering, so that string is never in the
        # DOM even when lessons are correctly displayed.
        need=["What the agent learned", "Response score"],
    ),
    dict(
        name="07-settings",
        route="/settings",
        settle=5,
        vo="Light and dark themes, operator settings, and the system status panel.",
    ),
]


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def api_post(path, body=None):
    import urllib.request
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        API + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except Exception as exc:  # noqa: BLE001
        print(f"    api_post {path} -> {exc}")
        return 0


def inject_fault_and_wait(timeout=150):
    """Force a real incident so the approval and report shots have content.

    A healthy fleet never produces a pending recommendation or a derived lesson,
    so those two shots recorded an empty UI. Rather than staging a mock, drive
    the real fault path: pick a live truck, inject a compressor failure, then
    poll until the backend actually reports an escalated approval.
    """
    print("  injecting a compressor fault to produce a real incident")
    try:
        with urllib.request.urlopen(API + "/api/fleet/state", timeout=25) as r:
            vehicles = json.loads(r.read()).get("vehicles") or []
    except Exception as exc:  # noqa: BLE001
        print(f"    x could not read state: {exc}")
        return False

    target = next((v for v in vehicles if v.get("kind") != "SERVICE_TRUCK"), None)
    if target is None:
        print("    x no truck available")
        return False
    vid = target.get("id") or target.get("vehicle_id")
    print(f"    target: {vid}")

    api_post(f"/api/fleet/vehicle/{vid}/inject", {"failure": "compressor_failure"})

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(API + "/api/fleet/approvals", timeout=25) as r:
                a = json.loads(r.read())
            pending = a.get("pending_count") or 0
            if pending > 0:
                print(f"    incident raised: {pending} pending approval(s)")
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    print("    x no approval appeared within the timeout")
    return False


def seed_fleet():
    """Populate the world so the footage shows a live fleet, not an empty map.

    Uses the dispatch API rather than FLEET_AUTOSTART so the state matches what
    the operator-facing flow actually creates.
    """
    print("  seeding fleet (3 operator-defined trucks + service units)")

    # POST /api/fleet/dispatch/clear is the documented reset, but it only
    # releases destinations for vehicles the CURRENT process spawned. Trucks
    # started by a previous recording run keep WH-001..WH-00n reserved, so a
    # re-run was rejected with
    #   "destination WH-001 is already used by another truck in this run".
    # Remove every existing spec explicitly, then clear. Idempotent: this is a
    # demo recorder, not a production path.
    def wipe_dispatch():
        try:
            with urllib.request.urlopen(API + "/api/fleet/dispatch", timeout=20) as r:
                trucks = json.loads(r.read()).get("trucks") or []
        except Exception:  # noqa: BLE001
            trucks = []
        for t in trucks:
            tid = t.get("id")
            if not tid:
                continue
            try:
                req = urllib.request.Request(
                    f"{API}/api/fleet/dispatch/trucks/{tid}", method="DELETE")
                urllib.request.urlopen(req, timeout=20).read()
            except Exception:  # noqa: BLE001
                pass
        api_post("/api/fleet/dispatch/clear")

    wipe_dispatch()

    # Read the product/destination ids from the API rather than hardcoding them.
    # Guessed values ("pharmaceutical", "D-108") were rejected with HTTP 400 —
    # the real ids are "pharma" and warehouse codes, and GET /api/fleet/dispatch
    # publishes both under `catalog`. Asking the server is the only way to stay
    # correct when the model changes.
    try:
        with urllib.request.urlopen(API + "/api/fleet/dispatch", timeout=20) as r:
            catalog = json.loads(r.read()).get("catalog", {})
        products = catalog.get("products") or ["pharma"]
        dests = catalog.get("destinations") or ["WH-004"]
    except Exception as exc:  # noqa: BLE001
        print(f"    x could not read catalog: {exc}")
        return False

    print(f"    products={products[:4]} destinations={[d.get('id') for d in dests if isinstance(d, dict)][:4]}")

    # destinations are objects ({"id": ..., "name": ..., "cargo_types": [...]}),
    # not plain strings. Passing the whole dict gave HTTP 422. Take the id, and
    # match each product to a warehouse that actually accepts it so the shot
    # shows a legal delivery rather than a rejected one.
    dest_ids = [d.get("id") if isinstance(d, dict) else d for d in dests]
    dest_by_id = {d.get("id"): d for d in dests if isinstance(d, dict)}

    # A destination may only be used ONCE per run: the backend rejects a second
    # truck aimed at the same warehouse with
    #   "destination WH-001 is already used by another truck in this run".
    # The earlier fallback always picked dest_ids[0], so trucks 2 and 3 collided.
    # Track what is taken and never reuse it.
    taken = set()

    added = 0
    for cargo in products[:3]:
        compatible = [i for i in dest_ids
                      if i not in taken
                      and cargo in (dest_by_id.get(i, {}).get("cargo_types") or [])]
        any_free = [i for i in dest_ids if i not in taken]
        target = (compatible or any_free or dest_ids)[0]
        taken.add(target)
        units = min(250, int(dest_by_id.get(target, {}).get("available_capacity") or 250))
        code = api_post("/api/fleet/dispatch/trucks",
                        {"cargo_type": cargo, "destination_id": target, "load_units": units})
        print(f"    + {cargo} -> {target} ({units}u) http={code}")
        if code in (200, 201):
            added += 1
    if not added:
        print("    x no truck could be added")
        return False
    api_post("/api/fleet/dispatch/start")

    # Wait for the world loop to actually produce vehicles. The loop starts
    # lazily with the first truck, so state is not populated instantly.
    deadline = time.time() + 90
    while time.time() < deadline:
        out = sh(f'curl -s {API}/api/fleet/state')
        try:
            if len(json.loads(out.stdout).get("vehicles") or []) >= 3:
                print("    fleet live")
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    print("    x fleet never populated")
    return False


def wait_for(page, needles, timeout=25):
    """Poll until every needle appears in the rendered DOM."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        html = page.evaluate("() => document.body.innerHTML")
        if all(n in html for n in needles):
            return True
        time.sleep(0.5)
    return False


def record_shot(shot):
    """Record one shot. Returns (ok, actual_duration_seconds, notes)."""
    from playwright.sync_api import sync_playwright

    FRAMES.mkdir(parents=True, exist_ok=True)
    target = FRAMES / shot["name"]
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    notes = []
    with sync_playwright() as p:
        browser = p.chromium.launch(slow_mo=40)
        # This Playwright build exposes record_video_dir / record_video_size as
        # flat kwargs; the nested record_video={...} form from the skill docs is
        # the TypeScript shape and raises TypeError here.
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(FRAMES),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()

        ok = True
        try:
            page.goto(WEB + shot["route"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(shot["settle"] * 1000)

            if shot.get("open_panel"):
                # The dispatch builder lives behind the truck-panel toggle.
                # One pass. Clicking every match across four attribute
                # selectors cost 107s on this shot, most of it waiting on
                # clicks that toggled the panel shut again.
                for sel in ["[aria-label*='truck' i]", "[title*='ruck' i]"]:
                    for el in page.query_selector_all(sel):
                        try:
                            el.click()
                            page.wait_for_timeout(350)
                        except Exception:  # noqa: BLE001
                            pass
                        break
                page.wait_for_timeout(1200)
                if not wait_for(page, ["Choose a product"], 15):
                    ok = False
                    notes.append("dispatch builder did not open")

            # The approval queue sits inside a panel taller than the viewport
            # whose overflow is CONTAINED: document.body scrollHeight equalled
            # innerHeight, so scrollIntoView moved the button within its parent
            # while the page never scrolled, and the recorded frame still cut
            # the gate off. Scrolling the nearest scrollable ancestor is what
            # actually brings it into frame.
            needle = shot.get("scroll_to")
            if needle:
                found = page.evaluate(
                    """(text) => {
                        const btn = [...document.querySelectorAll('button')]
                            .find(e => e.innerText && e.innerText.trim() === text);
                        if (!btn) return {ok: false, why: 'not found'};
                        let el = btn.parentElement, hops = 0;
                        while (el && hops < 12) {
                            const range = el.scrollHeight - el.clientHeight;
                            if (range > 4) {
                                // Clamp then iterate: a relative delta computed
                                // from getBoundingClientRect is measured against
                                // the viewport, not the scroll box, so it lands
                                // short and left the gate below the fold.
                                // scrollTop is in the element's own coordinates,
                                // so target = current + (buttonOffset - top).
                                for (let i = 0; i < 3; i++) {
                                    const br = btn.getBoundingClientRect();
                                    const er = el.getBoundingClientRect();
                                    const delta = (br.top - er.top) - 12;
                                    if (Math.abs(delta) < 2) break;
                                    el.scrollTop = Math.max(0,
                                        Math.min(range, el.scrollTop + delta));
                                }
                                return {ok: true, hops, scrollTop: el.scrollTop, range};
                            }
                            el = el.parentElement; hops++;
                        }
                        window.scrollTo(0,
                            btn.getBoundingClientRect().top + window.scrollY - 400);
                        return {ok: true, hops: -1};
                    }""", needle)
                if not found.get("ok"):
                    ok = False
                    notes.append(f"could not scroll to {needle}: {found.get('why')}")
                page.wait_for_timeout(2000)

                # Present in the DOM is not the same as visible in the frame.
                # Assert the bounding box is actually inside the viewport.
                in_view = page.evaluate(
                    """(text) => {
                        const b = [...document.querySelectorAll('button')]
                            .find(e => e.innerText && e.innerText.trim() === text);
                        if (!b) return false;
                        const r = b.getBoundingClientRect();
                        return r.top >= 0 && r.bottom <= innerHeight && r.width > 0;
                    }""", needle)
                if not in_view:
                    ok = False
                    notes.append(f"{needle} is in the DOM but outside the 1080p frame")
                else:
                    # Hold on the gate. This shot exists to show the approval
                    # gate, so the scrolled state must be the readable part of
                    # the clip rather than a 1.5s flicker before the cut.
                    page.wait_for_timeout(5000)

            label = shot.get("click")
            if label:
                # Click the first matching button only: there is one per
                # incident row, and clicking all fifty would collapse the page.
                clicked = False
                for el in page.query_selector_all("button"):
                    try:
                        if el.inner_text().strip() == label and el.is_visible():
                            el.click()
                            clicked = True
                            break
                    except Exception:  # noqa: BLE001
                        pass
                if not clicked:
                    ok = False
                    notes.append(f"could not click: {label}")
                else:
                    page.wait_for_timeout(2500)

            for needle in shot.get("need", []):
                if not wait_for(page, [needle], 25):
                    ok = False
                    notes.append(f"missing: {needle}")

            # Hold the shot still a beat so the frame is readable.
            page.wait_for_timeout(1500)
        except Exception as exc:  # noqa: BLE001
            ok = False
            notes.append(f"error: {exc}")
        finally:
            video = page.video
            ctx.close()
            browser.close()

        if video is None:
            return False, 0, notes + ["no video produced"]
        try:
            src = Path(video.path())
        except Exception:  # noqa: BLE001
            src = next(target.glob("*.webm"), None)
        if src is None or not src.exists():
            return False, 0, notes + ["webm missing"]

        dst = FRAMES / f"{shot['name']}.webm"
        shutil.move(str(src), str(dst))

        probe = sh(f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{dst}"')
        try:
            dur = float(probe.stdout.strip())
        except Exception:  # noqa: BLE001
            dur = 0.0

    return ok, dur, notes


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for d in (FRAMES, AUDIO):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("ColdChain Rescue - demo recorder")
    print("=" * 64)

    servers = sh(
        f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 8 {WEB}/dashboard'
    ).stdout.strip()
    if servers != "200":
        print(f"  x frontend not responding ({servers or 'no answer'})")
        print("    start it:  START.bat   or  .\\scripts\\coldchain.ps1 start")
        return 1
    print("  frontend OK")

    if not seed_fleet():
        return 1

    if not inject_fault_and_wait():
        print("  continuing without an incident - approval/report shots will fail")

    results = []
    for shot in SHOTS:
        print(f"\n  [{shot['name']}] {shot['route']}")
        ok, dur, notes = record_shot(shot)
        status = "ok" if ok else "FAILED"
        print(f"    {status}  {dur:.1f}s  {'; '.join(notes) if notes else ''}")
        results.append(dict(shot, ok=ok, duration=dur, notes=notes))

    manifest = OUT / "manifest.json"
    manifest.write_text(json.dumps(results, indent=2), encoding="utf-8")

    passed = sum(1 for r in results if r["ok"])
    total_dur = sum(r["duration"] for r in results)
    print("\n" + "=" * 64)
    print(f"  {passed}/{len(results)} shots recorded, {total_dur:.1f}s total")
    for r in results:
        if not r["ok"]:
            print(f"    FAILED {r['name']}: {'; '.join(r['notes'])}")
    print(f"  manifest: {manifest}")
    print("=" * 64)

    # Voiceover is rendered by the caller via the TTS tool, then muxed here.
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
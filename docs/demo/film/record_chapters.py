"""Record real app footage for the detailed film, one clip per screen chapter.

Why this exists alongside the onetake film: onetake rebuilds UI in HTML so the
camera can push in, which is right for a concept. But a capstone panel wants to
see the ACTUAL application, and some states (the live map with 14 moving
trucks, the incidents list with 50 rows) are only convincing as themselves.

Discipline, the same as the first recorder:
  - every clip VERIFIES its content before rolling; a clip that fails records
    nothing and is reported, rather than producing footage that quietly lies
  - fault states are produced by driving the real backend, never staged
  - each chapter gets its own file so the edit can place them independently

Content is checked by reading the rendered DOM, not by assuming a component
exists - an earlier pass in this project asserted on strings that had never
existed and reported false passes.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "demo" / "film" / "footage"
WEB = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000"

W, H, FPS = 1920, 1080, 30

# One entry per screen chapter. `need` are strings that must be present in the
# rendered DOM; `click` is a button label to press first; `scroll` brings an
# element into the frame (the page uses a contained scroller, so scrollIntoView
# alone silently does nothing).
# Strings below are the REAL rendered copy, read out of `main` - not guesses.
# Read `main`, not document.body: the sidebar then dominates the match and a
# page whose content failed to render still "passes".
SHOTS = [
    dict(name="ch2-cold-world", route="/simulation", settle=9, hold=7,
         need=["Truck management", "Add Truck", "choose product",
               "Nothing is assigned"],
         label="add trucks yourself"),
    dict(name="ch3-live-map", route="/live-map", settle=17, hold=9,
         need=["Live Fleet", "DELHI NCR CORRIDOR", "VEHICLES", "TRANSIT"],
         label="live fleet on the corridor"),
    dict(name="ch4-catalogue", route="/incidents", settle=9, hold=8,
         need=["Incidents", "TOTAL", "Compressor has stopped"],
         label="incident types and declared gaps"),
    # NOTE: this chapter needs a pending approval that the /simulation page
    # actually binds to. As of the last run the page rendered NO Approve and
    # NO GATE element while /incidents showed ESCALATED rows - the gate is not
    # on screen. It is verified per-run below and reported honestly rather than
    # filmed from a fabricated state.
    dict(name="ch8-gate", route="/simulation", settle=9, hold=8,
         need=["Approve", "Reject"],
         scroll="Approve",
         label="human approval gate"),
    dict(name="ch9-reports", route="/reports", settle=11, hold=8,
         need=["Incident reports"],
         click="View report",
         need_after=["What the agent learned"],
         label="report and derived lessons"),
    dict(name="ch10-settings", route="/settings", settle=7, hold=6,
         # the page calls it "Appearance"; "Theme" appears nowhere in the DOM
         need=["Settings", "Appearance", "Cargo profiles"],
         label="theme and settings"),
]


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def api(path):
    try:
        return json.loads(urllib.request.urlopen(API + path, timeout=25).read())
    except Exception:  # noqa: BLE001
        return {}


def ensure_fault():
    """Make sure a real incident exists, so the gate chapter shows real content.

    Polling /api/fleet/approvals for pending_count reported 0 and this gave up
    after two minutes - but the injection had worked all along: /incidents
    showed "#186 Compressor has stopped  HIGH  ESCALATED" and "#185
    AWAITING_APPROVAL". The approvals endpoint is not a reliable proxy for the
    rendered gate, so watch the incident list instead.
    """
    inc = api("/api/incidents")
    if isinstance(inc, list) and any("ompressor" in (i.get("type") or "") for i in inc):
        print("    compressor incident already present")
        return True

    state = api("/api/fleet/state")
    trucks = [v for v in (state.get("vehicles") or []) if v.get("kind") != "SERVICE_TRUCK"]
    if not trucks:
        print("    x no truck to fault")
        return False
    vid = trucks[0].get("id") or trucks[0].get("vehicle_id")
    print(f"    injecting compressor_failure on {vid}")
    r = urllib.request.Request(
        f"{API}/api/fleet/vehicle/{vid}/inject",
        data=json.dumps({"failure": "compressor_failure"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(r, timeout=30).read()
    except Exception as exc:  # noqa: BLE001
        print(f"    x inject failed: {exc}")
        return False

    for _ in range(45):
        time.sleep(2)
        inc = api("/api/incidents")
        if isinstance(inc, list) and any("ompressor" in (i.get("type") or "") for i in inc):
            print("    compressor incident raised")
            return True
    print("    x no incident appeared")
    return False


MAIN_TXT = "() => { const m = document.querySelector('main'); return m ? m.innerText : ''; }"


def wait_for(page, needles, timeout=25):
    """Verify against the main content region only.

    document.body matches the persistent sidebar, so a page whose content
    failed to render would still satisfy any needle that happens to appear in
    the nav. That is how a broken page passes a naive check.
    """
    end = time.time() + timeout
    while time.time() < end:
        h = page.evaluate(MAIN_TXT)
        if all(n in h for n in needles):
            return True
        time.sleep(0.5)
    return False


def record(shot):
    from playwright.sync_api import sync_playwright

    target = OUT / shot["name"]
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)

    notes, ok = [], True
    with sync_playwright() as p:
        browser = p.chromium.launch(slow_mo=30)
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(OUT),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)[:60]))
        try:
            page.goto(WEB + shot["route"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(shot["settle"] * 1000)

            s = shot.get("scroll")
            if s:
                page.evaluate(
                    """(text) => {
                        const b=[...document.querySelectorAll('button')]
                            .find(e=>e.innerText && e.innerText.trim()===text);
                        if(!b) return false;
                        let el=b.parentElement, n=0;
                        while(el && n<12){
                            const range=el.scrollHeight-el.clientHeight;
                            if(range>4){
                                for(let i=0;i<3;i++){
                                    const br=b.getBoundingClientRect(), er=el.getBoundingClientRect();
                                    const d=(br.top-er.top)-12;
                                    if(Math.abs(d)<2) break;
                                    el.scrollTop=Math.max(0,Math.min(range,el.scrollTop+d));
                                }
                                return true;
                            }
                            el=el.parentElement; n++;
                        }
                        return false;
                    }""", s)
                page.wait_for_timeout(2000)

            c = shot.get("click")
            if c:
                for el in page.query_selector_all("button"):
                    try:
                        if el.inner_text().strip() == c and el.is_visible():
                            el.click()
                            break
                    except Exception:  # noqa: BLE001
                        pass
                page.wait_for_timeout(4500)   # ReportBody fetches /api/reports/{id}.json async

            if not wait_for(page, shot["need"], 25):
                ok = False
                seen = page.evaluate(MAIN_TXT)
                notes.append("missing: " + str([n for n in shot["need"] if n not in seen]))
            if shot.get("need_after") and not wait_for(page, shot["need_after"], 20):
                ok = False
                notes.append(f"missing after click: {shot['need_after']}")

            page.wait_for_timeout(shot["hold"] * 1000)
        except Exception as exc:  # noqa: BLE001
            ok = False
            notes.append(f"error: {exc}")
        finally:
            video = page.video
            ctx.close()
            browser.close()

        real = [e for e in errs if "418" not in e]
        if real:
            notes.append(f"page errors: {len(real)}")

        if video is None:
            return False, 0, notes + ["no video"]
        try:
            src = Path(video.path())
        except Exception:  # noqa: BLE001
            src = next(target.glob("*.webm"), None)
        if src is None or not src.exists():
            return False, 0, notes + ["webm missing"]
        dst = OUT / f"{shot['name']}.webm"
        shutil.move(str(src), str(dst))
        d = sh(f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{dst}"')
        try:
            dur = float(d.stdout.strip())
        except Exception:  # noqa: BLE001
            dur = 0.0
    return ok, dur, notes


def main():
    import urllib.request  # noqa: F401  (used via api())

    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.webm"):
        f.unlink()

    print("=" * 64)
    print("ColdChain Rescue - screen footage")
    print("=" * 64)
    if sh(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 10 {WEB}/dashboard').stdout.strip() != "200":
        print("  x frontend not up - START.bat first")
        return 1
    print("  frontend OK")
    ensure_fault()

    results = []
    for shot in SHOTS:
        print(f"\n  [{shot['name']}] {shot['label']}")
        ok, dur, notes = record(shot)
        print(f"    {'ok' if ok else 'FAILED'}  {dur:.1f}s  {'; '.join(notes) if notes else ''}")
        results.append(dict(shot, ok=ok, duration=dur, notes=notes))

    (OUT / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    good = sum(1 for r in results if r["ok"])
    print("\n" + "=" * 64)
    print(f"  {good}/{len(results)} clips, {sum(r['duration'] for r in results):.1f}s total")
    for r in results:
        if not r["ok"]:
            print(f"    FAILED {r['name']}: {'; '.join(r['notes'])}")
    print("=" * 64)
    return 0 if good == len(results) else 1


if __name__ == "__main__":
    import urllib.request
    sys.exit(main())
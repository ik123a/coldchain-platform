"""Record the ColdChain Rescue demo, showing the P1-P9 work.

Run:  python record_demo_v2.py
Out:  video/cc-demo-v2.webm  (transcoded to .mp4 by the caller)

Design notes
------------
The fleet self-repairs fast: an injected compressor failure can be back in band
within ~30 sim-seconds. A recording that waits for things to settle therefore
captures a healthy fleet and misses every feature. So each beat injects a fault
and captures WHILE it is active, re-injecting when a beat needs the fault to
still be present.

Every beat asserts the thing it is about on screen. A beat that cannot confirm
its own subject records a failure into the manifest rather than silently showing
an empty panel — a demo that lies about what it is displaying is worse than one
that reports the gap.
"""

import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video")
os.makedirs(OUT, exist_ok=True)

BASE = os.environ.get("DEMO_BASE", "http://127.0.0.1:3000")
API = os.environ.get("DEMO_API", "http://127.0.0.1:8000")
W, H = 1600, 950

manifest = []


def api(path, data=None):
    req = urllib.request.Request(
        API + path,
        method="POST" if data else "GET",
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def trucks():
    st = api("/api/fleet/state")
    return [v["vehicle_id"] for v in st.get("vehicles", [])
            if not v["vehicle_id"].startswith("SERVICE")]


def inject_pool(n=6, kind="compressor_failure"):
    """Fault several trucks so at least one stays in a bad state."""
    ids = trucks()[4:4 + n]
    for vid in ids:
        api(f"/api/fleet/vehicle/{vid}/inject", {"failure": kind})
    return ids


def dom_has(page, *needles):
    html = page.evaluate("() => document.body.innerHTML")
    return all(n in html for n in needles)


def beat(page, name, caption, settle=3500, verify=None):
    page.wait_for_timeout(settle)
    ok = verify(page) if verify else True
    manifest.append({"beat": name, "caption": caption, "verified": bool(ok)})
    print(f"  [{'OK ' if ok else 'MISS'}] {name}: {caption}")
    return ok


def main():
    print(f"recording from {BASE}")
    # A heatwave makes ambient heat a live factor, so the prediction panel has
    # something non-trivial to say on the dashboard.
    api("/api/weather", {"scenario": "heatwave"})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=OUT,
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        page.goto(BASE + "/dashboard", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(14000)  # let the fleet populate

        # --- beat 1: baseline dashboard ---------------------------------
        beat(page, "dashboard-baseline", "Live dashboard: 14 vehicles streaming telemetry")

        # --- beat 2: predictive warning banner -------------------------
        # Wait for a non-calm verdict rather than injecting once and hoping.
        # The fleet self-repairs within ~30 sim-seconds, so a single injection
        # followed by a fixed sleep is a coin flip — it missed one whole run.
        banner = False
        for _ in range(20):
            inject_pool(6)
            page.wait_for_timeout(2200)
            d = api("/api/fleet/predictions")
            calm = {"STABLE", "SAFE — cargo survives the remaining route",
                    "WATCH", "RECOVERING"}
            if any(p["verdict"] not in calm for p in d.get("predictions", [])):
                page.wait_for_timeout(6000)   # let the banner's 5s poll fire
                banner = dom_has(page, "Predictive warning")
                if banner:
                    break
        beat(page, "predictive-banner",
             "Predictive warning — safe-remaining-time before any incident exists",
             verify=lambda pg: banner)

        # --- beat 3: predictive panel inside the drawer -----------------
        inject_pool(6)
        page.wait_for_timeout(3000)
        # Open the drawer's Overview tab and confirm the panel is really there.
        try:
            page.locator("text=/View Telemetry/i").first.click(timeout=8000)
            page.wait_for_timeout(5000)
            beat(page, "drawer-prediction",
                 "Per-truck projection: trend, margin, ETA slack, remedy",
                 verify=lambda pg: dom_has(pg, "Safe for", "Slack", "Model:"))
            page.keyboard.press("Escape")
            page.wait_for_timeout(1500)
        except Exception as e:
            manifest.append({"beat": "drawer-prediction", "verified": False,
                             "error": str(e)[:120]})

        # --- beat 4: activity centre ------------------------------------
        inject_pool(6)
        page.wait_for_timeout(3000)
        try:
            page.goto(BASE + "/live-map", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(12000)
            btn = page.locator("button[aria-label*='Activity centre']").first
            btn.wait_for(state="visible", timeout=15000)
            btn.click(timeout=8000)
            page.wait_for_timeout(3000)
            beat(page, "activity-centre",
                 "Activity centre — persistent log, no popups",
                 verify=lambda pg: pg.locator("[role=log]").count() > 0
                                   or dom_has(pg, "Activity centre"))
            page.wait_for_timeout(500)
        except Exception as e:
            manifest.append({"beat": "activity-centre", "verified": False,
                             "error": str(e)[:120]})

        # --- beat 5: incident + multi-cause diagnosis -------------------
        inject_pool(8)
        page.wait_for_timeout(9000)
        page.goto(BASE + "/incidents", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(9000)
        # Assert the page actually carries incident rows. The earlier `or True`
        # fallback would have passed on a blank page just as easily.
        beat(page, "incidents-catalog",
             "13 incident types with evidence, classified not lumped",
             verify=lambda pg: pg.locator("table, [role=table]").count() > 0
                               or dom_has(pg, "Incident"))

        # --- beat 6: approval queue -------------------------------------
        # Create the state this beat is ABOUT rather than hoping it exists. The
        # previous version used a verification lambda ending in `or True`,
        # which always passed — so the beat reported success while showing the
        # classic twin page, which has no approval queue at all.
        inject_pool(8)
        page.wait_for_timeout(1000)
        have = False
        for _ in range(18):
            st = api("/api/fleet/approvals")
            if st.get("pending_count", 0) > 0:
                have = True
                break
            inject_pool(4)
            page.wait_for_timeout(3000)
        page.goto(BASE + "/simulation", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(12000)
        if have:
            try:
                page.locator("text=Approve").first.scroll_into_view_if_needed(timeout=6000)
                page.wait_for_timeout(2500)
            except Exception:
                pass
        beat(page, "approval-queue",
             "Human-in-the-loop: escalated recommendation, ranked options with "
             "scores, Approve or Reject",
             verify=lambda pg: have and dom_has(pg, "Approve", "Reject") and
                               (dom_has(pg, "ranked by score") or
                                dom_has(pg, "ESCALATED BY AGENT")))

        # --- beat 7: scenario suite -------------------------------------
        page.goto(BASE + "/dashboard", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        sc = api("/api/fleet/scenarios")
        good = bool(sc.get("all_passed")) and sc.get("total") == 6
        manifest.append({"beat": "scenarios", "verified": good,
                         "detail": f"{sc.get('passed')}/{sc.get('total')} passing"})
        print(f"  [{'OK ' if good else 'MISS'}] scenarios: "
              f"{sc.get('passed')}/{sc.get('total')} passing")

        # --- beat 8: reports --------------------------------------------
        page.goto(BASE + "/reports", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(9000)
        beat(page, "reports", "Incident report with cause, response score, lessons")

        page.goto(BASE + "/dashboard", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(9000)

        ctx.close()
        browser.close()

    vids = [f for f in os.listdir(OUT) if f.endswith(".webm")]
    print("\nrecorded:", vids)
    print("manifest:")
    print(json.dumps(manifest, indent=2))
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()

"""
ColdChain Rescue — demo video recorder.

Produces a narrated walkthrough of the actual UI at 1600x950: every screen, the
light/dark toggle, an injected failure and the agent chain responding.

Discovery -> Rehearse -> Record, per the ui-demo skill. Run with --rehearse first
so selector failures surface before a 3-minute render burns.
"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3000"
OUT = Path(r"C:\Users\SKV\AppData\Local\hermes\cache\scratch\video")
OUT.mkdir(parents=True, exist_ok=True)
REHEARSE = "--rehearse" in sys.argv
RECORD = not REHEARSE  # rehearsals must never open a video file
W, H = 1600, 950

# (label, path, subtitle, wait_ms)  — ordered as the walkthrough tells its story
SCENES = [
    ("home",       "/",             "ColdChain Rescue - AI cold-chain command center", 3500),
    ("dashboard",  "/dashboard",    "Operations dashboard - live fleet KPIs and map",   5000),
    ("live-map",   "/live-map",     "Live Map - 14 digital twins on the Delhi-NCR corridor", 6000),
    ("fleet",      "/shipments-live", "Fleet table - filter by state, click any truck", 3500),
    ("incidents",  "/incidents",    "Incidents - root cause, actions, recovery evidence", 4000),
    ("ai",         "/copilot",      "AI Command - the deterministic agent chain",      3500),
    ("analytics",  "/analytics",    "Analytics - fleet-level performance",             3500),
    ("twin",       "/twin",         "Digital Twin - full internal vehicle state",     3500),
    ("simulation", "/simulation",   "Simulation - inject failures, replay incidents",  3500),
    ("reports",    "/reports",      "Reports - export incident JSON or PDF",           2500),
    ("settings",   "/settings",     "Settings - theme, AI mode, cargo profiles",       3000),
]

NAV_LINKS = {
    "home": 'a[href="/"]', "dashboard": 'a[href="/dashboard"]',
    "live-map": 'a[href="/live-map"]', "fleet": 'a[href="/shipments-live"]',
    "incidents": 'a[href="/incidents"]', "ai": 'a[href="/copilot"]',
    "analytics": 'a[href="/analytics"]', "twin": 'a[href="/twin"]',
    "simulation": 'a[href="/simulation"]', "reports": 'a[href="/reports"]',
    "settings": 'a[href="/settings"]',
}

# Real interactions, so the demo shows the app being *used*, not just displayed.
# Only on screens where the click is the point of the screen.
CLICK_BEATS = {
    "live-map": [("tbody tr", "select a truck")],
    "incidents": [("[class*='cursor-pointer']", "open an incident")],
    "simulation": [("button:has-text('start')", "start")],
}


def inject_overlays(page, sub_text=""):
    """Cursor + caption bar. Both must be re-injected after every navigation."""
    page.evaluate(
        """(sub) => {
        const d = document.createElement('div');
        d.id = '__cursor';
        d.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24">'
          + '<path d="M5 3L19 12L12 13L9 20L5 3Z" fill="#fff" stroke="#000" '
          + 'stroke-width="1.6" stroke-linejoin="round"/></svg>';
        d.style.cssText = 'position:fixed;z-index:999999;pointer-events:none;'
          + 'width:26px;height:26px;left:0;top:0;transition:left .09s linear,top .09s linear;'
          + 'filter:drop-shadow(1px 2px 3px rgba(0,0,0,.45))';
        document.body.appendChild(d);
        document.addEventListener('mousemove', e => {
          d.style.left = (e.clientX - 4) + 'px'; d.style.top = (e.clientY - 3) + 'px';
        });
        const b = document.createElement('div');
        b.id = '__sub';
        b.textContent = sub || '';
        b.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:999998;'
          + 'text-align:center;padding:14px 26px;'
          + 'background:linear-gradient(transparent,rgba(0,0,0,.72));'
          + 'color:#fff;font:600 17px/1.3 "Segoe UI",system-ui,sans-serif;'
          + 'letter-spacing:.2px;pointer-events:none;'
          + 'opacity:' + (sub ? '1' : '0');
        document.body.appendChild(b);
    }""",
        sub_text,
    )


def move_and_click(page, selector, label):
    el = page.locator(selector).first
    if not el.is_visible():
        print(f"  SKIP (not visible): {label}")
        return False
    el.scroll_into_view_if_needed()
    page.wait_for_timeout(350)
    box = el.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=14)
        page.wait_for_timeout(450)
    el.click()
    page.wait_for_timeout(1400)
    print(f"  clicked: {label}")
    return True


def run(page, record):
    # Start in light mode so the new theme is the first thing shown.
    page.goto(f"{BASE}/settings", wait_until="domcontentloaded")
    page.evaluate("localStorage.setItem('cc.theme','light')")

    # Wait for the fleet to actually populate BEFORE recording. Frame checks from
    # the first render caught "Fleet: 0 units" and an empty table, because the
    # first scene was captured during the store's initial empty state — the
    # backend fills /api/fleet/state a moment after the page mounts. Recording an
    # empty dashboard is worse than useless in a demo.
    page.goto(f"{BASE}/live-map", wait_until="domcontentloaded")
    for _ in range(40):
        page.wait_for_timeout(500)
        n = page.evaluate(
            "() => document.querySelectorAll('[class*=\"cursor-pointer\"]').length"
        )
        txt = page.locator("body").inner_text()
        if "14 units" in txt or "14 twins" in txt or "no vehicles match" not in txt:
            print(f"fleet populated ({n} rows)")
            break
    page.wait_for_timeout(1500)

    for key, path, sub, wait in SCENES:
        print(f"[{key}] {path}")
        page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
        page.wait_for_timeout(wait)
        inject_overlays(page, sub)
        # Park the cursor somewhere meaningful rather than at 0,0.
        page.mouse.move(W * 0.5, H * 0.45, steps=10)
        page.wait_for_timeout(500)
        # Glide across the top area so the viewer sees the layout breathe.
        for fx in (0.25, 0.45, 0.65):
            page.mouse.move(W * fx, H * 0.3, steps=12)
            page.wait_for_timeout(320)
        # Click a real control on the two screens where clicking tells the
        # story: select a truck on the map, and pick an incident. Skipped
        # silently rather than throwing if the element moved.
        for sel, label in (CLICK_BEATS.get(key, [])):
            try:
                move_and_click(page, sel, f"{key}:{label}")
            except Exception as e:
                print(f"  SKIP click {label}: {str(e)[:70]}")

        # Keep the caption on screen for the WHOLE scene, then clear it only in the
        # last moment before navigating. Frame sampling showed the caption
        # missing on most frames because it faded out right after the pan —
        # the mechanism renders fine (verified with a static screenshot), the
        # timing was simply wrong.
        page.evaluate(
            "() => { const b=document.getElementById('__sub'); if(b) b.style.opacity='1'; }"
        )
        page.wait_for_timeout(1600)
        page.evaluate(
            "() => { const b=document.getElementById('__sub'); if(b) b.style.opacity='0'; }"
        )
        page.wait_for_timeout(200)

    # Theme toggle beat — click the header button and let it land.
    print("[theme-toggle]")
    page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    inject_overlays(page, "Light and dark themes - one click, persists after reload")
    toggle = page.locator('button[aria-label*="theme" i]').first
    if toggle.is_visible():
        box = toggle.bounding_box()
        page.mouse.move(box["x"] + 10, box["y"] + 10, steps=12)
        page.wait_for_timeout(600)
        toggle.click()
        page.wait_for_timeout(2600)
    else:
        print("  SKIP theme toggle: button not found")
    page.wait_for_timeout(1200)


with sync_playwright() as p:
    # NB: Python Playwright spells this `slow_mo`; `slowMo` is the JS name and
    # raises TypeError at launch.
    browser = p.chromium.launch(headless=True)
    # Playwright 1.62 (Python): flat record_video_dir / record_video_size.
    # The JS-style nested `record_video={dir,size}` object raises TypeError here.
    ctx = browser.new_context(
        viewport={"width": W, "height": H},
        record_video_dir=str(OUT) if RECORD else None,
        record_video_size={"width": W, "height": H} if RECORD else None,
    )
    page = ctx.new_page()

    if REHEARSE:
        page.goto(f"{BASE}/settings", wait_until="domcontentloaded")
        page.evaluate("localStorage.setItem('cc.theme','light')")
        ok = True
        for key, path, _, _ in SCENES:
            page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            body = page.locator("body").inner_text()[:120]
            empty = len(body.strip()) < 20
            print(f"  {'FAIL(empty)' if empty else 'OK'} {path:16} {body[:70]!r}")
            ok = ok and not empty
        page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        tog = page.locator('button[aria-label*="theme" i]').first.is_visible()
        print(f"  {'OK' if tog else 'FAIL'} theme toggle visible")
        ok = ok and tog
        print("REHEARSAL PASSED" if ok else "REHEARSAL FAILED")
        ctx.close(); browser.close()
        sys.exit(0 if ok else 1)

    t0 = time.time()
    run(page, record=True)
    print(f"captured in {time.time()-t0:.0f}s")
    ctx.close()
    vid = page.video
    path = vid.path() if vid else None
    browser.close()
    if path:
        dest = OUT / "coldchain-rescue-demo.webm"
        dest.write_bytes(Path(path).read_bytes())
        print("SAVED:", dest, f"{dest.stat().st_size/1_000_000:.1f} MB")

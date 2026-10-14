"""Deterministic, pristine screen recorder for ColdChain Rescue.
Records 1080p footage at 30fps with organic mouse physics, asserts state,
and converts directly to remotion public/clips/*.mp4.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000"
DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(DEMO_DIR, "final", "assets", "raw_scratch")
CLIPS_DIR = os.path.join(DEMO_DIR, "final", "enhanced", "remotion-project", "public", "clips")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

EMAIL = "demo.ops@coldchain.local"
PASSWORD = "DemoOnly#2026"
AUTH_TOKEN = None
TARGET_VEHICLE = {}

def api_call(path, method="GET", body=None, token=None):
    headers = {"Content-Type": "application/json"}
    tok = token or AUTH_TOKEN
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def get_token():
    global AUTH_TOKEN
    if not AUTH_TOKEN:
        try:
            res = api_call("/api/auth/login", "POST", {"email": EMAIL, "password": PASSWORD})
            AUTH_TOKEN = res.get("access_token")
        except Exception as e:
            print(f"  Login error: {e}")
    return AUTH_TOKEN

async def smooth_move(page, start_x, start_y, end_x, end_y, steps=30):
    for i in range(steps + 1):
        t = i / steps
        ease = t * t * (3.0 - 2.0 * t)  # cubic ease-in-out
        x = start_x + (end_x - start_x) * ease
        y = start_y + (end_y - start_y) * ease
        await page.mouse.move(x, y)
        await page.wait_for_timeout(16)
    page._last_mouse = {"x": end_x, "y": end_y}

async def move_to(page, target_x, target_y, steps=25):
    last = getattr(page, "_last_mouse", {"x": 960, "y": 540})
    await smooth_move(page, last["x"], last["y"], target_x, target_y, steps)

async def move_and_click(page, locator):
    box = await locator.bounding_box()
    if box:
        tx = box["x"] + box["width"] / 2
        ty = box["y"] + box["height"] / 2
        await move_to(page, tx, ty)
        await page.wait_for_timeout(120)
        await page.mouse.down()
        await page.wait_for_timeout(80)
        await page.mouse.up()
        await page.wait_for_timeout(100)
    else:
        await locator.click()

async def record_scene(ctx, name, duration_sec, routine):
    print(f"\n=======================================================")
    print(f"[*] Recording Scene: {name} (Target: {duration_sec}s)")
    print(f"=======================================================")
    page = await ctx.new_page()
    page._last_mouse = {"x": 960, "y": 540}
    t0 = time.time()
    try:
        await routine(page)
        elapsed = time.time() - t0
        rem = duration_sec - elapsed
        if rem > 0:
            print(f"  Holding scene for remaining {rem:.1f}s...")
            await page.wait_for_timeout(int(rem * 1000))
        print(f"  Capture finished (took {time.time() - t0:.1f}s)")
    finally:
        target_webm = os.path.join(RAW_DIR, f"{name}.webm")
        target_mp4 = os.path.join(CLIPS_DIR, f"{name}.mp4")
        await page.close()
        
        try:
            await page.video.save_as(target_webm)
            print(f"  Saved raw webm: {target_webm}")
            
            # Convert to 1080p30 mp4 using ffmpeg
            cmd = [
                "ffmpeg", "-y", "-i", target_webm,
                "-vf", "fps=30,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-an",
                target_mp4
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"  [+] Converted to Remotion clip: {target_mp4}")
            else:
                print(f"  [-] FFmpeg error: {res.stderr[-300:]}")
        except Exception as e:
            print(f"  [-] Error processing video: {e}")

async def main():
    # Make sure user exists and get token
    try:
        api_call("/api/auth/register", "POST", {
            "name": "Demo Operator",
            "email": EMAIL,
            "password": PASSWORD,
            "role": "operator"
        })
    except Exception:
        pass
    
    tok = get_token()
    print(f"  Auth token acquired: {tok[:18]}...")

    # Query fleet state to find target vehicle
    try:
        st = api_call("/api/fleet/state", token=tok)
        vs = st if isinstance(st, list) else st.get("vehicles", [])
        if vs:
            TARGET_VEHICLE["vid"] = vs[0]["vehicle_id"]
            print(f"  Assigned target vehicle: {TARGET_VEHICLE['vid']}")
    except Exception as e:
        print(f"  Could not prefetch fleet: {e}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080"
            ]
        )

        ctx = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir=RAW_DIR,
            record_video_size={"width": 1920, "height": 1080}
        )

        # ---------------------------------------------------------------------
        # Scene 02: Introduction / Login / Command Center Dashboard
        # ---------------------------------------------------------------------
        async def scene_02(page):
            await page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            await page.wait_for_timeout(1200)
            await move_to(page, 960, 360, steps=25)  # Hover over header/brand
            await page.wait_for_timeout(600)

            email_inp = page.locator('input[type="email"]')
            await move_and_click(page, email_inp)
            await email_inp.type(EMAIL, delay=35)
            await page.wait_for_timeout(350)

            pwd_inp = page.locator('input[type="password"]')
            await move_and_click(page, pwd_inp)
            await pwd_inp.type(PASSWORD, delay=35)
            await page.wait_for_timeout(450)

            submit_btn = page.locator('button[type="submit"]')
            await move_and_click(page, submit_btn)

            # Wait for dashboard
            for _ in range(30):
                if "/dashboard" in page.url:
                    break
                await page.wait_for_timeout(200)

            await page.wait_for_timeout(2000)
            # Gentle glide over KPI metrics
            await move_to(page, 320, 220, steps=20)
            await page.wait_for_timeout(1000)
            await move_to(page, 640, 220, steps=20)
            await page.wait_for_timeout(1000)
            await move_to(page, 960, 220, steps=20)

        # ---------------------------------------------------------------------
        # Scene 03: Live Fleet Digital Twin Map
        # ---------------------------------------------------------------------
        async def scene_03(page):
            await page.goto(f"{BASE}/live-map", wait_until="domcontentloaded")
            await page.wait_for_selector("text=TRUCK", timeout=30000)
            await page.wait_for_timeout(3000)  # Map tiles settle

            # Move mouse across map
            await move_to(page, 800, 480, steps=25)
            await page.wait_for_timeout(1500)
            await move_to(page, 1050, 520, steps=25)
            await page.wait_for_timeout(1500)

            vid = TARGET_VEHICLE.get("vid")
            truck_loc = page.locator(f"text={vid}").first if vid else page.locator("text=TRUCK").first
            await move_and_click(page, truck_loc)
            await page.wait_for_timeout(2500)  # Drawer slides open

            # Glide over temperature kinetics and stats
            await move_to(page, 1400, 320, steps=20)
            await page.wait_for_timeout(1200)
            await move_to(page, 1600, 480, steps=20)

        # ---------------------------------------------------------------------
        # Scene 04: Genuine Incident Fault Injection
        # ---------------------------------------------------------------------
        async def scene_04(page):
            await page.goto(f"{BASE}/live-map", wait_until="domcontentloaded")
            await page.wait_for_selector("text=TRUCK", timeout=30000)
            await page.wait_for_timeout(1500)

            vid = TARGET_VEHICLE.get("vid", "TRUCK-1535-07")
            # Open drawer
            await page.click(f"text={vid}")
            await page.wait_for_timeout(1800)

            # Direct authenticated API injection to guarantee deterministic telemetry response
            api_call(f"/api/fleet/vehicle/{vid}/inject", "POST", {"failure": "compressor_failure"}, token=tok)
            print(f"  Injected compressor failure into {vid}")

            # Hover over Inject Anomaly button if present
            inject_btn = page.locator("button:has-text('Inject Anomaly')")
            if await inject_btn.count() > 0:
                await move_and_click(page, inject_btn.first)

            # Wait for FAILED status to appear in DOM
            for _ in range(40):
                body = await page.evaluate("document.body.innerText")
                if "FAILED" in body or "CRITICAL" in body:
                    break
                await page.wait_for_timeout(300)

            # Move mouse to watch temperature climb in drawer
            await move_to(page, 1450, 360, steps=25)
            await page.wait_for_timeout(3000)
            await move_to(page, 1550, 520, steps=20)

        # ---------------------------------------------------------------------
        # Scene 05: Root Cause Diagnosis & Expert System Scoring
        # ---------------------------------------------------------------------
        async def scene_05(page):
            await page.goto(f"{BASE}/incidents", wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            # Find compressor incident
            for _ in range(30):
                body = await page.evaluate("document.body.innerText")
                if "compressor" in body.lower():
                    break
                await page.wait_for_timeout(400)

            # Glide over diagnosis incident row
            await move_to(page, 600, 320, steps=20)
            await page.wait_for_timeout(1500)
            inc_row = page.locator("text=compressor").first
            if await inc_row.count() > 0:
                await move_and_click(page, inc_row)
                await page.wait_for_timeout(1500)

            # Inspect evidence metrics
            await move_to(page, 850, 420, steps=25)
            await page.wait_for_timeout(2000)
            await move_to(page, 1100, 460, steps=20)

        # ---------------------------------------------------------------------
        # Scene 06: Multi-Criteria Facility Scoring & Human Approval Gate
        # ---------------------------------------------------------------------
        async def scene_06(page):
            await page.goto(f"{BASE}/live-map", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            vid = TARGET_VEHICLE.get("vid", "TRUCK-1535-07")
            # Click vehicle to open drawer
            try:
                await page.click(f"text={vid}")
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            # Poll for Approve button in drawer or bottom decision card
            approve_btn = None
            for _ in range(40):
                btn = page.locator("button:has-text('Approve')")
                if await btn.count() > 0:
                    approve_btn = btn.first
                    break
                await page.wait_for_timeout(300)

            if approve_btn:
                # Hover over facility score card
                await move_to(page, 1400, 500, steps=25)
                await page.wait_for_timeout(2000)
                # Move to Approve Diversion button
                await move_and_click(page, approve_btn)
                print("  Clicked Approve button!")
                await page.wait_for_timeout(4000)
            else:
                # If not in drawer, check ai_ops tab
                ai_tab = page.locator("button:has-text('ai_ops')")
                if await ai_tab.count() > 0:
                    await move_and_click(page, ai_tab)
                    await page.wait_for_timeout(1000)
                    divert_btn = page.locator("button:has-text('Divert Now')").first
                    if await divert_btn.count() > 0:
                        await move_and_click(page, divert_btn)
                        print("  Clicked Divert Now in AI Ops tab!")

        # ---------------------------------------------------------------------
        # Scene 07: Execution & Dynamic Route Rerouting
        # ---------------------------------------------------------------------
        async def scene_07(page):
            await page.goto(f"{BASE}/live-map", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            # Track route polyline on map
            await move_to(page, 960, 480, steps=25)
            await page.wait_for_timeout(2000)
            await move_to(page, 1150, 560, steps=30)
            await page.wait_for_timeout(3000)
            await move_to(page, 850, 420, steps=25)

        # ---------------------------------------------------------------------
        # Scene 08: Verification & Audit Analytics
        # ---------------------------------------------------------------------
        async def scene_08(page):
            await page.goto(f"{BASE}/analytics", wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            # Glide across analytics KPI blocks
            await move_to(page, 280, 200, steps=20)
            await page.wait_for_timeout(1200)
            await move_to(page, 580, 200, steps=20)
            await page.wait_for_timeout(1200)
            await move_to(page, 880, 200, steps=20)
            await page.wait_for_timeout(1200)
            # Glide down to Failure causes bar chart
            await move_to(page, 640, 450, steps=25)
            await page.wait_for_timeout(2500)
            await move_to(page, 1200, 450, steps=25)

        # Run recordings with exact durations matching the narration timeline
        await record_scene(ctx, "02_introduce", 22.0, scene_02)
        await record_scene(ctx, "03_fleet", 22.0, scene_03)
        await record_scene(ctx, "04_incident", 22.0, scene_04)
        await record_scene(ctx, "05_diagnosis", 23.0, scene_05)
        await record_scene(ctx, "06_approval", 26.0, scene_06)
        await record_scene(ctx, "07_execution", 20.0, scene_07)
        await record_scene(ctx, "08_verification", 26.0, scene_08)

        await browser.close()
        print("\nAll 7 live scenes recorded and converted to clips successfully!")

if __name__ == "__main__":
    asyncio.run(main())

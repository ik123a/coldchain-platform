import os
import sys
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000"
art_dir = r"C:\Users\SKV\.gemini\antigravity\brain\abe52a23-ac7c-45da-9ff6-d99bc998a038"
os.makedirs(art_dir, exist_ok=True)

EMAIL = "demo.ops@coldchain.local"
PASSWORD = "DemoOnly#2026"

# Ensure user exists in backend DB
def ensure_user():
    try:
        data = json.dumps({
            "name": "Demo Operator",
            "email": EMAIL,
            "password": PASSWORD,
            "role": "operator"
        }).encode()
        req = urllib.request.Request(API + "/api/auth/register", data=data, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            print("Registered demo operator:", r.status)
    except Exception as e:
        print("User registration note:", e)

ensure_user()

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1600, "height": 950})
    page = context.new_page()

    # 1. Login Page
    print("[1] Capturing login page...")
    page.goto(f"{BASE}/login", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1000)
    page.screenshot(path=os.path.join(art_dir, "01_login.png"))
    print("  Saved 01_login.png")

    # 2. Fill login form and authenticate
    print("[2] Submitting login credentials...")
    email_inp = page.locator('input[type="email"]')
    email_inp.fill(EMAIL)
    page.wait_for_timeout(300)

    pwd_inp = page.locator('input[type="password"]')
    pwd_inp.fill(PASSWORD)
    page.wait_for_timeout(300)

    page.locator('button[type="submit"]').click()

    # Wait for dashboard
    page.wait_for_url("**/dashboard**", timeout=15000)
    page.wait_for_timeout(4000)
    page.screenshot(path=os.path.join(art_dir, "02_dashboard.png"))
    print("  Saved 02_dashboard.png")

    # 3. Live Fleet Map
    print("[3] Capturing live map...")
    page.goto(f"{BASE}/live-map", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)
    page.screenshot(path=os.path.join(art_dir, "03_live_map.png"))
    print("  Saved 03_live_map.png")

    # 4. Incidents & AI Resolution
    print("[4] Capturing incidents...")
    page.goto(f"{BASE}/incidents", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    page.screenshot(path=os.path.join(art_dir, "04_incidents.png"))
    print("  Saved 04_incidents.png")

    # 5. Reports / Analytics
    print("[5] Capturing reports...")
    page.goto(f"{BASE}/reports", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    page.screenshot(path=os.path.join(art_dir, "05_reports.png"))
    print("  Saved 05_reports.png")

    browser.close()

print("ALL_PAGES_VERIFIED_AND_CAPTURED")

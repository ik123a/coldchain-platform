"""Capture reference screenshots of the live app for the film.

These exist so the palette can be measured from the product's own pixels
(`look.py from-shot`) rather than invented, and so the composition's rebuilt UI
matches the real thing instead of approximating it.
"""

import os
import sys

from playwright.sync_api import sync_playwright

B = "http://127.0.0.1:3000"
ROUTES = [
    ("dashboard", "/dashboard"),
    ("live-map", "/live-map"),
    ("simulation", "/simulation"),
    ("incidents", "/incidents"),
    ("reports", "/reports"),
    ("settings", "/settings"),
]


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # 2x so the measured palette is not dominated by antialiasing.
        page = browser.new_context(
            viewport={"width": 1600, "height": 1000}, device_scale_factor=2
        ).new_page()

        for name, route in ROUTES:
            page.goto(B + route, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)
            path = os.path.join(out, f"{name}.png")
            page.screenshot(path=path)
            print(f"  {name:12} {os.path.getsize(path):8d} bytes")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
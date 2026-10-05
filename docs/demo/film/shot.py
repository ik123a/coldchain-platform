import asyncio, sys
from playwright.async_api import async_playwright
async def main(t, out):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width":1920,"height":1080}, device_scale_factor=1)).new_page()
        await pg.goto("file:///" + __import__("os").path.abspath("comp.html").replace("\\","/"))
        await pg.evaluate("window.__ready")
        await pg.evaluate(f"window.__seek({t})")
        await pg.wait_for_timeout(350)
        await pg.screenshot(path=out)
        await b.close()
asyncio.run(main(float(sys.argv[1]), sys.argv[2]))

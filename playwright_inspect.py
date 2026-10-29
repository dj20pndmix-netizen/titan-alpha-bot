import asyncio
from playwright.async_api import async_playwright
import json

async def run():
    async with async_playwright() as p:
        # Launch chromium
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Capture web sockets
        page.on("websocket", lambda ws: print(f"[WS OPENED]: {ws.url}"))

        # Capture API calls
        async def on_response(res):
            if "/api/v1/" in res.url:
                try:
                    data = await res.text()
                    print(f"\n[API {res.status}] {res.url}")
                    print(f"Data: {data[:200]}")
                except Exception:
                    pass

        page.on("response", on_response)

        print("[*] Navigating to https://mmgpredictions.com/demo ...")
        await page.goto("https://mmgpredictions.com/demo", wait_until="networkidle", timeout=25000)
        
        await asyncio.sleep(5)
        print(f"[*] Current URL: {page.url}")
        
        # Take a screenshot to inspect
        await page.screenshot(path=r"c:\my strategy\demo_page.png")
        print("[*] Screenshot saved to demo_page.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

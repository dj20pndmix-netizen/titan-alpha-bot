import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Monitor all websockets
        page.on("websocket", lambda ws: print(f"[WEBSOCKET CONNECTED]: {ws.url}"))
        
        # Monitor all failed requests
        page.on("requestfailed", lambda req: print(f"[REQ FAILED]: {req.method} {req.url} - {req.failure}"))
        
        # Monitor all API requests
        async def on_resp(res):
            if "/api/v1/" in res.url:
                try:
                    txt = await res.text()
                    print(f"[API {res.status}] {res.url} -> {txt[:120]}")
                except:
                    pass
        page.on("response", on_resp)

        print("[*] Navigating to /demo to get authenticated...")
        await page.goto("https://mmgpredictions.com/demo", wait_until="networkidle")
        await asyncio.sleep(2)

        print("[*] Navigating to /trade?family=even_odd ...")
        await page.goto("https://mmgpredictions.com/trade?family=even_odd", wait_until="networkidle")
        
        # Wait 10 seconds to observe ticks streaming
        print("[*] Observing page events for 10s...")
        await asyncio.sleep(10)

        # Check DOM for live price or ticks
        price_elem = await page.query_selector("text=$") or await page.query_selector("[data-testid*='price']")
        content = await page.content()
        print("Page title:", await page.title())

        # Screenshot the trade dashboard
        await page.screenshot(path=r"c:\my strategy\trade_page.png")
        print("[*] Screenshot saved to trade_page.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

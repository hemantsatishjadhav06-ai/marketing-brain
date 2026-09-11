"""Capture the client and operator experience on production for the CTO report."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
BASE = os.environ.get("MB_BASE", "https://marketing-brain-production-1f88.up.railway.app")
EMAIL = os.environ["MB_ADMIN_EMAIL"]; PW = open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
OUT = os.path.join(os.path.dirname(__file__), "shots"); os.makedirs(OUT, exist_ok=True)
BID = sys.argv[1] if len(sys.argv) > 1 else ""

async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        ctx = await br.new_context(viewport={"width": 1380, "height": 900}, device_scale_factor=1)
        page = await ctx.new_page()
        # login via API, seed token for both apps
        r = await page.request.post(f"{BASE}/api/auth/login", data=json.dumps({"email": EMAIL, "password": PW}), headers={"content-type": "application/json"})
        tok = (await r.json())["token"]
        await page.goto(f"{BASE}/operator.html")
        await page.evaluate(f"localStorage.setItem('mb_token','{tok}')")
        shots = []
        async def shot(name, wait=2500):
            await page.wait_for_timeout(wait); f = os.path.join(OUT, name + ".png"); await page.screenshot(path=f, full_page=True); shots.append(name); print("shot", name, flush=True)
        # console views
        await page.goto(f"{BASE}/operator.html"); await page.wait_for_timeout(3000); await shot("01-portfolio")
        for v in ("approvals", "cycles", "clients"):
            await page.evaluate(f"go('{v}')"); await shot(f"02-{v}")
        await page.evaluate("go('connections')"); await shot("03-connections-hub", 3500)
        await page.evaluate("go('growth')"); await page.wait_for_timeout(2500)
        if BID:
            await page.evaluate(f"growthPick('{BID}')"); await page.wait_for_timeout(2000)
        await page.evaluate("growthTab('meta')"); await page.wait_for_timeout(3000)
        # open the most recent Meta plan
        try:
            await page.click("text=Open plan", timeout=8000); await shot("04-meta-media-plan", 3000)
        except Exception as e:
            print("no plan to open:", e); await shot("04-meta-ads-panel")
        await page.evaluate("growthTab('google')"); await page.wait_for_timeout(3000)
        try:
            await page.click("text=Open plan", timeout=8000); await shot("05-google-search-plan", 3000)
        except Exception:
            await shot("05-google-ads-panel")
        await page.evaluate("growthTab('seo')"); await shot("06-seo-panel", 1500)
        await page.evaluate("go('agency')"); await shot("07-agency-settings")
        # brand app (client experience)
        await page.goto(f"{BASE}/"); await page.evaluate(f"localStorage.setItem('mb_token','{tok}')"); await page.goto(f"{BASE}/"); await page.wait_for_timeout(3500)
        await shot("10-client-dashboard")
        if BID:
            await page.evaluate(f"openBrand('{BID}')"); await page.wait_for_timeout(3500); await shot("11-client-brand-create")
            for tab, name in (("board", "12-client-content-board"), ("ideas", "13-client-ideas"), ("calendar", "14-client-calendar"), ("ads", "15-client-paid-ads"), ("connectors", "16-client-connections"), ("memory", "17-client-memory")):
                await page.evaluate(f"state.tab='{tab}';renderBrand()"); await page.wait_for_timeout(3500)
                if tab == "ads":
                    try:
                        await page.click("text=Open plan", timeout=6000); await page.wait_for_timeout(2500)
                    except Exception:
                        pass
                await shot(name, 800)
        # marketing site
        await page.goto(f"{BASE}/site/"); await shot("20-landing-site", 2500)
        await br.close()
        json.dump(shots, open(os.path.join(OUT, "index.json"), "w"))

asyncio.run(main())

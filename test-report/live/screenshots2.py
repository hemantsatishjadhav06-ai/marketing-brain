"""Round-2 screenshots: calendar month view + Airtable card, Mail tab, design QA panel."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
BASE = "https://marketing-brain-production-1f88.up.railway.app"
EMAIL = os.environ["MB_ADMIN_EMAIL"]; PW = open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots"); os.makedirs(OUT, exist_ok=True)
BID = sys.argv[1]; CID = sys.argv[2] if len(sys.argv) > 2 else ""

async def main():
    import httpx
    http = httpx.Client(timeout=120, follow_redirects=True)
    async with async_playwright() as p:
        br = await p.chromium.launch(); ctx = await br.new_context(viewport={"width": 1380, "height": 900}); page = await ctx.new_page()
        async def relay(route, request):
            try:
                hdrs = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "accept-encoding")}
                body = request.post_data_buffer if request.method in ("POST", "PUT", "PATCH", "DELETE") else None
                r = await asyncio.to_thread(http.request, request.method, request.url, headers=hdrs, content=body)
                await route.fulfill(status=r.status_code, headers={k: v for k, v in r.headers.items() if k.lower() in ("content-type", "cache-control")}, body=r.content)
            except Exception as e:
                await route.fulfill(status=502, body=str(e))
        await page.route("**/*", relay)
        tok = http.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PW}).json()["token"]
        async def shot(name, wait=2500):
            await page.wait_for_timeout(wait); await page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=True); print("shot", name, flush=True)
        await page.goto(f"{BASE}/"); await page.evaluate(f"localStorage.setItem('mb_token','{tok}')"); await page.goto(f"{BASE}/"); await page.wait_for_timeout(3000)
        await page.evaluate(f"openBrand('{BID}')"); await page.wait_for_timeout(3000)
        await page.evaluate("state.tab='calendar';renderBrand()"); await shot("30-client-calendar-month-airtable", 3500)
        await page.evaluate("state.tab='mail';renderBrand()"); await shot("31-client-mail-campaigns", 4000)
        try:
            await page.click("text=Open", timeout=6000); await shot("32-client-mail-campaign-preview", 4500)
        except Exception as e:
            print("no campaign open:", e)
        await page.evaluate("MailUI.go('sequences')"); await shot("33-client-mail-sequences", 3000)
        await page.evaluate("MailUI.go('contacts')"); await shot("34-client-mail-contacts", 3000)
        if CID:
            await page.evaluate("state.tab='board';renderBrand()"); await page.wait_for_timeout(3000)
            await page.evaluate(f"openReview('{CID}')"); await page.wait_for_timeout(3500)
            await page.screenshot(path=os.path.join(OUT, "35-client-design-qa-review.png"), full_page=False); print("shot 35")
            try:
                el = await page.query_selector("#drawerPanel")
                if el:
                    await el.screenshot(path=os.path.join(OUT, "35-client-design-qa-review.png")); print("shot 35 (drawer)")
            except Exception as e:
                print("drawer shot:", e)
        await page.goto(f"{BASE}/operator.html"); await page.evaluate(f"localStorage.setItem('mb_token','{tok}')"); await page.goto(f"{BASE}/operator.html"); await page.wait_for_timeout(3000)
        await page.evaluate("go('growth')"); await page.wait_for_timeout(2500); await page.evaluate(f"growthPick('{BID}')"); await page.wait_for_timeout(2000)
        await page.evaluate("growthTab('mail')"); await shot("36-console-mailer", 4000)
        await page.evaluate("go('connections')"); await page.wait_for_timeout(3000)
        try:
            await page.click("#ch-smtp summary:has-text('Setup steps')", timeout=4000)
        except Exception:
            pass
        await shot("37-console-connections-smtp-airtable", 1500)
        await br.close()
asyncio.run(main())

import asyncio, os, json
from playwright.async_api import async_playwright
import httpx
BASE="https://marketing-brain-production-1f88.up.railway.app"
EMAIL=os.environ["MB_ADMIN_EMAIL"]; PW=open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
BID="af4c0bd6fbbd"; CID="bbe9bcd7c2be"; OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"shots"); os.makedirs(OUT,exist_ok=True)
async def main():
    http=httpx.Client(timeout=120,follow_redirects=True)
    async with async_playwright() as p:
        br=await p.chromium.launch(); ctx=await br.new_context(viewport={"width":1380,"height":1000}); pg=await ctx.new_page()
        async def relay(route,req):
            try:
                hdrs={k:v for k,v in req.headers.items() if k.lower() not in ("host","content-length","accept-encoding")}
                body=req.post_data_buffer if req.method in ("POST","PUT","PATCH","DELETE") else None
                r=await asyncio.to_thread(http.request,req.method,req.url,headers=hdrs,content=body)
                await route.fulfill(status=r.status_code,headers={k:v for k,v in r.headers.items() if k.lower() in ("content-type","cache-control")},body=r.content)
            except Exception as e: await route.fulfill(status=502,body=str(e))
        await pg.route("**/*",relay)
        tok=http.post(f"{BASE}/api/auth/login",json={"email":EMAIL,"password":PW}).json()["token"]
        await pg.goto(f"{BASE}/"); await pg.evaluate(f"localStorage.setItem('mb_token','{tok}')"); await pg.goto(f"{BASE}/"); await pg.wait_for_timeout(3000)
        await pg.evaluate(f"openBrand('{BID}')"); await pg.wait_for_timeout(2500)
        await pg.evaluate("state.tab='film studio';renderBrand()"); await pg.wait_for_timeout(3000)
        await pg.evaluate(f"openFilm('{CID}')"); await pg.wait_for_timeout(3500)
        await pg.screenshot(path=os.path.join(OUT,"40-client-film-studio.png"),full_page=True); print("shot 40")
        await br.close()
asyncio.run(main())

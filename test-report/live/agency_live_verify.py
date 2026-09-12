"""Live verification of the Agency OS against production.

Creates ONE temporary client + ONE temporary manager, runs a tiny cycle
(caps: 1 creative, no images), bulk-approves, dry-run publishes, builds a
report, proves manager isolation, then deletes everything it created.
Evidence: test-report/live/agency_live.json
"""
import json, os, sys, time, httpx
BASE = "https://marketing-brain-production-1f88.up.railway.app"
EMAIL = os.environ["MB_ADMIN_EMAIL"]; PW = open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
RUN = time.strftime("%m%d%H%M")
out = []
def rec(n, ok, detail=""):
    out.append({"test": n, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:300]})
    print(f"[{'PASS' if ok else 'FAIL'}] {n} — {str(detail)[:140]}")
c = httpx.Client(base_url=BASE, timeout=60)
r = c.post("/api/auth/login", json={"email": EMAIL, "password": PW}); rec("ADMIN_login", r.status_code == 200, r.status_code)
tok = r.json()["token"]; H = {"Authorization": "Bearer " + tok}
created = {"brand": None, "user": None}
try:
    r = c.get("/api/agency/portfolio", headers=H); p = r.json()
    rec("PORTFOLIO_loads", r.status_code == 200 and "totals" in p, f"{p.get('totals')} pool={p.get('pool')}")
    r = c.get("/api/agency/templates", headers=H); rec("TEMPLATES_listed", r.status_code == 200 and len(r.json()["templates"]) >= 8, [t["id"] for t in r.json()["templates"]])
    r = c.get("/api/agency/settings", headers=H); rec("SETTINGS_readable", r.status_code == 200, r.json().get("branding", {}).get("agency_name"))
    r = c.get("/api/agency/branding"); rec("BRANDING_public", r.status_code == 200 and "footer" not in r.json(), r.json())
    # onboard a temp client (no website: no scrape, no network from prod)
    r = c.post("/api/agency/onboard", headers=H, json={"name": f"ZZ Agency Test {RUN}", "vertical": "dental",
                                                     "config": {"caps": {"gen_daily": 6, "creatives_per_cycle": 1, "images_per_cycle": 0},
                                                                "cycle": {"generate_images": False, "ideas_per_channel": 2, "calendar_days": 7}},
                                                     "setup": {"channels": ["instagram"]}})
    rec("ONBOARD_client", r.status_code == 200, r.text[:200]); d = r.json(); bid = d["brand_id"]; created["brand"] = bid
    for _ in range(30):
        j = c.get(f"/api/agency/jobs/{d['job_id']}", headers=H).json()
        if j.get("state") in ("done", "failed"): break
        time.sleep(2)
    rec("ONBOARD_job_done", j.get("state") == "done", j.get("result") or j.get("error"))
    b = c.get(f"/api/brands/{bid}", headers=H).json(); rec("ONBOARD_brand_ready", b.get("status") == "ready", b.get("status"))
    cfg = c.get(f"/api/brands/{bid}/config", headers=H).json()["config"]
    rec("CONFIG_seeded_from_template", cfg["vertical"] == "dental" and cfg["caps"]["creatives_per_cycle"] == 1 and "BOOK" in cfg["triggers"], cfg["caps"])
    # manager isolation
    r = c.post("/api/users", headers=H, json={"email": f"zz-mgr-{RUN}@example.com", "password": "Mgr!Pass-" + RUN, "role": "manager", "brand_ids": [bid]})
    rec("MANAGER_created", r.status_code == 200 and r.json().get("brand_ids") == [bid], r.text[:120]); created["user"] = r.json().get("id")
    r = c.post("/api/auth/login", json={"email": f"zz-mgr-{RUN}@example.com", "password": "Mgr!Pass-" + RUN}); MH = {"Authorization": "Bearer " + r.json()["token"]}
    vis = [x["id"] for x in c.get("/api/brands", headers=MH).json()]
    rec("MANAGER_sees_only_assigned", vis == [bid], vis)
    other = next((x["id"] for x in c.get("/api/brands", headers=H).json() if x["id"] != bid), None)
    if other:
        rec("MANAGER_403_on_other_brand", c.get(f"/api/brands/{other}", headers=MH).status_code == 403, other)
        rec("MANAGER_bulk_cannot_touch_other", c.post("/api/agency/bulk/approve", headers=MH, json={"items": [{"brand_id": other, "creative_id": "x"}]}).json()["failed"] == 1)
    rec("MANAGER_cannot_onboard", c.post("/api/agency/onboard", headers=MH, json={"name": "nope co"}).status_code == 403)
    rec("MANAGER_portfolio_scoped", [x["brand_id"] for x in c.get("/api/agency/portfolio", headers=MH).json()["clients"]] == [bid])
    # tiny cycle as the manager (real model calls: 2 ideas + calendar + 1 creative)
    r = c.post("/api/agency/cycle", headers=MH, json={"brand_ids": [bid], "label": f"live-verify {RUN}"})
    rec("CYCLE_started", r.status_code == 200, r.text[:160]); cy = r.json()
    for _ in range(90):
        cy = c.get(f"/api/agency/cycles/{cy['id']}", headers=MH).json()
        if cy["state"] == "done": break
        time.sleep(4)
    res = cy["brands"].get(bid, {})
    rec("CYCLE_done", cy["state"] == "done" and res.get("state") == "done", res.get("result") or res.get("error"))
    r0 = res.get("result") or {}
    rec("CYCLE_respected_caps", r0.get("creatives", 0) <= 1 and r0.get("images", 0) == 0, r0)
    crs = c.get(f"/api/brands/{bid}/creatives", headers=H).json()
    rec("CYCLE_creatives_unapproved", len(crs) >= 1 and all(not (x["payload"].get("approval") or {}).get("state") for x in crs), len(crs))
    rec("CYCLE_published_nothing", c.get(f"/api/brands/{bid}/publish", headers=H).json() == [])
    q = c.get("/api/agency/queue", headers=MH).json(); rec("QUEUE_shows_client", q["totals"]["waiting"] >= 1, q["totals"])
    items = [{"brand_id": bid, "creative_id": x["id"]} for x in crs]
    r = c.post("/api/agency/bulk/approve", headers=MH, json={"items": items}).json(); rec("BULK_approve", r["ok"] == len(items) and r["failed"] == 0, r)
    r = c.post("/api/agency/bulk/publish", headers=MH, json={"items": items, "mode": "simulated"}).json()
    rec("BULK_dry_run_publish", r["ok"] == len(items) and all(x["status"] == "simulated" for x in r["results"]), r)
    r = c.post("/api/agency/bulk/publish", headers=MH, json={"items": items, "mode": "live"}).json()
    rec("BULK_live_blocked_without_creds", r["ok"] == 0 and "credentials" in r["results"][0]["error"], r["results"][0])
    period = time.strftime("%Y-%m", time.gmtime())
    r = c.post(f"/api/brands/{bid}/reports", headers=MH, json={"period": period}); rep = r.json()
    rec("REPORT_built", r.status_code == 200 and rep["payload"]["numbers"]["creatives"] >= 1, rep["payload"]["numbers"])
    html = c.get(f"/api/brands/{bid}/reports/{rep['id']}/html", headers=MH).text
    rec("REPORT_html_whitelabel", "<h1>" in html and "<script" not in html, len(html))
    h = c.get("/api/agency/portfolio", headers=H).json(); row = next(x for x in h["clients"] if x["brand_id"] == bid)
    rec("PORTFOLIO_row_after_cycle", row["approvals"]["approved"] >= 1 and row["cycle"]["last_at"], {"score": row["score"], "alerts": [a["code"] for a in row["alerts"]]})
finally:
    if created["user"]:
        rec("CLEANUP_user", c.delete(f"/api/users/{created['user']}", headers=H).status_code == 200)
    if created["brand"]:
        rec("CLEANUP_brand", c.delete(f"/api/brands/{created['brand']}", headers=H).status_code == 200)
        rec("CLEANUP_brand_gone", c.get(f"/api/brands/{created['brand']}", headers=H).status_code == 404)
    json.dump({"run": RUN, "base": BASE, "results": out, "pass": sum(r["status"] == "PASS" for r in out), "fail": sum(r["status"] == "FAIL" for r in out)},
              open(os.path.join(os.path.dirname(__file__), "agency_live.json"), "w"), indent=1)
    print("PASS", sum(r["status"] == "PASS" for r in out), "FAIL", sum(r["status"] == "FAIL" for r in out))

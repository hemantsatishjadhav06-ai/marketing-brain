"""CTO end-to-end run on production for neopolisinfra.com.

Every step a client would go through, in order, against the live deployment:
onboard → scrape → analyse → setup → ideas → calendar → creative → visual →
algo audit → approval → dry-run publish → SEO audit → Meta plan (audiences,
budget, compliance) → Google plan → edit plan → email draft → WhatsApp
trigger → monthly report → portfolio. Real model calls, real site fetches.
Evidence: test-report/live/neopolis_e2e.json (+ artefacts summarised).
"""
import json, os, sys, time, httpx
BASE = os.environ.get("MB_BASE", "https://marketing-brain-production-1f88.up.railway.app")
EMAIL = os.environ["MB_ADMIN_EMAIL"]; PW = open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
SITE = "https://www.neopolisinfra.com"
KEEP = os.environ.get("MB_KEEP", "1") == "1"
out, art = [], {}
T0 = time.time()
def rec(step, ok, detail="", **extra):
    out.append({"step": step, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:400], "t": round(time.time() - T0, 1), **extra})
    print(f"[{'PASS' if ok else 'FAIL'}] {step} — {str(detail)[:150]}", flush=True)
    return ok
c = httpx.Client(base_url=BASE, timeout=180)
r = c.post("/api/auth/login", json={"email": EMAIL, "password": PW}); rec("00 admin login", r.status_code == 200, r.status_code)
H = {"Authorization": "Bearer " + r.json()["token"]}
brands = c.get("/api/brands", headers=H).json()
existing = next((b for b in brands if (b.get("website") or "").rstrip("/") in (SITE, "https://neopolisinfra.com") and b.get("status") == "ready"), None)
bid = None
try:
    # 1. onboard (real_estate template) — scrape + analyse run inside the pool job
    if existing:
        bid = existing["id"]; rec("01 onboard", True, f"reusing ready client {existing['name']} ({bid})")
    else:
        r = c.post("/api/agency/onboard", headers=H, json={"name": "Neopolis Infra LLP", "website": SITE, "vertical": "real_estate",
                   "config": {"market_brief": {"offer": "landlord-share flats 8–14% below resale, direct from the landowner",
                                               "audience": "first-home buyers and NRI investors, West Hyderabad",
                                               "location": "Kokapet, Narsingi, Tellapur, Kollur (West Hyderabad)",
                                               "usps": ["title-verified", "zero broker chain", "8–14% below resale"]},
                              "cta": {"text": "Book a site visit — reply VISIT", "contact": "+91 95336 86567"},
                              "caps": {"gen_daily": 40, "creatives_per_cycle": 2, "images_per_cycle": 1}},
                   "setup": {"channels": ["instagram", "facebook", "whatsapp"], "goals": ["site visits", "leads"]}})
        rec("01 onboard", r.status_code == 200, r.text[:200]); d = r.json(); bid = d["brand_id"]
        for _ in range(60):
            j = c.get(f"/api/agency/jobs/{d['job_id']}", headers=H).json()
            if j.get("state") in ("done", "failed"): break
            time.sleep(3)
        rec("02 onboard job (scrape + analyse + workspace)", j.get("state") == "done", j.get("result") or j.get("error"), log=j.get("log", [])[-6:])
    b = c.get(f"/api/brands/{bid}", headers=H).json()
    art["brand"] = {k: b.get(k) for k in ("id", "name", "website", "status", "setup")}
    sc = b.get("scrape") or {}
    rec("03 scrape captured real site data", bool(sc.get("meta")) or bool(sc.get("text")), {"title": (sc.get("meta") or {}).get("title"), "colors": (sc.get("colors") or [])[:3], "socials": list((sc.get("socials") or {}).keys())})
    prof = b.get("profile") or {}
    rec("04 AI brand analysis", bool(prof.get("brand_voice") or prof.get("positioning")), {"voice": str(prof.get("brand_voice"))[:120], "audience": str(prof.get("target_audience"))[:120], "pillars": prof.get("content_pillars")})
    art["profile"] = {k: prof.get(k) for k in ("brand_voice", "target_audience", "positioning", "content_pillars", "brand_kit")}
    rec("05 client config seeded (real_estate → HOUSING, triggers, caps)", (prof.get("config") or {}).get("vertical") == "real_estate", (prof.get("config") or {}).get("caps"))
    rec("06 brand ready", b.get("status") == "ready", b.get("status"))
    # 2. content pipeline
    r = c.post(f"/api/brands/{bid}/ideas", headers=H, json={"channels": ["instagram"], "count": 4, "funnel_stage": "consideration"})
    ideas = r.json().get("ideas", []) if r.status_code == 200 else []
    rec("07 ideas generated", r.status_code == 200 and len(ideas) >= 3, [i["payload"].get("title") for i in ideas][:4]); art["ideas"] = [i["payload"] for i in ideas][:4]
    r = c.post(f"/api/brands/{bid}/calendar", headers=H, json={"days": 14}); cal = r.json().get("calendar", []) if r.status_code == 200 else []
    rec("08 14-day calendar", r.status_code == 200 and len(cal) >= 3, [(x.get("date"), (x.get("payload") or {}).get("title")) for x in cal[:4]])
    r = c.post(f"/api/brands/{bid}/creatives", headers=H, json={"idea_id": ideas[0]["id"]}); cr = r.json() if r.status_code == 200 else {}
    rec("09 creative produced", r.status_code == 200 and bool(cr.get("payload", {}).get("caption")), {"title": cr.get("payload", {}).get("title"), "caption": (cr.get("payload", {}).get("caption") or "")[:160]})
    art["creative"] = cr.get("payload")
    cid = cr.get("id")
    r = c.post(f"/api/brands/{bid}/images", headers=H, json={"creative_id": cid})
    rec("10 branded visual generated (logo composited)", r.status_code == 200 and r.json().get("ok"), r.json() if r.status_code == 200 else r.text[:200]); art["asset_url"] = (r.json() if r.status_code == 200 else {}).get("asset_url")
    r = c.post(f"/api/brands/{bid}/creatives/{cid}/algo-audit", headers=H)
    rec("11 Instagram algo audit (7 ranking signals, weighted score)", r.status_code == 200 and isinstance(r.json().get("algo_score"), (int, float)), {"algo_score": r.json().get("algo_score"), "signals": [(x.get("signal"), x.get("score")) for x in r.json().get("signals", [])], "verdict": str(r.json().get("verdict"))[:100]} if r.status_code == 200 else r.text[:200]); art["algo_audit"] = r.json() if r.status_code == 200 else None
    q = c.get("/api/approvals", headers=H).json()
    rec("12 creative waiting in approval centre", any(i["id"] == cid for i in q["waiting_for_approval"]), q["counts"])
    r = c.post(f"/api/brands/{bid}/creatives/{cid}/approval", headers=H, json={"state": "approved", "comment": "ok"})
    rec("13 human approval captured → memory", r.status_code == 200 and r.json()["payload"]["approval"]["state"] == "approved")
    mem = c.get(f"/api/brands/{bid}/memory", headers=H).json(); rec("14 brand memory learned from approval", mem["count"] >= 1, [m.get("content", "")[:80] for m in mem["memory"][:2]])
    r = c.post(f"/api/brands/{bid}/publish", headers=H, json={"creative_id": cid, "mode": "simulated"})
    rec("15 dry-run publish + manual checklist", r.status_code == 200 and r.json()["status"] == "simulated", (r.json().get("payload") or {}).get("manual_checklist", [])[:3])
    r = c.post(f"/api/brands/{bid}/publish", headers=H, json={"creative_id": cid, "mode": "live"})
    rec("16 live publish blocked without connected channel", r.status_code == 400 and "credentials" in r.text, r.json().get("detail"))
    # 3. growth tooling
    r = c.post(f"/api/brands/{bid}/seo/audit", headers=H, json={"url": SITE})
    rec("17 SEO audit of neopolisinfra.com (live fetch)", r.status_code == 200 and "score" in r.json(), {"score": r.json().get("score"), "fails": [x["name"] for x in r.json().get("fix_first", [])]} if r.status_code == 200 else r.text[:200])
    art["seo"] = r.json() if r.status_code == 200 else None
    r = c.post(f"/api/brands/{bid}/ads/meta/plan", headers=H, json={"objective": "OUTCOME_LEADS", "daily_budget": 2000, "prompt": "site visits for Kokapet/Narsingi landlord-share flats; NRI investors second audience; WhatsApp lead capture"})
    ok = r.status_code == 200; p = r.json().get("plan", {}) if ok else {}
    rec("18 Meta media plan: audiences + budget + placements", ok and len(p.get("ad_sets", [])) >= 2 and p["budget"]["daily_total"] == 2000, p.get("summary") if ok else r.text[:300])
    rec("19 HOUSING compliance enforced", ok and p.get("compliance", {}).get("special_ad_category") == "HOUSING" and all(s["targeting"]["age_min"] == 18 and not s["targeting"]["genders"] for s in p.get("ad_sets", [])), p.get("compliance", {}).get("applied"))
    rec("20 benchmark estimates present", ok and "benchmark" in p.get("estimates", {}).get("basis", ""), p.get("estimates", {}).get("daily"))
    art["meta_plan"] = p; meta_cid = r.json().get("campaign_id") if ok else None
    if meta_cid:
        p2 = json.loads(json.dumps(p)); p2["ad_sets"][0]["budget_share"] = 0.6; p2["ad_sets"][1]["budget_share"] = 0.4; p2["ad_sets"][0]["targeting"]["genders"] = ["male"]
        r = c.put(f"/api/brands/{bid}/ads/meta/campaigns/{meta_cid}", headers=H, json={"plan": {**p2, "daily_budget": 2500}})
        pe = r.json().get("plan", {}) if r.status_code == 200 else {}
        rec("21 manual edit re-split budget, re-applied HOUSING", r.status_code == 200 and pe["ad_sets"][0]["daily_budget"] == 1500 and pe["ad_sets"][0]["targeting"]["genders"] == [], pe.get("budget", {}).get("split"))
        r = c.post(f"/api/brands/{bid}/ads/meta/launch", headers=H, json={"campaign_id": meta_cid, "approve": True})
        rec("22 launch blocked: Meta Ads not connected (no spend possible)", r.status_code == 400 and "not connected" in r.text, r.json().get("detail"))
        r = c.post(f"/api/brands/{bid}/ads/meta/activate", headers=H, json={"campaign_id": meta_cid, "approve": False})
        rec("23 activate blocked without approval", r.status_code == 403, r.json().get("detail"))
    r = c.post(f"/api/brands/{bid}/ads/google/plan", headers=H, json={"daily_budget": 1000, "prompt": "search intent: landlord share flats hyderabad, kokapet 3bhk"})
    g = r.json().get("plan", {}) if r.status_code == 200 else {}
    rec("24 Google Search plan: ad groups + keywords + RSA", r.status_code == 200 and len(g.get("ad_groups", [])) >= 2 and g.get("keywords"), g.get("summary") if r.status_code == 200 else r.text[:300]); art["google_plan"] = g
    r = c.get(f"/api/brands/{bid}/channels/hub", headers=H); hub = r.json() if r.status_code == 200 else {}
    rec("25 connections hub lists every channel", r.status_code == 200 and len(hub.get("channels", [])) >= 13, {c_["id"]: c_["status"] for c_ in hub.get("channels", [])})
    r = c.post(f"/api/brands/{bid}/channels/connect", headers=H, json={"channel": "instagram", "credentials": {"access_token": "EAAB-test-invalid", "ig_user_id": "17841400000000000"}})
    rec("26 connect instagram (test token) stored", r.status_code == 200, r.json())
    r = c.post(f"/api/brands/{bid}/channels/instagram/test", headers=H)
    rec("27 test-connection reports invalid token honestly (read-only)", r.status_code == 200 and r.json()["ok"] is False, r.json().get("detail"))
    r = c.delete(f"/api/brands/{bid}/channels/instagram", headers=H); rec("28 disconnect", r.status_code == 200)
    r = c.post(f"/api/brands/{bid}/email/mailchimp/draft", headers=H, json={"goal": "invite past enquiries to a Kokapet site-visit weekend", "kind": "broadcast"})
    rec("29 email campaign drafted (send needs approval)", r.status_code == 200 and r.json().get("email_campaign_id"), {"subject": (r.json().get("content") or {}).get("subject")} if r.status_code == 200 else r.text[:200]); art["email"] = (r.json().get("content") if r.status_code == 200 else None)
    r = c.post(f"/api/brands/{bid}/email/mailchimp/send", headers=H, json={"email_campaign_id": (art.get("email") and r.json().get("email_campaign_id")) or "x", "approve": True})
    rec("30 email send blocked: Mailchimp not connected", r.status_code in (400, 403), r.json().get("detail"))
    r = c.post("/api/whatsapp/webhook", json={"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "000"}, "messages": [{"from": "919999999999", "text": {"body": "PRICE for kokapet 3bhk?"}}]}}]}]})
    rec("31 WhatsApp inbound webhook accepted (no brand mapped → ignored safely)", r.status_code == 200, r.json())
    r = c.post(f"/api/brands/{bid}/whatsapp/send", headers=H, json={"to": "919999999999", "text": "hi"})
    rec("32 WhatsApp send blocked: not connected", r.status_code in (400, 403), r.json().get("detail"))
    r = c.post(f"/api/brands/{bid}/reports", headers=H, json={"period": time.strftime("%Y-%m", time.gmtime())})
    rec("33 monthly white-label report", r.status_code == 200 and r.json()["payload"]["numbers"]["creatives"] >= 1, r.json()["payload"]["numbers"] if r.status_code == 200 else r.text[:200]); art["report"] = r.json().get("payload") if r.status_code == 200 else None
    art["report_id"] = r.json().get("id") if r.status_code == 200 else None
    port = c.get("/api/agency/portfolio", headers=H).json(); row = next((x for x in port["clients"] if x["brand_id"] == bid), {})
    rec("34 portfolio health row", bool(row), {"score": row.get("score"), "grade": row.get("grade"), "alerts": [a["code"] for a in row.get("alerts", [])]}); art["portfolio_row"] = row
    r = c.get(f"/api/brands/{bid}/history", headers=H); rec("35 audit trail (agent runs)", r.status_code == 200, r.json().get("count"))
finally:
    if bid and not KEEP:
        c.delete(f"/api/brands/{bid}", headers=H)
    res = {"run": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "base": BASE, "site": SITE, "brand_id": bid, "kept": KEEP,
           "pass": sum(r["status"] == "PASS" for r in out), "fail": sum(r["status"] == "FAIL" for r in out), "steps": out, "artefacts": art}
    json.dump(res, open(os.path.join(os.path.dirname(__file__), "neopolis_e2e.json"), "w"), indent=1, default=str)
    print("PASS", res["pass"], "FAIL", res["fail"], "brand", bid)

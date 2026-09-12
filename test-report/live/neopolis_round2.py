"""Round 2 on production for Neopolis Infra LLP: a brand-new post judged and fixed
by the Design QA agent, the built-in mailer (contacts → AI draft → preview →
approval gate), and the Airtable calendar status. Evidence: neopolis_round2.json."""
import json, os, time, httpx
BASE = "https://marketing-brain-production-1f88.up.railway.app"
EMAIL = os.environ["MB_ADMIN_EMAIL"]; PW = open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
BID = os.environ.get("MB_BID", "af4c0bd6fbbd")
out, art = [], {}
def rec(step, ok, detail="", **x):
    out.append({"step": step, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:500], **x}); print(f"[{'PASS' if ok else 'FAIL'}] {step} — {str(detail)[:160]}", flush=True)
c = httpx.Client(base_url=BASE, timeout=240)
tok = c.post("/api/auth/login", json={"email": EMAIL, "password": PW}).json()["token"]; H = {"Authorization": "Bearer " + tok}
try:
    # ---- a new post, end to end, with the art director in the loop ----
    r = c.post(f"/api/brands/{BID}/ideas", headers=H, json={"channels": ["instagram"], "count": 2, "formats": ["post"],
               "topic": "why landlord-share flats cost 8–14% less than resale in Kokapet", "funnel_stage": "consideration"})
    ideas = r.json().get("ideas", []) if r.status_code == 200 else []
    rec("01 new idea", bool(ideas), [i["payload"].get("title") for i in ideas])
    r = c.post(f"/api/brands/{BID}/creatives", headers=H, json={"idea_id": ideas[0]["id"]}); cr = r.json(); cid = cr["id"]
    rec("02 creative produced", r.status_code == 200, {"title": cr["payload"].get("title"), "caption": (cr["payload"].get("caption") or "")[:140]})
    art["creative"] = {k: cr["payload"].get(k) for k in ("title", "caption", "hashtags", "image_prompt", "cta")}
    r = c.post(f"/api/brands/{BID}/images", headers=H, json={"creative_id": cid}); rec("03 first visual generated", r.status_code == 200, r.json() if r.status_code == 200 else r.text[:200])
    art["before_asset"] = (r.json() if r.status_code == 200 else {}).get("asset_url")
    r = c.post(f"/api/brands/{BID}/creatives/{cid}/design-review", headers=H); rv = r.json() if r.status_code == 200 else {}
    rec("04 art-director review (vision)", r.status_code == 200 and rv.get("score") is not None, {"score": rv.get("score"), "verdict": rv.get("verdict"), "issues": [(i.get("area"), i.get("severity"), i.get("problem")) for i in rv.get("issues", [])][:6], "file": rv.get("checks", {}).get("width") and f"{rv['checks']['width']}x{rv['checks']['height']} target {rv['checks']['target']}"})
    art["review_before"] = rv
    r = c.post(f"/api/brands/{BID}/creatives/{cid}/design-fix", headers=H); fx = r.json() if r.status_code == 200 else {}
    rec("05 design fix applied", r.status_code == 200, {"applied": fx.get("applied"), "before": fx.get("before"), "after": fx.get("after"), "regen": fx.get("regen"), "publish_ready": fx.get("publish_ready")})
    art["fix"] = fx
    cfin = c.get(f"/api/brands/{BID}/creatives", headers=H).json(); cfin = next(x for x in cfin if x["id"] == cid)
    rec("06 creative carries design_qa record + asset history", bool(cfin["payload"].get("design_qa")), {"asset": cfin.get("asset_path"), "history": cfin["payload"].get("asset_history")})
    art["after_asset"] = cfin.get("asset_path"); art["creative_id"] = cid
    # ---- built-in mailer ----
    r = c.post(f"/api/brands/{BID}/mail/contacts", headers=H, json={"csv": "email,name,tags\npriya.test@example.com,Priya Sharma,enquiry-2026\nrahul.test@example.com,Rahul Verma,\"enquiry-2026, nri\"\n", "tags": ["cto-test"]})
    rec("07 contacts imported (test addresses)", r.status_code == 200 and r.json()["added"] + r.json()["updated"] == 2, r.json())
    st = c.get(f"/api/brands/{BID}/mail/status", headers=H).json(); rec("08 mail status", "smtp_connected" in st, st)
    r = c.post(f"/api/brands/{BID}/mail/draft", headers=H, json={"goal": "invite 2026 enquiries to a Kokapet site-visit weekend, direct from landowners, 8–14% below resale", "segment": {"tags": ["enquiry-2026"]}})
    camp = r.json().get("campaign", {}) if r.status_code == 200 else {}
    rec("09 broadcast drafted by AI", r.status_code == 200 and camp.get("payload", {}).get("subject"), {"subject": camp.get("payload", {}).get("subject"), "alt": camp.get("payload", {}).get("subject_alt"), "preview": camp.get("payload", {}).get("preview"), "audience": camp.get("audience_size")})
    art["mail"] = camp.get("payload")
    pv = c.get(f"/api/brands/{BID}/mail/campaigns/{camp['id']}/preview", headers=H)
    rec("10 branded preview renders with tracking + unsubscribe", pv.status_code == 200 and "/m/u/" in pv.text and "Unsubscribe" in pv.text, {"bytes": len(pv.text), "subject": pv.headers.get("x-subject")})
    art["mail_preview_html"] = pv.text
    r = c.post(f"/api/brands/{BID}/mail/draft", headers=H, json={"goal": "re-engage enquiries who never booked a visit", "kind": "sequence", "segment": {"tags": ["nri"]}})
    seq = r.json().get("campaign", {}) if r.status_code == 200 else {}
    rec("11 3–4 step sequence drafted", r.status_code == 200 and len(seq.get("payload", {}).get("steps", [])) >= 3, [(s["delay_days"], s["subject"]) for s in seq.get("payload", {}).get("steps", [])])
    art["sequence"] = seq.get("payload", {}).get("steps")
    r = c.post(f"/api/brands/{BID}/mail/campaigns/{camp['id']}/approve", headers=H, json={"approve": True})
    rec("12 send blocked: SMTP not connected (nothing sent)", r.status_code == 400 and "SMTP" in r.text, r.json().get("detail"))
    r = c.post(f"/api/brands/{BID}/mail/campaigns/{camp['id']}/approve", headers=H, json={"approve": False})
    rec("13 send blocked without approval", r.status_code == 403, r.json().get("detail"))
    r = c.get(f"/api/brands/{BID}/mail/campaigns", headers=H); rec("14 campaigns listed with stats", r.status_code == 200 and len(r.json()) >= 2, [(x["kind"], x["status"], x["subject"]) for x in r.json()][:4])
    # ---- airtable ----
    r = c.get(f"/api/brands/{BID}/airtable", headers=H); rec("15 airtable status (no PAT on this client yet)", r.status_code == 200, r.json())
    r = c.post(f"/api/brands/{BID}/airtable/push", headers=H); rec("16 push refuses cleanly without a token", r.status_code == 400, r.json().get("detail"))
    hub = c.get(f"/api/brands/{BID}/channels/hub", headers=H).json()
    rec("17 hub lists SMTP + Airtable with workspace field", any(x["id"] == "smtp" for x in hub["channels"]) and any(f["key"] == "workspace_id" for x in hub["channels"] if x["id"] == "airtable" for f in x["fields"]))
    port = c.get("/api/agency/portfolio", headers=H).json(); row = next(x for x in port["clients"] if x["brand_id"] == BID)
    rec("18 portfolio after round 2", True, {"score": row["score"], "waiting": row["approvals"]["waiting"], "creatives_7d": row["content"]["creatives_7d"]})
finally:
    res = {"run": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "brand_id": BID, "pass": sum(r["status"] == "PASS" for r in out), "fail": sum(r["status"] == "FAIL" for r in out), "steps": out, "artefacts": art}
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "neopolis_round2.json"), "w"), indent=1, default=str)
    print("PASS", res["pass"], "FAIL", res["fail"])

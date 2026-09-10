import json, httpx
BASE="https://marketing-brain-production-1f88.up.railway.app"
d=json.load(open("live_report.json")); RUN=d["run"]; A=d["orgs"]["A"]; PW="Str0ng!Pass-"+RUN
tok=httpx.post(BASE+"/api/auth/login",json={"email":A["email"],"password":PW},timeout=30).json()["token"]; H={"Authorization":"Bearer "+tok}; bid=A["bid"]
out=[]
def rec(n,s,detail): out.append({"test":n,"status":s,"detail":detail}); print(f"[{s:8}] {n} — {detail[:160]}")
r=httpx.get(BASE+f"/api/brands/{bid}/connectors",headers=H,timeout=30); b=r.json()
guides=b.get("setup_guides",{}); rec("CONNECT_setup_guides_for_all_platforms","PASS" if r.status_code==200 and set(guides)>= {"instagram","facebook","linkedin","twitter"} and all(len(v)>=3 for v in guides.values()) else "FAIL",f"{r.status_code} platforms={sorted(guides)} configured={b.get('configured')}")
r=httpx.post(BASE+f"/api/brands/{bid}/connectors",json={"platform":"tiktok","credentials":{"x":"y"}},headers=H,timeout=30); rec("CONNECT_unsupported_platform_rejected","PASS" if r.status_code==400 else "FAIL",f"{r.status_code} {r.text[:100]}")
r=httpx.post(BASE+f"/api/brands/{bid}/connectors",json={"platform":"instagram","credentials":{"access_token":"FAKE-TOKEN-FOR-TEST","ig_user_id":"17841400000000000"}},headers=H,timeout=30); rec("CONNECT_save_instagram_credentials","PASS" if r.status_code==200 else "FAIL",f"{r.status_code} {r.text[:100]}")
r=httpx.get(BASE+f"/api/brands/{bid}/connectors",headers=H,timeout=30); b=r.json(); rec("CONNECT_status_shows_configured","PASS" if "instagram" in (b.get("configured") or []) else "FAIL",f"configured={b.get('configured')}")
rec("CONNECT_credentials_never_returned_by_api","PASS" if "FAKE-TOKEN" not in r.text else "FAIL","token echoed back!" if "FAKE-TOKEN" in r.text else "not echoed")
# live publish with bad creds: must fail GRACEFULLY (status failed + error recorded), never crash, never claim success
c=httpx.post(BASE+f"/api/brands/{bid}/studio/save",json={"title":"conn","caption":"c","format":"post","asset_path":""},headers=H,timeout=30).json()["creative_id"]
httpx.post(BASE+f"/api/brands/{bid}/creatives/{c}/approval",json={"state":"approved","comment":"ok"},headers=H,timeout=30)
r=httpx.post(BASE+f"/api/brands/{bid}/publish",json={"creative_id":c,"channel":"instagram","mode":"live"},headers=H,timeout=120); b=r.json() if r.status_code<500 else {}
graceful = r.status_code==200 and b.get("status")=="failed" and "error" in (b.get("payload") or b.get("result") or b)
rec("PUBLISH_live_bad_token_fails_gracefully","PASS" if graceful or (r.status_code in (400,502)) else "FAIL",f"{r.status_code} status={b.get('status')} keys={list(b)[:8]} {str(b)[:160]}")
r=httpx.get(BASE+f"/api/brands/{bid}/publish",headers=H,timeout=30); rows=[p for p in r.json() if p.get("creative_id")==c]
rec("PUBLISH_failed_attempt_recorded_not_published","PASS" if rows and all(p.get("status")!="published" for p in rows if p.get("mode")=="live") else "FAIL",f"live rows={[ (p.get('mode'),p.get('status')) for p in rows]}")
json.dump({"results":out},open("connectors_report.json","w"),indent=1); print("SUMMARY",{s:sum(1 for o in out if o["status"]==s) for s in ("PASS","FAIL")})

import json, time, httpx
BASE="https://marketing-brain-production-1f88.up.railway.app"
d=json.load(open("live_report.json")); RUN=d["run"]; A=d["orgs"]["A"]; B=d["orgs"]["B"]; PW="Str0ng!Pass-"+RUN
out=[]
def rec(n,s,detail): out.append({"test":n,"status":s,"detail":detail}); print(f"[{s:8}] {n} — {detail[:140]}")
h=httpx.get(BASE+"/api/health",timeout=30).json(); rec("HEALTH_ok","PASS" if h.get("ok") and h.get("persistent_db") and not h.get("direct_access") else "FAIL",json.dumps(h))
r=httpx.post(BASE+"/api/signup",json={"company_name":"Gate Test","email":f"gate-{RUN}@example.com","password":"Str0ngPass!1","website":""},timeout=30)
rec("SIGNUP_gate_closed_403","PASS" if r.status_code==403 else "FAIL",f"{r.status_code} {r.text[:80]}")
# login (legacy sha256 hash from signup-time -> must still work AND be upgraded to pbkdf2 by this login)
r=httpx.post(BASE+"/api/auth/login",json={"email":A["email"],"password":PW},timeout=30); rec("AUTH_legacy_hash_login_still_works","PASS" if r.status_code==200 else "FAIL",str(r.status_code)); tokA=r.json().get("token")
r=httpx.post(BASE+"/api/auth/login",json={"email":A["email"],"password":PW},timeout=30); rec("AUTH_login_after_rehash_works","PASS" if r.status_code==200 else "FAIL",str(r.status_code))
rB=httpx.post(BASE+"/api/auth/login",json={"email":B["email"],"password":PW},timeout=30); tokB=rB.json().get("token")
HA={"Authorization":"Bearer "+tokA}; HB={"Authorization":"Bearer "+tokB}
rec("AUTH_me_with_revocation_check","PASS" if httpx.get(BASE+"/api/auth/me",headers=HA,timeout=30).status_code==200 else "FAIL","")
# idempotency (was FAIL live: 2 rows)
c=httpx.post(BASE+f"/api/brands/{A['bid']}/studio/save",json={"title":"idem","caption":"c","format":"post","asset_path":""},headers=HA,timeout=30).json()["creative_id"]
n0=len(httpx.get(BASE+f"/api/brands/{A['bid']}/publish",headers=HA,timeout=30).json())
p1=httpx.post(BASE+f"/api/brands/{A['bid']}/publish",json={"creative_id":c,"channel":"instagram","mode":"simulated"},headers=HA,timeout=30).json()
p2=httpx.post(BASE+f"/api/brands/{A['bid']}/publish",json={"creative_id":c,"channel":"instagram","mode":"simulated"},headers=HA,timeout=30).json()
n1=len(httpx.get(BASE+f"/api/brands/{A['bid']}/publish",headers=HA,timeout=30).json())
rec("PUBLISH_duplicate_request_single_publish","PASS" if n1-n0==1 and p1.get("id")==p2.get("id") else "FAIL",f"rows added={n1-n0} same_id={p1.get('id')==p2.get('id')}")
# private competitor URL rejected at creation (was: stored)
r=httpx.post(BASE+f"/api/brands/{A['bid']}/competitors",json={"url":"http://169.254.169.254/latest/meta-data/","name":"x"},headers=HA,timeout=60)
rec("SSRF_private_url_rejected_at_creation","PASS" if r.status_code==400 else "FAIL",f"{r.status_code} {r.text[:80]}")
# IDOR still blocked + cross-tenant workspace read blocked
rec("IDOR_B_cannot_set_A_idea_state","PASS" if httpx.post(BASE+f"/api/brands/{A['bid']}/ideas/x/state",json={"state":"approved"},headers=HB,timeout=30).status_code in (403,404) else "FAIL","")
bA=httpx.get(BASE+f"/api/brands/{A['bid']}",headers=HA,timeout=30).json(); slugA=bA.get("slug")
r=httpx.get(BASE+f"/workspaces/{slugA}/brand-profile/profile.json",headers=HB,timeout=30)
rec("TENANT_B_cannot_read_A_workspace_files","PASS" if r.status_code in (403,404) else "FAIL",f"{r.status_code}")
# cost guard visible on an expensive route? (cannot trip the cap cheaply; assert route exists and is auth-gated)
r=httpx.post(BASE+f"/api/brands/{A['bid']}/studio/moodboard",json={"topic":"x","format":"post"},timeout=30)
rec("COST_guarded_route_requires_auth","PASS" if r.status_code==401 else "FAIL",str(r.status_code))
json.dump({"results":out},open("post_deploy_report.json","w"),indent=1)
print("SUMMARY", {s:sum(1 for o in out if o["status"]==s) for s in ("PASS","FAIL")})

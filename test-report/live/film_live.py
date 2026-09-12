"""Live verification of the Cinematic Storyboard Film on production for Neopolis.
Plans a storyboard, proves nothing rendered, edits a cut (re-opens the gate),
approves, renders, checks frames + VO. Evidence: film_live.json."""
import json, os, sys, time, httpx, urllib.request
BASE="https://marketing-brain-production-1f88.up.railway.app"
EMAIL=os.environ["MB_ADMIN_EMAIL"]; PW=open(os.environ["MB_ADMIN_PW_FILE"]).read().strip()
BID=os.environ.get("MB_BID","af4c0bd6fbbd")
out,art=[],{}
def rec(step,ok,detail="",**x): out.append({"step":step,"status":"PASS" if ok else "FAIL","detail":str(detail)[:400],**x}); print(f"[{'PASS' if ok else 'FAIL'}] {step} — {str(detail)[:150]}",flush=True)
c=httpx.Client(base_url=BASE,timeout=240)
tok=c.post("/api/auth/login",json={"email":EMAIL,"password":PW}).json()["token"]; H={"Authorization":"Bearer "+tok}
def poll(r,label):
    n=0
    while r.get("job_id") and r.get("state") not in ("done","failed") and n<120:
        time.sleep(4); j=c.get(f"/api/agency/jobs/{r['job_id']}",headers=H).json(); r={**r,"state":j.get("state"),**(j.get("result") or {}),"error":j.get("error"),"log":j.get("log")}; n+=1
    return r
try:
    o=c.get("/api/film-studio/options",headers=H).json()
    rec("01 options: looks + aspects + limits",len(o["looks"])>=8 and "9:16" in o["aspects"] and o["limits"]["max_cuts"]==12,[l["id"] for l in o["looks"]])
    r=c.post(f"/api/brands/{BID}/film/plan",headers=H,json={"prompt":"30s launch film: why landlord-share flats in Kokapet cost 8-14% below resale, direct from the landowner, title-verified, zero broker chain; end on a site-visit CTA","look":"warm-neutral-premium","aspect":"9:16","cuts":6,"target_seconds":30}).json()
    r=poll(r,"plan")
    rec("02 storyboard directed (no render)",r.get("state")=="done" and r.get("status")=="storyboard" and r.get("cuts")>=5,{"cuts":r.get("cuts"),"total":r.get("total_seconds"),"log":(r.get("log") or [])[-2:]})
    cid=r.get("creative_id"); art["creative_id"]=cid
    f=c.get(f"/api/brands/{BID}/film/{cid}",headers=H).json(); film=f["film"]
    rec("03 nothing rendered yet",film["status"]=="storyboard" and not film["rendered"] and all("asset" not in cu for cu in film["cuts"]) and not f.get("asset_path"),{"status":film["status"]})
    tc=[(cu["t_in"],cu["t_out"],cu["duration_s"]) for cu in film["cuts"]]
    rec("04 timecodes computed + durations clamped",film["cuts"][0]["t_in"]==0 and all(3<=cu["duration_s"]<=15 for cu in film["cuts"]) and all(film["cuts"][i]["t_in"]==film["cuts"][i-1]["t_out"] for i in range(1,len(film["cuts"]))),tc)
    art["storyboard"]={"title":f["title"],"logline":film.get("logline"),"look":film["look"],"total_seconds":film["total_seconds"],"cuts":[{k:cu.get(k) for k in ("n","t_in","t_out","duration_s","camera","lighting","vo_tone","vo_line","on_screen_text","visual","transition")} for cu in film["cuts"]]}
    # edit cut 1 → re-opens the gate
    c.post(f"/api/brands/{BID}/creatives/{cid}/approval",headers=H,json={"state":"approved","comment":"ok"})
    r2=c.put(f"/api/brands/{BID}/film/{cid}/cut/0",headers=H,json={"duration_s":5,"vo_tone":"warm, assured"}).json()
    fchk=c.get(f"/api/brands/{BID}/film/{cid}",headers=H).json()
    rec("05 edit recomputes + re-opens approval gate",r2["film"]["cuts"][0]["duration_s"]==5 and r2["film"]["cuts"][1]["t_in"]==5 and (fchk.get("approval") or {}).get("state")!="approved",{"approval":fchk.get("approval")})
    # reorder last→first then back is optional; test reorder validity
    n=len(fchk["film"]["cuts"]); r3=c.post(f"/api/brands/{BID}/film/{cid}/reorder",headers=H,json={"order":list(range(n))[::-1]}).json()
    rec("06 reorder renumbers",[cu["n"] for cu in r3["film"]["cuts"]]==list(range(1,n+1)),[cu["n"] for cu in r3["film"]["cuts"]])
    c.post(f"/api/brands/{BID}/film/{cid}/reorder",headers=H,json={"order":list(range(n))[::-1]})  # back to original order
    # render blocked until approved
    rb=c.post(f"/api/brands/{BID}/film/{cid}/render",headers=H)
    rec("07 render blocked before approval",rb.status_code==400,rb.json().get("detail"))
    c.post(f"/api/brands/{BID}/creatives/{cid}/approval",headers=H,json={"state":"approved","comment":"approved for render"})
    r=c.post(f"/api/brands/{BID}/film/{cid}/render",headers=H).json(); r=poll(r,"render")
    rec("08 render after approval → frames + VO",r.get("state")=="done" and r.get("status")=="rendered" and r.get("frames")>=4,{"frames":r.get("frames"),"log":(r.get("log") or [])[-2:]})
    f2=c.get(f"/api/brands/{BID}/film/{cid}",headers=H).json(); film2=f2["film"]
    rec("09 rendered creative carries frames + VO + asset",film2["rendered"] and all(cu.get("asset") for cu in film2["cuts"]) and film2.get("vo_asset") and f2.get("asset_path"),{"vo":bool(film2.get("vo_asset")),"asset":f2.get("asset_path")})
    art["rendered"]={"vo_asset":film2.get("vo_asset"),"first_frame":f2.get("asset_path"),"cut_assets":[cu.get("asset") for cu in film2["cuts"]]}
    # save first two frames for the report
    SP=os.path.dirname(os.path.abspath(__file__))
    for i,cu in enumerate(film2["cuts"][:2]):
        a=cu.get("asset")
        if a:
            rel=a.split("/workspaces/neopolis-infra-llp/")[-1] if "/workspaces/" in a else a
            try: urllib.request.urlretrieve(f"{BASE}/workspaces/neopolis-infra-llp/{rel}",os.path.join(SP,f"film_cut{i+1}.png")); print("saved cut",i+1)
            except Exception as e: print("save fail",e)
    # list shows it rendered
    lst=c.get(f"/api/brands/{BID}/films",headers=H).json()
    rec("10 films list shows rendered film",any(x["id"]==cid and x["status"]=="rendered" for x in lst),[(x["title"],x["status"]) for x in lst][:3])
finally:
    res={"run":time.strftime("%Y-%m-%d %H:%M UTC",time.gmtime()),"brand_id":BID,"pass":sum(r["status"]=="PASS" for r in out),"fail":sum(r["status"]=="FAIL" for r in out),"steps":out,"artefacts":art}
    json.dump(res,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"film_live.json"),"w"),indent=1,default=str)
    print("PASS",res["pass"],"FAIL",res["fail"])

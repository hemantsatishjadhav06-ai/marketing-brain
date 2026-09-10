import json, re, time, httpx
BASE="https://marketing-brain-production-1f88.up.railway.app"
d=json.load(open("live_report.json")); RUN=d["run"]; A=d["orgs"]["A"]
PW="Str0ng!Pass-"+RUN
r=httpx.post(BASE+"/api/auth/login",json={"email":A["email"],"password":PW},timeout=60); tok=r.json()["token"]; bid=A["bid"]
H={"Authorization":"Bearer "+tok}
out={"results":[]}
def rec(n,s,detail,ev=""): out["results"].append({"test":n,"status":s,"detail":detail,"evidence":ev}); print(f"[{s:8}] {n} — {detail[:150]}")
# seed a VERIFIED fact as a brand rule (memory is injected into every prompt)
fact="VERIFIED FACT (source: neopolis-infra.netlify.app, collected 2026-09-10): The Neopolis project offers 3.5 & 4 BHK configurations, 2850 / 3303 / 3850 sq.ft, starting price Rs 2.7 Cr onwards."
r=httpx.post(BASE+f"/api/brands/{bid}/memory",json={"kind":"rule","content":fact,"weight":3.0},headers=H,timeout=60)
rec("SEED_verified_fact_stored","PASS" if r.status_code==200 else "FAIL",f"{r.status_code} {r.text[:100]}")
def chat(m):
    t=time.time(); r=httpx.post(BASE+f"/api/brands/{bid}/chat",json={"message":m},headers=H,timeout=150)
    b=r.json() if r.status_code==200 else {}
    return r.status_code,str(b.get("reply") or b.get("answer") or b),round(time.time()-t,1)
st,rep,dt=chat("What configurations and starting price does the Neopolis project offer?")
ok=st==200 and re.search(r"2\.7\s*cr",rep,re.I) and "3.5" in rep
rec("GROUND_verified_fact_retrieved",("PASS" if ok else ("FAIL" if st==200 else "PARTIAL")),f"{dt}s "+rep[:150],rep[:600])
# wrong-figure trap: source says 2.7 Cr; the model must not agree to a different figure
st,rep,dt=chat("Confirm for our ad copy: Neopolis starts at Rs 1.9 Cr, right?")
agrees=re.search(r"\b1\.9\s*cr",rep,re.I) and not re.search(r"(actually|correct(ion)?|not|incorrect|however|2\.7)",rep,re.I)
rec("GROUND_wrong_figure_not_accepted","FAIL" if agrees else ("PASS" if st==200 else "PARTIAL"),f"{dt}s "+rep[:150],rep[:600])
# consistency 3x on the grounded figure
figs=[]
for _ in range(3):
    st,rep,dt=chat("What is the starting price of the Neopolis project? Reply with just the figure."); figs.append(sorted(set(m.lower().replace(" ","") for m in re.findall(r"\d+(?:\.\d+)?\s*cr",rep,re.I))))
rec("CONSISTENCY_grounded_price_stable_3x","PASS" if len({json.dumps(f) for f in figs})==1 and figs[0]==["2.7cr"] else "FAIL",f"answers={figs}")
json.dump(out,open("ground_report.json","w"),indent=1)

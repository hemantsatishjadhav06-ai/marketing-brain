"""Run the Design QA fix as a background job on production and poll it; save before/after images."""
import json, os, sys, time, httpx, urllib.request
BASE = "https://marketing-brain-production-1f88.up.railway.app"
tok = open(sys.argv[1]).read().strip(); BID = sys.argv[2]; CID = sys.argv[3]; OUT = sys.argv[4]
H = {"Authorization": "Bearer " + tok}
c = httpx.Client(base_url=BASE, timeout=120, headers=H)
r = c.post(f"/api/brands/{BID}/creatives/{CID}/design-fix"); print("submit", r.status_code, r.text[:200])
j = r.json(); jid = j["job_id"]
for _ in range(80):
    s = c.get(f"/api/agency/jobs/{jid}").json()
    print("  ", s.get("state"), (s.get("log") or [""])[-1][:100], flush=True)
    if s.get("state") in ("done", "failed"):
        break
    time.sleep(6)
res = s.get("result") or {}
json.dump({"job": {k: v for k, v in s.items() if k != "result"}, "result": res}, open(OUT, "w"), indent=1, default=str)
print("applied:", res.get("applied")); print("before:", res.get("before")); print("after:", res.get("after")); print("regen:", res.get("regen")); print("publish_ready:", res.get("publish_ready"))
rv = res.get("review") or {}; print("verdict:", rv.get("verdict")); [print(" -", i.get("area"), i.get("severity"), "|", i.get("problem")) for i in rv.get("issues", [])]
print("vision:", json.dumps({k: rv.get("vision", {}).get(k) for k in ("text_in_image", "matches_caption", "brand_colours", "logo")})[:600])
SP = os.path.dirname(OUT)
for tag, key in (("before", (res.get("before") or {}).get("asset")), ("after", (res.get("after") or {}).get("asset"))):
    if key:
        rel = key.split("/workspaces/neopolis-infra-llp/")[-1]
        urllib.request.urlretrieve(f"{BASE}/workspaces/neopolis-infra-llp/{rel}", os.path.join(SP, f"final_{tag}.png")); print(tag, "saved", rel)
from PIL import Image
for tag in ("before", "after"):
    p = os.path.join(SP, f"final_{tag}.png")
    if os.path.exists(p):
        im = Image.open(p); print(tag, im.size); im.convert("RGB").resize((432, int(432 * im.size[1] / im.size[0]))).save(os.path.join(SP, f"final_{tag}_small.jpg"), quality=80)

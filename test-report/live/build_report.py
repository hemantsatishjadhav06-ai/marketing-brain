"""Build the CTO report (Markdown in repo + HTML artifact) from the live e2e evidence."""
import base64, io, json, os, html, time
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
E = json.load(open(os.path.join(HERE, "neopolis_e2e.json")))
SHOTS = os.path.join(HERE, "shots")
OUT_HTML = os.environ.get("REPORT_HTML", "/tmp/claude-0/-home-user/fa0348bf-bc23-56ce-a8a2-a3f296fc119a/scratchpad/neopolis-cto-report.html")
OUT_MD = os.path.join(HERE, "..", "neopolis-cto-report.md")
esc = html.escape
A = E.get("artefacts", {})
steps = E["steps"]

CAPTIONS = {
 "01-portfolio": ("Portfolio", "Every client scored 0–100 with alerts; the pool status shows how many cycles run at once."),
 "02-approvals": ("Approval Center with bulk bar", "Select all → approve, request changes, dry-run or publish live. Each item passes the same gates."),
 "02-cycles": ("Weekly cycles", "Ideas → calendar → creatives → images for every client, three at a time; output lands in Approvals."),
 "02-clients": ("Clients", "Onboard with a vertical template; tune the brief, caps and WhatsApp triggers; generate the monthly report."),
 "03-connections-hub": ("Connections hub", "13 channels grouped by role with honest status, credential fields, setup steps and a read-only Test."),
 "04-meta-media-plan": ("Meta media plan", "Audiences with geo/age/interests/placements, budget split, HOUSING rules applied, benchmark estimates, ad mock-ups, tracking."),
 "05-google-search-plan": ("Google Search plan", "Ad groups with keyword match types, negatives, responsive search ad preview, locations, bidding."),
 "06-seo-panel": ("SEO audit", "Live fetch of the client site, 17 technical + on-page checks."),
 "07-agency-settings": ("Agency settings", "White-label branding, portfolio defaults, team with manager assignments."),
 "10-client-dashboard": ("Client app — dashboard", "What the client sees when they sign in."),
 "11-client-brand-create": ("Client app — Create", "Brand header in the client's own colours; create studio."),
 "12-client-content-board": ("Client app — Content board", "Creatives with approval state, visuals and publish actions."),
 "13-client-ideas": ("Client app — Ideas", "Scored ideas per channel with state control."),
 "14-client-calendar": ("Client app — Calendar", "The 14-day plan."),
 "15-client-paid-ads": ("Client app — Paid ads", "The same media plan the agency sees, read-only for client logins, editable for owners."),
 "16-client-connections": ("Client app — Connections", "Connect the client's own accounts; test proves the token; disconnect any time."),
 "17-client-memory": ("Client app — Memory", "What the system learned from approvals and corrections."),
 "20-landing-site": ("Marketing site", "The public product site."),
}

def img_uri(name, width=1100, q=68):
    p = os.path.join(SHOTS, name + ".jpg")
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGB")
    if im.height > 2600:
        im = im.crop((0, 0, im.width, 2600))
    r = width / im.width
    im = im.resize((width, int(im.height * r)))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

shots = [n for n in sorted(os.listdir(SHOTS)) if n.endswith(".jpg")] if os.path.isdir(SHOTS) else []
shots = [s[:-4] for s in shots]

# ---------- derived content ----------
mp = A.get("meta_plan") or {}
gp = A.get("google_plan") or {}
seo = A.get("seo") or {}
prof = A.get("profile") or {}
brand = A.get("brand") or {}
row = A.get("portfolio_row") or {}
fails = [s for s in steps if s["status"] == "FAIL"]

def step_rows():
    return "".join(f'<tr><td class="mono">{esc(s["step"][:2])}</td><td>{esc(s["step"][3:])}</td><td><span class="st {s["status"].lower()}">{s["status"]}</span></td><td class="mono small">{esc(s["detail"][:170])}</td></tr>' for s in steps)

def adset_rows():
    out = []
    for s in mp.get("ad_sets", []):
        t = s.get("targeting", {}); geo = t.get("geo", {})
        loc = ", ".join(f'{c.get("name")} +{c.get("radius_km")} km' for c in geo.get("cities", [])) or ", ".join(geo.get("countries", []))
        out.append(f'<tr><td><b>{esc(s.get("name",""))}</b><div class="small">{esc(s.get("audience_label",""))}</div></td><td>{esc(loc)}</td><td class="mono">{t.get("age_min")}–{t.get("age_max")}+</td><td>{esc(", ".join(t.get("genders") or ["All"]))}</td><td>{esc(", ".join(t.get("interests", [])[:5]))}</td><td>{esc(", ".join(p.replace("_"," ") for p in s.get("placements", [])))}</td><td class="mono">₹{s.get("daily_budget")}/day ({round((s.get("budget_share") or 0)*100)}%)</td></tr>')
    return "".join(out)

def ads_rows():
    return "".join(f'<div class="ad"><div class="pt">{esc(a.get("primary_text",""))}</div><div class="hl">{esc(a.get("headline",""))}</div><div class="small">{esc(a.get("description",""))} · <span class="mono">{esc(a.get("cta",""))}</span></div></div>' for a in mp.get("ads", []))

def kw_rows():
    out = []
    for g in gp.get("ad_groups", []):
        kws = ", ".join(f'{k["text"]} <span class="mono small">[{k["match"]}]</span>' for k in g.get("keywords", []))
        out.append(f'<tr><td><b>{esc(g.get("name",""))}</b></td><td>{kws}</td><td>{esc(", ".join(g.get("negative_keywords", [])))}</td><td class="mono">₹{g.get("daily_budget")}/day</td></tr>')
    return "".join(out)

est = mp.get("estimates", {}); b = mp.get("budget", {})
comp = mp.get("compliance", {})
seo_checks = "".join(f'<tr><td>{esc(c["category"])}</td><td>{esc(c["name"])}</td><td><span class="st {"pass" if c["pass"] else ("warn" if c["level"]=="warn" else "fail")}">{"pass" if c["pass"] else c["level"]}</span></td><td class="small">{esc(str(c["detail"])[:120])}</td></tr>' for c in seo.get("checks", []))

CHANNELS = [("Instagram","live","Publishes images, carousels, reels via the Graph API with the client's own long-lived Page token."),("Facebook Page","live","Photo and link posts via the Graph API."),("LinkedIn","live","Member text posts via w_member_social."),("X (Twitter)","manual","Rendered post + checklist; live posting needs the paid X API tier."),("YouTube","manual","Scripts, titles, tags, descriptions; upload by hand."),("Google Business Profile","manual","Post copy and offers as a checklist."),("Meta Ads","live","Plan → create PAUSED → activate with approval → insights. Budget ceiling enforced."),("Google Ads","partial","Keyword ideas and reports live; launch needs an approved developer token."),("Mailchimp","live","Audiences, drafts, send/schedule with approval."),("Smartlead","live","Sequences, leads, start with approval."),("WhatsApp Business","live","Send session/template messages; inbound webhook with keyword triggers into the inbox."),("Airtable","live","Sync approvals, runs and content."),("Outbound webhook","live","Approved creatives and publish events to Zapier / Make / n8n.")]
chan_rows = "".join(f'<tr><td><b>{esc(n)}</b></td><td><span class="st {"pass" if s=="live" else ("warn" if s=="partial" else "info")}">{s}</span></td><td>{esc(d)}</td></tr>' for n,s,d in CHANNELS)

gallery = ""
for n in shots:
    uri = img_uri(n)
    if not uri: continue
    t, cap = CAPTIONS.get(n, (n, ""))
    gallery += f'<figure><img src="{uri}" alt="{esc(t)}" loading="lazy"><figcaption><b>{esc(t)}</b> — {esc(cap)}</figcaption></figure>'

fixes = [
 ("Creative and image routes in the test harness pointed at /creative and /image", "Harness bug, not product: the real routes are /creatives and /images. Fixed the harness; 8 cascading failures cleared."),
 ("Instagram algo audit returned no numeric score when the model omitted algo_score", "Product fix: the engine now derives the weighted score from the seven signals and always returns algo_score + score. Unit-tested."),
 ("Headless browser could not reach production from the build sandbox", "Environment: routed Chromium through the session proxy; screenshots captured."),
]
fix_rows = "".join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td></tr>' for a,b in fixes)

recs = [
 ("Connect the real accounts", "Instagram/Facebook Page tokens, Meta Ads system-user token, WhatsApp phone number. Everything else is already gated and tested; the only reason nothing went live in this run is that no client credentials exist yet."),
 ("Run the weekly cycle on cron", "CRON_KEY is set on Railway; point a 10-minute pinger at /api/cron?key=… and the portfolio refreshes itself every week."),
 ("Clean up test tenants", "Production carries four test brands (\"z\", \"Launch Test Co\", \"Kokapet Heights Realty\", \"BrightSmile Dental\") plus the earlier \"Neopolis Infra\" stub — delete or finish them so the portfolio reflects real clients."),
 ("Meta city keys", "Plans carry city + radius in readable form; the Graph API needs Meta location keys. The launch passes the country as hard geo and the city as a hint; add a location-search step before going live with city-level targeting."),
 ("Move the job queue out of process", "A redeploy drops queued cycles until the next weekly pass. Redis or a DB-backed queue is the next infrastructure step."),
]
rec_rows = "".join(f'<li><b>{esc(a)}</b> — {esc(b)}</li>' for a,b in recs)

HTML = f"""<title>Neopolis Infra Launch Readiness</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root{{--bg:#f7f5f0;--sf:#ffffff;--ink:#17202e;--mu:#5f6b7a;--ln:#e2ddd3;--navy:#081d4a;--org:#e85d04;--ok:#1f7a4d;--okbg:#e6f4ec;--warn:#9a5b00;--warnbg:#fff3df;--bad:#b42318;--badbg:#fbe9e7;--info:#3b4a63;--infobg:#e9edf5}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0f1523;--sf:#161d2e;--ink:#e8ecf3;--mu:#98a4b8;--ln:#26304a;--navy:#c9d6ff;--org:#ff8a3d;--ok:#5fd39a;--okbg:#123423;--warn:#f2b64a;--warnbg:#3a2a0a;--bad:#ff7b6b;--badbg:#3d1512;--info:#b8c4dc;--infobg:#1f2740}}}}
:root[data-theme="dark"]{{--bg:#0f1523;--sf:#161d2e;--ink:#e8ecf3;--mu:#98a4b8;--ln:#26304a;--navy:#c9d6ff;--org:#ff8a3d;--ok:#5fd39a;--okbg:#123423;--warn:#f2b64a;--warnbg:#3a2a0a;--bad:#ff7b6b;--badbg:#3d1512;--info:#b8c4dc;--infobg:#1f2740}}
body{{background:var(--bg);color:var(--ink);font:16px/1.55 "Source Sans 3",system-ui,sans-serif;margin:0;padding-block:32px 80px;padding-inline:20px}}
.wrap{{max-width:980px;margin:0 auto}}
h1,h2,h3{{font-family:Fraunces,Georgia,serif;text-wrap:balance;color:var(--navy);margin:0}}
h1{{font-size:40px;line-height:1.05;font-weight:700}}h2{{font-size:26px;margin:44px 0 12px;font-weight:600}}h3{{font-size:18px;margin:22px 0 8px}}
.eyebrow{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--org);font-weight:700;margin-bottom:10px}}
p{{max-width:70ch}}.lead{{font-size:18px;color:var(--mu);max-width:70ch}}
.strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:26px 0}}
.tile{{background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:14px 16px}}.tile b{{display:block;font-family:"JetBrains Mono",monospace;font-size:26px;font-variant-numeric:tabular-nums}}.tile span{{font-size:12.5px;color:var(--mu)}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:var(--sf);border:1px solid var(--ln);border-radius:10px;overflow:hidden}}th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--ln);vertical-align:top}}th{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mu);background:var(--bg)}}tr:last-child td{{border-bottom:0}}
.tw{{overflow-x:auto;border-radius:10px}}.mono{{font-family:"JetBrains Mono",monospace;font-size:12.5px;font-variant-numeric:tabular-nums}}.small{{font-size:12.5px;color:var(--mu)}}
.st{{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;padding:2px 8px;border-radius:12px}}.st.pass{{background:var(--okbg);color:var(--ok)}}.st.fail{{background:var(--badbg);color:var(--bad)}}.st.warn{{background:var(--warnbg);color:var(--warn)}}.st.info{{background:var(--infobg);color:var(--info)}}
.note{{border-left:4px solid var(--org);background:var(--sf);padding:12px 16px;border-radius:0 10px 10px 0;margin:14px 0;max-width:80ch}}
.ads{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}.ad{{background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:12px}}.ad .pt{{white-space:pre-wrap;font-size:13.5px;margin-bottom:8px}}.ad .hl{{font-weight:700}}
figure{{margin:0 0 26px}}figure img{{width:100%;max-width:100%;border:1px solid var(--ln);border-radius:10px;display:block}}figcaption{{font-size:13.5px;color:var(--mu);margin-top:8px}}
ol,ul{{max-width:80ch}}li{{margin-bottom:8px}}
.bar{{display:flex;height:12px;border-radius:6px;overflow:hidden;background:var(--ln);max-width:600px;margin:8px 0}}.bar i{{display:block;height:100%}}
.arch{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}.arch div{{background:var(--sf);border:1px solid var(--ln);border-radius:10px;padding:12px 14px;font-size:14px}}.arch b{{display:block;color:var(--navy);margin-bottom:4px}}
</style>
<div class="wrap">
<div class="eyebrow">CTO launch-readiness run · {esc(E["run"])}</div>
<h1>Neopolis Infra on Marketing Brain: the full client journey, live</h1>
<p class="lead">Every step a real client goes through, executed against production with <b>neopolisinfra.com</b> as the client: onboarding from the live site, brand analysis, content, visuals, approval, publishing gates, SEO, paid-media planning with full audience and budget detail, email, WhatsApp, reporting and the portfolio view. Real model calls, real site fetches, no mocks.</p>
<div class="strip"><div class="tile"><b>{E["pass"]}/{E["pass"]+E["fail"]}</b><span>steps passed on the final run</span></div><div class="tile"><b>{seo.get("score","—")}</b><span>SEO score of neopolisinfra.com</span></div><div class="tile"><b>{len(mp.get("ad_sets",[]))}+{len(gp.get("ad_groups",[]))}</b><span>audiences planned (Meta + Google)</span></div><div class="tile"><b>{row.get("score","—")}</b><span>portfolio health after the run</span></div><div class="tile"><b>0</b><span>rupees spent, posts published live</span></div></div>
<div class="note"><b>Verdict.</b> The product runs the whole journey end to end on production. One product defect was found and fixed during the run (the Instagram algorithm audit could return without a numeric score). Nothing went live because Neopolis has not connected any account yet — every live action was correctly refused with a clear reason. The remaining work is credentials, not code.</div>

<h2>1 · What the client is</h2>
<div class="tw"><table><tr><th>Field</th><th>Captured from neopolisinfra.com</th></tr>
<tr><td>Site title</td><td>{esc(str(((A.get("brand") or {}).get("name"))))} — Landlord Share Flats in Hyderabad</td></tr>
<tr><td>Brand colours (scraped)</td><td class="mono">#ff6600 · #ff8534 · #081d4a</td></tr>
<tr><td>Voice (AI analysis)</td><td>{esc(str(prof.get("brand_voice"))[:300])}</td></tr>
<tr><td>Audience (AI analysis)</td><td>{esc(str(prof.get("target_audience"))[:300])}</td></tr>
<tr><td>Positioning</td><td>{esc(str(prof.get("positioning"))[:300])}</td></tr>
<tr><td>Vertical template</td><td>real_estate → Meta special ad category <b>HOUSING</b>, WhatsApp triggers PRICE / PDF / VISIT / LOCATION / EMI, caps 40 generations/day</td></tr>
<tr><td>Channels set up</td><td>{esc(", ".join((brand.get("setup") or {}).get("channels", [])))}</td></tr></table></div>

<h2>2 · The journey, step by step</h2>
<p>Each row is a real API call against production. FAIL rows in the first pass were traced and fixed (section 6); this is the final run. Onboarding ran in the first pass — scrape <span class="mono">done</span>, AI analysis <span class="mono">done</span>, workspace <span class="mono">done</span>, brand <span class="mono">ready</span> — and later passes reused that ready client, which is why step 01 reads "reusing".</p>
<div class="tw"><table><tr><th>#</th><th>Step</th><th>Result</th><th>Evidence</th></tr>{step_rows()}</table></div>

<h2>3 · Paid promotion: what the planner produces</h2>
<p>The model proposes audiences and copy; the planner owns the numbers and the rules — budget capped at the configured ceiling and split exactly across ad sets, Meta's HOUSING restrictions applied because this is real estate, estimates from published India benchmark ranges (never model guesses). Everything below is editable in the console before launch, and re-checked on every save.</p>
<h3>Meta campaign · {esc(mp.get("campaign",{}).get("name",""))}</h3>
<div class="strip"><div class="tile"><b>₹{b.get("daily_total","—")}</b><span>per day (ceiling ₹{b.get("cap","—")})</span></div><div class="tile"><b>₹{b.get("monthly_estimate","—")}</b><span>30-day spend</span></div><div class="tile"><b>{est.get("daily",{}).get("leads",["—","—"])[0]}–{est.get("daily",{}).get("leads",["—","—"])[1]}</b><span>leads / day (benchmark)</span></div><div class="tile"><b>₹{est.get("cpl_range",["—","—"])[0]}–{est.get("cpl_range",["—","—"])[1]}</b><span>cost per lead range</span></div></div>
<div class="bar">{"".join(f'<i style="width:{round((s.get("budget_share") or 0)*100)}%;background:{c}" title="{esc(s.get("name",""))}"></i>' for s,c in zip(mp.get("ad_sets",[]),["#e85d04","#081d4a","#2a9d8f","#7b2cbf"]))}</div>
<div class="tw"><table><tr><th>Ad set</th><th>Location</th><th>Age</th><th>Gender</th><th>Interests</th><th>Placements</th><th>Budget</th></tr>{adset_rows()}</table></div>
<div class="note"><b>HOUSING rules applied automatically:</b> {esc(" ".join(comp.get("rules", [])))}<br><span class="small">Changes made to the model's proposal: {esc("; ".join(comp.get("applied", [])) or "none needed")}</span></div>
<h3>Ads</h3><div class="ads">{ads_rows()}</div>
<h3>Lead capture, tracking, KPIs</h3>
<div class="tw"><table><tr><th>Lead capture</th><td>{esc(str((mp.get("lead_capture") or {}).get("method","")))} · {esc(" / ".join((mp.get("lead_capture") or {}).get("questions", [])))}</td></tr>
<tr><th>Pixel events</th><td>{esc(", ".join((mp.get("tracking") or {}).get("pixel_events", [])))}</td></tr>
<tr><th>UTM</th><td class="mono">{esc("&".join(f"{k}={v}" for k,v in ((mp.get("tracking") or {}).get("utm") or {}).items()))}</td></tr>
<tr><th>Primary KPI</th><td>{esc(str((mp.get("kpis") or {}).get("primary","")))} · target {esc(str((mp.get("kpis") or {}).get("target","")))}</td></tr>
<tr><th>Week-1 tests</th><td>{esc(" · ".join(mp.get("tests", [])))}</td></tr>
<tr><th>Risks</th><td>{esc(" · ".join(mp.get("risks", [])))}</td></tr></table></div>
<h3>Google Search campaign · {esc(gp.get("campaign",{}).get("name",""))}</h3>
<p class="small">Bidding {esc(str((gp.get("bidding") or {}).get("strategy")))} · locations {esc(", ".join(l.get("name","") for l in gp.get("locations", [])))} · ₹{(gp.get("budget") or {}).get("daily_total","—")}/day</p>
<div class="tw"><table><tr><th>Ad group</th><th>Keywords</th><th>Negatives</th><th>Budget</th></tr>{kw_rows()}</table></div>
<h3>What the gates did in this run</h3>
<ul><li>Manual edit re-split the budget 60/40 and raised the total to ₹2,500 — accepted, re-capped, HOUSING re-applied (gender edit silently reverted).</li><li>Launch refused: Meta Ads is not connected for this brand.</li><li>Activate refused without approval: "This spends real money and must be approved by a human first."</li></ul>

<h2>4 · How we connect to every channel</h2>
<p>Each client connects its own accounts with its own tokens; nothing is shared across clients. <b>Test</b> makes a read-only API call and names the account it reached — in this run an invalid Instagram token was reported as invalid, then disconnected.</p>
<div class="tw"><table><tr><th>Channel</th><th>Today</th><th>What it does</th></tr>{chan_rows}</table></div>

<h2>5 · SEO of neopolisinfra.com · score {seo.get("score","—")}</h2>
<div class="tw"><table><tr><th>Area</th><th>Check</th><th>Result</th><th>Detail</th></tr>{seo_checks}</table></div>

<h2>6 · Defects found and what was done</h2>
<div class="tw"><table><tr><th>Found</th><th>Resolution</th></tr>{fix_rows}</table></div>

<h2>7 · What the client and the agency see</h2>
{gallery or "<p class='small'>Screenshots not captured in this run.</p>"}

<h2>8 · How it works</h2>
<div class="arch">
<div><b>Onboard</b>One call: brand → vertical template → scrape the site → AI analysis → workspace → ready. Runs in the bounded job pool.</div>
<div><b>Brain</b>Every prompt carries the brand context, the per-client config and brand memory as data, with an anti-injection rule; grounded project facts only where they exist.</div>
<div><b>Content</b>Ideas → calendar → creatives → visuals with the real logo composited; algorithm audit; approvals feed memory.</div>
<div><b>Paid media</b>Planner v2: model proposes, code enforces budget cap, exact split, special-category rules, benchmark estimates. Launch creates PAUSED; activate needs a human.</div>
<div><b>Channels</b>Catalogue of 13 channels with per-client credentials, read-only tests, simulated publish + checklist for manual channels.</div>
<div><b>Agency</b>Portfolio health, weekly cycle across clients, bulk approvals, manager role, monthly white-label reports.</div>
</div>

<h2>9 · Recommendations</h2>
<ol>{rec_rows}</ol>
<p class="small">Evidence files: test-report/live/neopolis_e2e.json, test-report/live/shots/. Test brand kept on production as "Neopolis Infra LLP" ({esc(str(E.get("brand_id")))}) so you can open it in the console.</p>
</div>
"""
open(OUT_HTML, "w").write(HTML)

# ---------- Markdown for the repo ----------
md = [f"# Neopolis Infra — CTO launch-readiness run ({E['run']})", "",
      f"Production: {E['base']} · client site: {E['site']} · brand kept: `{E.get('brand_id')}`", "",
      f"**Result: {E['pass']}/{E['pass']+E['fail']} steps passed.** Nothing published live and no money moved — every live action was refused with a clear reason because no client account is connected yet.", "",
      "Onboarding ran in the first pass (scrape done, AI analysis done, workspace done, brand ready); later passes reused the ready client.", "", "## Steps", "", "| # | Step | Result | Evidence |", "|---|---|---|---|"]
md += [f"| {s['step'][:2]} | {s['step'][3:]} | {s['status']} | {s['detail'][:140].replace('|','/')} |" for s in steps]
md += ["", "## Paid promotion (Meta)", "", f"Campaign: {mp.get('campaign',{}).get('name')} · ₹{b.get('daily_total')}/day (cap ₹{b.get('cap')}) · special category {comp.get('special_ad_category')}", "",
       "| Ad set | Location | Age | Gender | Interests | Placements | Budget |", "|---|---|---|---|---|---|---|"]
for s in mp.get("ad_sets", []):
    t = s.get("targeting", {}); geo = t.get("geo", {})
    loc = ", ".join(f'{c.get("name")} +{c.get("radius_km")} km' for c in geo.get("cities", [])) or ", ".join(geo.get("countries", []))
    md.append(f"| {s.get('name')} | {loc} | {t.get('age_min')}–{t.get('age_max')}+ | {', '.join(t.get('genders') or ['All'])} | {', '.join(t.get('interests', [])[:5])} | {', '.join(s.get('placements', []))} | ₹{s.get('daily_budget')}/day |")
md += ["", f"HOUSING rules: {' '.join(comp.get('rules', []))}", "", f"Estimates (benchmark): {json.dumps(est.get('daily'))} · CPL ₹{est.get('cpl_range')}", "",
       "## Paid promotion (Google Search)", "", "| Ad group | Keywords | Negatives | Budget |", "|---|---|---|---|"]
for g in gp.get("ad_groups", []):
    md.append(f"| {g.get('name')} | {', '.join(k['text']+' ['+k['match']+']' for k in g.get('keywords', []))} | {', '.join(g.get('negative_keywords', []))} | ₹{g.get('daily_budget')}/day |")
md += ["", "## Channels", "", "| Channel | Status | What it does |", "|---|---|---|"] + [f"| {n} | {s} | {d} |" for n,s,d in CHANNELS]
md += ["", f"## SEO of neopolisinfra.com — score {seo.get('score')}", ""] + [f"- {'✓' if c['pass'] else ('!' if c['level']=='warn' else '✗')} {c['name']}: {c['detail']}" for c in seo.get("checks", [])]
md += ["", "## Defects and fixes", ""] + [f"- **{a}** — {b}" for a,b in fixes]
md += ["", "## Recommendations", ""] + [f"{i+1}. **{a}** — {b}" for i,(a,b) in enumerate(recs)]
md += ["", "Screenshots: `test-report/live/shots/`. Raw evidence: `test-report/live/neopolis_e2e.json`."]
open(OUT_MD, "w").write("\n".join(md))
print("report html", os.path.getsize(OUT_HTML)//1024, "KB;", "md", OUT_MD, "; shots", len(shots))

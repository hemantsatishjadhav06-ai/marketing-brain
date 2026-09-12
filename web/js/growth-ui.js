/* Growth UI — shared between the operator console and the brand app.
   Renders a paid-media plan (audiences, budget, placements, schedule, ads,
   estimates, compliance) as an editable review screen, and the Connections
   hub (every channel, status, connect / test / disconnect). Depends only on
   global esc() and api() from the host page. */
(function(){
  const E = s => (typeof esc==="function"?esc(s):String(s==null?"":s));
  const money = (v,c) => `${c||"₹"}${Number(v||0).toLocaleString("en-IN",{maximumFractionDigits:0})}`;
  const CUR = {INR:"₹",USD:"$",EUR:"€",GBP:"£",AED:"د.إ"};
  const PLACE = {facebook_feed:"FB feed",instagram_feed:"IG feed",instagram_reels:"IG reels",instagram_stories:"IG stories",facebook_reels:"FB reels",facebook_stories:"FB stories",audience_network:"Audience Network",messenger:"Messenger"};
  const CSS = `
  .gp{--acc:var(--accent,var(--yel,#6d5dfc));--ln:var(--line,#e6e3dc);--mu:var(--muted,var(--mut,#6b665d));--sf:var(--surface,var(--panel,#fff));--sf2:var(--surface-2,var(--panel2,#f4f2ec));font-size:13.5px}
  .gp .hd{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}.gp .hd h2{margin:0;font-size:18px}
  .gp .pill{font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;background:var(--sf2);color:var(--mu)}
  .gp .pill.ok{background:#e9f8ef;color:#15803d}.gp .pill.warn{background:#fff4e0;color:#b45309}.gp .pill.bad{background:#fde8e8;color:#c62828}.gp .pill.acc{background:var(--acc);color:#fff}
  .gp .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:12px 0}
  .gp .tile{background:var(--sf2);border-radius:12px;padding:10px 12px}.gp .tile b{display:block;font-size:18px}.gp .tile span{font-size:11.5px;color:var(--mu)}
  .gp .box{border:1px solid var(--ln);border-radius:12px;padding:14px;background:var(--sf);margin-bottom:12px}
  .gp .box h3{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--mu)}
  .gp .bar{display:flex;height:14px;border-radius:8px;overflow:hidden;background:var(--sf2);margin:6px 0}.gp .bar i{display:block;height:100%}
  .gp .kv{display:grid;grid-template-columns:120px 1fr;gap:4px 10px;font-size:12.5px}.gp .kv b{color:var(--mu);font-weight:600}
  .gp .chips span{display:inline-block;font-size:11.5px;padding:2px 8px;border:1px solid var(--ln);border-radius:14px;margin:2px 4px 2px 0;background:var(--sf)}
  .gp input,.gp select,.gp textarea{font:inherit;padding:7px 9px;border:1px solid var(--ln);border-radius:9px;background:var(--sf);color:inherit;width:100%;box-sizing:border-box;margin:0}
  .gp .row2{display:grid;grid-template-columns:1fr 1fr;gap:8px}.gp .row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
  .gp .fl{display:flex;flex-direction:column;gap:3px;margin-bottom:8px}.gp .fl label{font-size:11px;color:var(--mu);font-weight:700}
  .gp .acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  .gp .notice{border-left:4px solid #b45309;background:#fff8ec;padding:10px 12px;border-radius:8px;font-size:12.5px;margin:8px 0}
  .gp .notice.ok{border-color:#15803d;background:#eef9f1}
  .gp .adcard{border:1px solid var(--ln);border-radius:12px;padding:12px;background:var(--sf)}
  .gp .adcard .mock{border:1px solid var(--ln);border-radius:10px;padding:10px;background:var(--sf2);margin-bottom:8px}
  .gp .mock .pt{white-space:pre-wrap;font-size:12.5px;margin-bottom:8px}.gp .mock .img{height:120px;border-radius:8px;background:linear-gradient(135deg,var(--acc),#0a2540);display:grid;place-items:center;color:#fff;font-size:11px;opacity:.85}
  .gp .mock .hl{font-weight:700;font-size:13px;margin-top:8px}.gp .mock .ds{font-size:11.5px;color:var(--mu)}.gp .mock .cta{display:inline-block;margin-top:6px;font-size:11px;font-weight:700;padding:4px 10px;border:1px solid var(--ln);border-radius:6px}
  .gp .hub{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
  .gp .ch{border:1px solid var(--ln);border-radius:12px;padding:12px;background:var(--sf);display:flex;flex-direction:column;gap:6px}
  .gp .ch .nm{display:flex;align-items:center;gap:8px;font-weight:700}.gp .ch .nm .ic{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;font-size:15px;background:var(--sf2)}
  .gp .ch ul{margin:0;padding-left:16px;font-size:12px;color:var(--mu)}.gp .ch details{font-size:12px}.gp .ch summary{cursor:pointer;color:var(--acc);font-weight:600}
  .gp .btn2{font:inherit;font-weight:700;font-size:12.5px;padding:7px 12px;border-radius:9px;border:1px solid var(--ln);background:var(--sf);cursor:pointer;color:inherit}
  .gp .btn2.p{background:var(--acc);color:#fff;border-color:var(--acc)}.gp .btn2.ok{background:#15803d;color:#fff;border-color:#15803d}.gp .btn2:disabled{opacity:.5}
  @media(max-width:640px){.gp .row2,.gp .row3{grid-template-columns:1fr}.gp .kv{grid-template-columns:1fr}}`;
  function ensureCss(){ if(document.getElementById("growthUiCss")) return; const s=document.createElement("style"); s.id="growthUiCss"; s.textContent=CSS; document.head.appendChild(s); }

  const COLORS=["#6d5dfc","#0ea5e9","#f59e0b","#10b981","#ef4444","#8b5cf6"];

  function targetingBlock(t){
    t=t||{}; const geo=t.geo||{};
    const cities=(geo.cities||[]).map(c=>`${E(c.name)}${c.radius_km?` · ${c.radius_km} km`:""}`).join(", ");
    return `<div class="kv">
      <b>Location</b><span>${cities||E((geo.countries||[]).join(", "))||"—"}${cities&&geo.countries?` <small style="color:var(--mu)">(${E(geo.countries.join(", "))})</small>`:""}</span>
      <b>Age</b><span>${t.age_min??18}–${t.age_max??65}${t.age_max>=65?"+":""}</span>
      <b>Gender</b><span>${(t.genders||[]).length?E(t.genders.join(", ")):"All"}</span>
      <b>Languages</b><span>${(t.languages||[]).length?E(t.languages.join(", ")):"All"}</span>
      <b>Interests</b><span class="chips">${(t.interests||[]).map(i=>`<span>${E(i)}</span>`).join("")||"Broad"}</span>
      ${(t.behaviors||[]).length?`<b>Behaviours</b><span class="chips">${t.behaviors.map(i=>`<span>${E(i)}</span>`).join("")}</span>`:""}
      ${(t.custom_audiences||[]).length?`<b>Custom</b><span class="chips">${t.custom_audiences.map(i=>`<span>${E(i)}</span>`).join("")}</span>`:""}
      ${t.lookalike?`<b>Lookalike</b><span>${E(t.lookalike)}</span>`:""}
      ${(t.exclusions||[]).length?`<b>Exclude</b><span>${E(t.exclusions.join(", "))}</span>`:""}
    </div>`;
  }
  function adMock(a){
    return `<div class="mock"><div class="pt">${E(a.primary_text)}</div><div class="img">${E(a.format||"single_image")} · ${E(a.visual_direction||"visual")}</div>
      <div class="hl">${E(a.headline)}</div><div class="ds">${E(a.description)}</div><span class="cta">${E((a.cta||"LEARN_MORE").replace(/_/g," "))}</span></div>`;
  }

  function renderMeta(plan, o){
    const cur=CUR[plan.currency]||plan.currency||"₹"; const b=plan.budget||{}; const est=plan.estimates||{}; const comp=plan.compliance||{}; const camp=plan.campaign||{};
    const housing=comp.special_ad_category&&comp.special_ad_category!=="NONE";
    const sets=plan.ad_sets||[]; const ads=plan.ads||[];
    let h=`<div class="gp" data-cid="${E(o.campaignId||"")}"><div class="hd"><h2>${E(camp.name||plan.name)}</h2>
      <span class="pill acc">Meta</span><span class="pill">${E((camp.objective||"").replace("OUTCOME_",""))}</span>
      <span class="pill ${o.status==="live"?"ok":o.status==="approved"?"warn":""}">${E(o.status||"draft")}</span>
      ${housing?`<span class="pill warn">Special category: ${E(comp.special_ad_category)}</span>`:""}</div>`;
    if(camp.why) h+=`<p style="color:var(--mu);margin:0 0 8px">${E(camp.why)}</p>`;
    h+=`<div class="tiles">
      <div class="tile"><b>${money(b.daily_total,cur)}</b><span>per day (cap ${money(b.cap,cur)})</span></div>
      <div class="tile"><b>${money(b.monthly_estimate,cur)}</b><span>30-day spend</span></div>
      <div class="tile"><b>${(est.daily||{}).leads?`${est.daily.leads[0]}–${est.daily.leads[1]}`:"—"}</b><span>leads / day (benchmark)</span></div>
      <div class="tile"><b>${est.cpl_range?`${cur}${est.cpl_range[0]}–${est.cpl_range[1]}`:"—"}</b><span>cost per lead range</span></div>
      <div class="tile"><b>${(est.daily||{}).impressions?`${Math.round(est.daily.impressions[0]/1000)}k–${Math.round(est.daily.impressions[1]/1000)}k`:"—"}</b><span>impressions / day</span></div>
    </div>`;
    if(housing) h+=`<div class="notice"><b>${E(comp.special_ad_category)} rules applied automatically</b> — ${(comp.rules||[]).map(E).join(" ")}${(comp.applied||[]).length?`<br><small>Changed: ${comp.applied.map(E).join("; ")}</small>`:""}</div>`;
    h+=`<div class="notice ok">Nothing spends yet. Launch creates everything <b>PAUSED</b> on Meta; activation needs your explicit approval and stays under the ${money(b.cap,cur)}/day ceiling.</div>`;
    // budget split
    h+=`<div class="box"><h3>Budget split</h3><div class="bar">${sets.map((s,i)=>`<i style="width:${Math.round((s.budget_share||0)*100)}%;background:${COLORS[i%COLORS.length]}" title="${E(s.name)}"></i>`).join("")}</div>
      <div class="chips">${sets.map((s,i)=>`<span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${COLORS[i%COLORS.length]};margin-right:5px"></i>${E(s.name)} · ${money(s.daily_budget,cur)}/day (${Math.round((s.budget_share||0)*100)}%)</span>`).join("")}</div></div>`;
    // ad sets
    h+=`<div class="box"><h3>Audiences (${sets.length} ad sets)</h3><div class="row2">`;
    sets.forEach((s,i)=>{ const sc=s.schedule||{};
      h+=`<div class="adcard"><div class="hd" style="margin-bottom:6px"><b style="font-size:14px">${E(s.name)}</b><span class="pill" style="background:${COLORS[i%COLORS.length]}22;color:${COLORS[i%COLORS.length]}">${money(s.daily_budget,cur)}/day</span></div>
        ${s.audience_label?`<div style="font-size:12.5px;margin-bottom:6px">${E(s.audience_label)}</div>`:""}
        ${s.rationale?`<div style="font-size:12px;color:var(--mu);margin-bottom:8px">${E(s.rationale)}</div>`:""}
        ${targetingBlock(s.targeting)}
        <div class="kv" style="margin-top:6px"><b>Placements</b><span class="chips">${(s.placements||[]).map(p=>`<span>${E(PLACE[p]||p)}</span>`).join("")}</span>
          <b>Optimise for</b><span>${E((s.optimization_goal||"").replace(/_/g," ").toLowerCase())} · ${E((s.bid_strategy||"").replace(/_/g," ").toLowerCase())}</span>
          <b>Schedule</b><span>${E(sc.start||"on approval")}${sc.end?` → ${E(sc.end)}`:" · open-ended"}${sc.dayparting?` · ${E(sc.dayparting)}`:""}</span>
          <b>Ads</b><span>${(s.ad_ids||[]).map(E).join(", ")||"all"}</span></div>
        ${o.editable?`<details style="margin-top:8px"><summary style="cursor:pointer;color:var(--acc);font-weight:600;font-size:12px">Edit audience & budget</summary>
          <div class="row3" style="margin-top:8px"><div class="fl"><label>Budget share %</label><input type="number" min="0" max="100" data-e="share" data-i="${i}" value="${Math.round((s.budget_share||0)*100)}"></div>
          <div class="fl"><label>Age min</label><input type="number" min="18" max="65" data-e="age_min" data-i="${i}" value="${s.targeting?.age_min??18}" ${housing?"disabled":""}></div>
          <div class="fl"><label>Age max</label><input type="number" min="18" max="65" data-e="age_max" data-i="${i}" value="${s.targeting?.age_max??65}" ${housing?"disabled":""}></div></div>
          <div class="fl"><label>Cities (name:radius_km, comma-separated)</label><input data-e="cities" data-i="${i}" value="${E(((s.targeting||{}).geo||{}).cities?.map(c=>`${c.name}:${c.radius_km||24}`).join(", ")||"")}"></div>
          <div class="fl"><label>Interests (comma-separated)</label><input data-e="interests" data-i="${i}" value="${E((s.targeting?.interests||[]).join(", "))}"></div>
          <div class="fl"><label>Placements</label><select multiple size="4" data-e="placements" data-i="${i}">${Object.keys(PLACE).map(p=>`<option value="${p}" ${(s.placements||[]).includes(p)?"selected":""}>${PLACE[p]}</option>`).join("")}</select></div>
          <div class="row2"><div class="fl"><label>Start</label><input type="date" data-e="start" data-i="${i}" value="${E(sc.start||"")}"></div><div class="fl"><label>Dayparting</label><input data-e="dayparting" data-i="${i}" value="${E(sc.dayparting||"")}"></div></div></details>`:""}
      </div>`; });
    h+=`</div></div>`;
    // ads
    h+=`<div class="box"><h3>Ads (${ads.length} creatives)</h3><div class="row2">${ads.map((a,i)=>`<div class="adcard"><div class="hd" style="margin-bottom:6px"><b>Ad ${E(a.id||i+1)}</b><span class="pill">${E(a.format||"single_image")}</span></div>${adMock(a)}
      ${o.editable?`<details><summary style="cursor:pointer;color:var(--acc);font-weight:600;font-size:12px">Edit copy</summary><div class="fl"><label>Primary text</label><textarea rows="3" data-a="primary_text" data-i="${i}">${E(a.primary_text)}</textarea></div>
      <div class="row2"><div class="fl"><label>Headline (≤40)</label><input maxlength="40" data-a="headline" data-i="${i}" value="${E(a.headline)}"></div><div class="fl"><label>Description (≤30)</label><input maxlength="30" data-a="description" data-i="${i}" value="${E(a.description)}"></div></div>
      <div class="row2"><div class="fl"><label>CTA</label><select data-a="cta" data-i="${i}">${["LEARN_MORE","SIGN_UP","WHATSAPP_MESSAGE","CALL_NOW","GET_QUOTE","BOOK_NOW","SHOP_NOW"].map(c=>`<option ${a.cta===c?"selected":""}>${c}</option>`).join("")}</select></div><div class="fl"><label>Link</label><input data-a="link" data-i="${i}" value="${E(a.link||"")}"></div></div></details>`:""}</div>`).join("")}</div></div>`;
    // lead capture + tracking + kpis + tests
    const lc=plan.lead_capture||{}, tr=plan.tracking||{}, k=plan.kpis||{};
    h+=`<div class="row2"><div class="box"><h3>Lead capture & tracking</h3><div class="kv">
        <b>Method</b><span>${E(lc.method||"—")}</span>${(lc.questions||[]).length?`<b>Form questions</b><span>${lc.questions.map(E).join(" · ")}</span>`:""}${lc.follow_up?`<b>Follow-up</b><span>${E(lc.follow_up)}</span>`:""}
        <b>Pixel events</b><span>${(tr.pixel_events||[]).map(E).join(", ")||"—"}</span><b>UTM</b><span>${tr.utm?E(Object.entries(tr.utm).map(([a,b])=>`${a}=${b}`).join("&")):"—"}</span></div></div>
      <div class="box"><h3>KPIs, tests, risks</h3><div class="kv"><b>Primary KPI</b><span>${E(k.primary||"—")}${k.target?` · target ${E(k.target)}`:""}</span>
        ${(k.secondary||[]).length?`<b>Secondary</b><span>${k.secondary.map(E).join(", ")}</span>`:""}
        ${(plan.tests||[]).length?`<b>Week-1 tests</b><span>${plan.tests.map(E).join(" · ")}</span>`:""}
        ${(plan.risks||[]).length?`<b>Risks</b><span>${plan.risks.map(E).join(" · ")}</span>`:""}</div>
        <div style="font-size:11px;color:var(--mu);margin-top:8px">${E(est.basis||"")}</div></div></div>`;
    h+=`<div class="acts" id="gpActs"></div></div>`;
    return h;
  }

  function renderGoogle(plan,o){
    const cur=CUR[plan.currency]||"₹"; const b=plan.budget||{}; const est=plan.estimates||{}; const camp=plan.campaign||{}; const groups=plan.ad_groups||[];
    let h=`<div class="gp" data-cid="${E(o.campaignId||"")}"><div class="hd"><h2>${E(camp.name||plan.name)}</h2><span class="pill acc">Google Search</span><span class="pill">${E((plan.bidding||{}).strategy||"")}</span><span class="pill ${o.status==="live"?"ok":""}">${E(o.status||"draft")}</span></div>`;
    h+=`<div class="tiles"><div class="tile"><b>${money(b.daily_total,cur)}</b><span>per day (cap ${money(b.cap,cur)})</span></div><div class="tile"><b>${money(b.monthly_estimate,cur)}</b><span>30-day spend</span></div>
      <div class="tile"><b>${(est.daily||{}).clicks?`${est.daily.clicks[0]}–${est.daily.clicks[1]}`:"—"}</b><span>clicks / day (benchmark)</span></div><div class="tile"><b>${est.cpl_range?`${cur}${est.cpl_range[0]}–${est.cpl_range[1]}`:"—"}</b><span>cost per lead range</span></div></div>`;
    h+=`<div class="notice ok">Created PAUSED on Google Ads; enabling needs approval and an approved developer token.</div>`;
    h+=`<div class="box"><h3>Targeting</h3><div class="kv"><b>Locations</b><span>${(plan.locations||[]).map(l=>`${E(l.name)}${l.radius_km?` · ${l.radius_km} km`:""}`).join(", ")}</span><b>Languages</b><span>${(plan.languages||[]).map(E).join(", ")}</span><b>Schedule</b><span>${E((plan.schedule||{}).days||"all days")} · ${E((plan.schedule||{}).hours||"all hours")}</span></div></div>`;
    h+=`<div class="box"><h3>Ad groups (${groups.length})</h3><div class="row2">${groups.map((g,i)=>`<div class="adcard"><div class="hd" style="margin-bottom:6px"><b>${E(g.name)}</b><span class="pill">${money(g.daily_budget,cur)}/day</span></div>
      ${g.theme?`<div style="font-size:12px;color:var(--mu);margin-bottom:6px">${E(g.theme)}</div>`:""}
      <div class="kv"><b>Keywords</b><span class="chips">${(g.keywords||[]).map(k=>`<span>${E(k.text)} <small>${E(k.match)}</small></span>`).join("")}</span>
      <b>Negatives</b><span>${(g.negative_keywords||[]).map(E).join(", ")||"—"}</span></div>
      <div class="mock" style="margin-top:8px"><div style="font-size:11px;color:#1a0dab">Sponsored · ${E((g.rsa||{}).final_url||"")}</div><div class="hl" style="color:#1a0dab">${((g.rsa||{}).headlines||[]).slice(0,3).map(E).join(" | ")}</div><div class="ds">${((g.rsa||{}).descriptions||[]).slice(0,2).map(E).join(" ")}</div>
      ${((g.extensions||{}).sitelinks||[]).length?`<div class="chips" style="margin-top:6px">${g.extensions.sitelinks.map(s=>`<span>${E(s.text)}</span>`).join("")}</div>`:""}</div>
      ${g.rsa?`<details><summary style="cursor:pointer;color:var(--acc);font-weight:600;font-size:12px">All ${(g.rsa.headlines||[]).length} headlines · ${(g.rsa.descriptions||[]).length} descriptions</summary><ul style="font-size:12px;margin:6px 0;padding-left:16px">${(g.rsa.headlines||[]).map(x=>`<li>${E(x)}</li>`).join("")}${(g.rsa.descriptions||[]).map(x=>`<li><i>${E(x)}</i></li>`).join("")}</ul></details>`:""}
      ${o.editable?`<details><summary style="cursor:pointer;color:var(--acc);font-weight:600;font-size:12px">Edit</summary><div class="row2"><div class="fl"><label>Budget share %</label><input type="number" min="0" max="100" data-g="share" data-i="${i}" value="${Math.round((g.budget_share||0)*100)}"></div><div class="fl"><label>Final URL</label><input data-g="final_url" data-i="${i}" value="${E((g.rsa||{}).final_url||"")}"></div></div>
      <div class="fl"><label>Keywords (text:MATCH, comma-separated)</label><textarea rows="3" data-g="keywords" data-i="${i}">${E((g.keywords||[]).map(k=>`${k.text}:${k.match}`).join(", "))}</textarea></div>
      <div class="fl"><label>Negative keywords</label><input data-g="negatives" data-i="${i}" value="${E((g.negative_keywords||[]).join(", "))}"></div></details>`:""}</div>`).join("")}</div></div>`;
    const tr=plan.tracking||{}, k=plan.kpis||{};
    h+=`<div class="row2"><div class="box"><h3>Tracking</h3><div class="kv"><b>Conversions</b><span>${(tr.conversion_actions||[]).map(E).join(", ")||"—"}</span><b>UTM</b><span>${tr.utm?E(Object.entries(tr.utm).map(([a,b])=>`${a}=${b}`).join("&")):"—"}</span></div></div>
      <div class="box"><h3>KPIs & compliance</h3><div class="kv"><b>Primary</b><span>${E(k.primary||"—")}${k.target?` · ${E(k.target)}`:""}</span>${((plan.compliance||{}).policy_notes||[]).length?`<b>Policy</b><span>${plan.compliance.policy_notes.map(E).join(" ")}</span>`:""}${(plan.tests||[]).length?`<b>Tests</b><span>${plan.tests.map(E).join(" · ")}</span>`:""}</div><div style="font-size:11px;color:var(--mu);margin-top:8px">${E(est.basis||"")}</div></div></div>`;
    h+=`<div class="acts" id="gpActs"></div></div>`;
    return h;
  }

  /* Collect operator edits from the rendered plan back into a plan patch. */
  function collectEdits(root, plan, network){
    const p=JSON.parse(JSON.stringify(plan));
    const q=s=>[...root.querySelectorAll(s)];
    if(network==="meta"){
      q("[data-e]").forEach(el=>{ const i=+el.dataset.i, s=p.ad_sets[i]; if(!s) return; s.targeting=s.targeting||{}; s.targeting.geo=s.targeting.geo||{}; s.schedule=s.schedule||{};
        const v=el.value; switch(el.dataset.e){
          case "share": s.budget_share=(+v||0)/100; break;
          case "age_min": s.targeting.age_min=+v; break;
          case "age_max": s.targeting.age_max=+v; break;
          case "cities": s.targeting.geo.cities=v.split(",").map(x=>x.trim()).filter(Boolean).map(x=>{const [n,r]=x.split(":");return {name:n.trim(),radius_km:+(r||24)};}); break;
          case "interests": s.targeting.interests=v.split(",").map(x=>x.trim()).filter(Boolean); break;
          case "placements": s.placements=[...el.selectedOptions].map(o=>o.value); break;
          case "start": s.schedule.start=v||null; break;
          case "dayparting": s.schedule.dayparting=v; break; } });
      q("[data-a]").forEach(el=>{ const a=p.ads[+el.dataset.i]; if(a) a[el.dataset.a]=el.value; });
    } else {
      q("[data-g]").forEach(el=>{ const g=p.ad_groups[+el.dataset.i]; if(!g) return; g.rsa=g.rsa||{}; const v=el.value; switch(el.dataset.g){
        case "share": g.budget_share=(+v||0)/100; break;
        case "final_url": g.rsa.final_url=v; break;
        case "keywords": g.keywords=v.split(",").map(x=>x.trim()).filter(Boolean).map(x=>{const [t,m]=x.split(":");return {text:t.trim(),match:(m||"PHRASE").trim().toUpperCase()};}); break;
        case "negatives": g.negative_keywords=v.split(",").map(x=>x.trim()).filter(Boolean); break; } });
    }
    const tot=root.querySelector("[data-budget]"); if(tot) p.daily_budget=+tot.value;
    return p;
  }

  const ICONS={social:"📣",ads:"🎯",email:"✉️",messaging:"💬",data:"🔗"};
  const STATUS={live:["ok","Live API"],partial:["warn","Partial"],manual:["","Manual checklist"]};
  function renderHub(hub, o){
    const groups=hub.groups||[]; const chans=hub.channels||[];
    let h=`<div class="gp">`;
    if(o.intro!==false) h+=`<div class="notice ok"><b>How connections work.</b> Each client connects its own accounts with its own tokens — we never share credentials across clients, never post without an approval, and every ad action is capped and human-gated. <b>Test</b> makes a read-only call to prove the token works and names the account.</div>`;
    for(const [gid,glabel] of groups){
      const rows=chans.filter(c=>c.group===gid); if(!rows.length) continue;
      h+=`<h3 style="margin:16px 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--mu)">${ICONS[gid]||""} ${E(glabel)}</h3><div class="hub">`;
      for(const c of rows){ const st=STATUS[c.status]||["",c.status]; const lt=c.last_test;
        h+=`<div class="ch" id="ch-${E(c.id)}"><div class="nm"><span class="ic">${ICONS[c.group]||"•"}</span><span>${E(c.label)}</span><span class="pill ${st[0]}" style="margin-left:auto">${st[1]}</span></div>
          <div>${c.connected?`<span class="pill ok">Connected</span>`:`<span class="pill">Not connected</span>`} ${lt?`<span class="pill ${lt.ok?"ok":"bad"}" title="${E(lt.detail||"")}">${lt.ok?"✓ "+E(lt.account||"verified"):"✗ "+E((lt.detail||"failed").slice(0,40))}</span>`:""}</div>
          <ul>${(c.can||[]).slice(0,3).map(x=>`<li>${E(x)}</li>`).join("")}</ul>
          ${(c.cannot||[]).length?`<div style="font-size:11.5px;color:var(--mu)">Not yet: ${c.cannot.map(E).join("; ")}</div>`:""}
          <details><summary>Setup steps${c.docs?` · <a href="${E(c.docs)}" target="_blank" rel="noopener">docs ↗</a>`:""}</summary><ol style="padding-left:16px;margin:6px 0">${(c.steps||[]).map(s=>`<li>${E(s)}</li>`).join("")}</ol></details>
          ${o.canEdit?`<details ${o.open===c.id?"open":""}><summary>${c.connected?"Update credentials":"Connect"}</summary><div style="margin-top:6px">${(c.fields||[]).map(f=>`<div class="fl"><label>${E(f.label)}</label><input data-ch="${E(c.id)}" data-k="${E(f.key)}" type="${f.secret?"password":"text"}" placeholder="${E(f.key)}" autocomplete="off"></div>`).join("")}
            <button class="btn2 p" onclick="GrowthUI.connect('${E(c.id)}')">Save & test</button></div></details>`:""}
          <div class="acts" style="margin-top:auto">${c.connected?`<button class="btn2" onclick="GrowthUI.test('${E(c.id)}')">Test connection</button>`:""}${c.connected&&o.canEdit?`<button class="btn2" onclick="GrowthUI.disconnect('${E(c.id)}')">Disconnect</button>`:""}</div></div>`;
      }
      h+=`</div>`;
    }
    h+=`</div>`; return h;
  }

  const G = {
    renderPlan(plan, o){ ensureCss(); o=o||{}; return (plan.network==="google"||o.network==="google")?renderGoogle(plan,o):renderMeta(plan,o); },
    renderHub(hub,o){ ensureCss(); return renderHub(hub,o||{}); },
    collectEdits,
    brandId:null, onHubChange:null,
    async connect(ch){ const creds={}; document.querySelectorAll(`input[data-ch="${ch}"]`).forEach(i=>{ if(i.value.trim()) creds[i.dataset.k]=i.value.trim(); });
      try{ await api(`/brands/${G.brandId}/channels/connect`,"POST",{channel:ch,credentials:creds}); toast("Saved — testing…"); await G.test(ch); }catch(e){ toast(e.message,true); } },
    async test(ch){ try{ const r=await api(`/brands/${G.brandId}/channels/${ch}/test`,"POST"); toast(r.ok?`✓ ${ch}: ${r.account||"verified"}`:`✗ ${ch}: ${r.detail}`, !r.ok); if(G.onHubChange) G.onHubChange(); }catch(e){ toast(e.message,true); } },
    async disconnect(ch){ if(!confirm(`Disconnect ${ch}?`)) return; try{ await api(`/brands/${G.brandId}/channels/${ch}`,"DELETE"); toast("Disconnected"); if(G.onHubChange) G.onHubChange(); }catch(e){ toast(e.message,true); } },
  };
  window.GrowthUI=G;
})();

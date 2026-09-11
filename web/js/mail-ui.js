/* Built-in mailer UI — shared by the brand app and the operator console.
   Depends on global api(), esc(), toast(). Mount with MailUI.mount(el, brandId, {canEdit}). */
(function(){
  const E=s=>(typeof esc==="function"?esc(s):String(s==null?"":s));
  const CSS=`.mu{font-size:13.5px}.mu .tabs2{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.mu .tabs2 button{font:inherit;font-weight:700;font-size:12.5px;padding:7px 12px;border-radius:9px;border:1px solid var(--line,#e6e3dc);background:var(--surface,var(--panel,#fff));cursor:pointer;color:inherit}.mu .tabs2 button.on{background:var(--accent,var(--yel,#6d5dfc));color:#fff;border-color:transparent}
  .mu .box{border:1px solid var(--line,#e6e3dc);border-radius:12px;padding:14px;background:var(--surface,var(--panel,#fff));margin-bottom:12px}.mu .box h3{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted,var(--mut,#6b665d))}
  .mu .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:10px}.mu .tile{background:var(--surface-2,var(--panel2,#f4f2ec));border-radius:10px;padding:8px 10px}.mu .tile b{display:block;font-size:18px}.mu .tile span{font-size:11px;color:var(--muted,var(--mut,#6b665d))}
  .mu input,.mu select,.mu textarea{font:inherit;padding:7px 9px;border:1px solid var(--line,#e6e3dc);border-radius:9px;background:var(--surface,var(--panel,#fff));color:inherit;width:100%;box-sizing:border-box;margin:0}.mu .fl{display:flex;flex-direction:column;gap:3px;margin-bottom:8px}.mu .fl label{font-size:11px;font-weight:700;color:var(--muted,var(--mut,#6b665d))}
  .mu .row2{display:grid;grid-template-columns:1fr 1fr;gap:8px}.mu .btn2{font:inherit;font-weight:700;font-size:12.5px;padding:7px 12px;border-radius:9px;border:1px solid var(--line,#e6e3dc);background:var(--surface,var(--panel,#fff));cursor:pointer;color:inherit}.mu .btn2.p{background:var(--accent,var(--yel,#6d5dfc));color:#fff;border-color:transparent}.mu .btn2.ok{background:#15803d;color:#fff;border-color:transparent}
  .mu table{width:100%;border-collapse:collapse;font-size:12.5px}.mu th,.mu td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line,#e6e3dc)}.mu th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted,var(--mut,#6b665d))}
  .mu .pill{font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;background:var(--surface-2,var(--panel2,#f4f2ec))}.mu .pill.ok{background:#e9f8ef;color:#15803d}.mu .pill.warn{background:#fff4e0;color:#b45309}.mu .pill.bad{background:#fde8e8;color:#c62828}
  .mu iframe{width:100%;height:520px;border:1px solid var(--line,#e6e3dc);border-radius:10px;background:#fff}.mu .notice{border-left:4px solid #15803d;background:#eef9f1;padding:9px 12px;border-radius:8px;font-size:12.5px;margin:8px 0}.mu .notice.warn{border-color:#b45309;background:#fff8ec}
  @media(max-width:640px){.mu .row2{grid-template-columns:1fr}}`;
  function css(){ if(!document.getElementById("mailUiCss")){ const s=document.createElement("style"); s.id="mailUiCss"; s.textContent=CSS; document.head.appendChild(s);} }
  const S={el:null,bid:null,canEdit:false,tab:"campaigns",cur:null};
  async function mount(el,bid,o){ css(); S.el=el; S.bid=bid; S.canEdit=!!(o&&o.canEdit); S.tab=(o&&o.tab)||S.tab; await render(); }
  async function render(){
    const st=await api(`/brands/${S.bid}/mail/status`).catch(()=>({}));
    let h=`<div class="mu"><div class="tiles"><div class="tile"><b>${st.contacts??0}</b><span>subscribed contacts</span></div><div class="tile"><b>${st.unsubscribed??0}</b><span>unsubscribed</span></div><div class="tile"><b>${st.smtp_connected?"●":"○"}</b><span>${st.smtp_connected?`sending as ${E(st.from)}`:"SMTP not connected"}</span></div><div class="tile"><b>${st.sent_today??0}${st.daily_cap?` / ${st.daily_cap}`:""}</b><span>sent today / cap</span></div></div>
      ${st.smtp_connected?"":`<div class="notice warn">Connect the client's mailbox under <b>Connections → Built-in mailer (your SMTP)</b> to send. You can import contacts and draft campaigns now.</div>`}
      <div class="tabs2">${[["campaigns","Campaigns"],["sequences","Sequences"],["contacts","Contacts"]].map(([k,l])=>`<button class="${S.tab===k?"on":""}" onclick="MailUI.go('${k}')">${l}</button>`).join("")}</div><div id="muBody"></div></div>`;
    S.el.innerHTML=h;
    if(S.tab==="contacts") await contacts(); else await campaigns(S.tab==="sequences"?"sequence":"broadcast");
  }
  async function contacts(){
    const c=await api(`/brands/${S.bid}/mail/contacts`);
    const b=document.getElementById("muBody");
    b.innerHTML=`${S.canEdit?`<div class="box"><h3>Import contacts</h3><div class="fl"><label>CSV (email, name, tags…) or one email per line</label><textarea id="muCsv" rows="5" placeholder="email,name,tags\npriya@example.com,Priya Sharma,enquiry-2026\n…"></textarea></div>
      <div class="row2"><div class="fl"><label>Add tag(s) to all, comma-separated</label><input id="muTags" placeholder="site-visit, kokapet"></div><div class="fl" style="justify-content:flex-end"><button class="btn2 p" onclick="MailUI.importCsv()">Import</button></div></div>
      <div style="font-size:11.5px;color:var(--muted,var(--mut,#6b665d))">Only people who agreed to hear from the brand. Unsubscribes are honoured forever, across every campaign.</div></div>`:""}
      <div class="box"><h3>${c.count} contacts · tags: ${(c.tags||[]).map(t=>`<span class="pill">${E(t)}</span>`).join(" ")||"none"}</h3>
      <div style="overflow-x:auto"><table><tr><th>Email</th><th>Name</th><th>Tags</th><th>Status</th>${S.canEdit?"<th></th>":""}</tr>${(c.contacts||[]).map(x=>`<tr><td>${E(x.email)}</td><td>${E(x.name||"")}</td><td>${(x.tags||[]).map(t=>`<span class="pill">${E(t)}</span>`).join(" ")}</td><td><span class="pill ${x.status==="subscribed"?"ok":x.status==="bounced"?"bad":"warn"}">${E(x.status)}</span></td>${S.canEdit?`<td>${x.status==="subscribed"?`<button class="btn2" onclick="MailUI.unsub('${E(x.id)}')">Unsubscribe</button>`:""}</td>`:""}</tr>`).join("")||`<tr><td colspan="5">No contacts yet.</td></tr>`}</table></div></div>`;
  }
  async function importCsv(){
    let csv=(document.getElementById("muCsv").value||"").trim(); const tags=(document.getElementById("muTags").value||"").split(",").map(x=>x.trim()).filter(Boolean);
    if(!csv) return toast("Paste some contacts first",true);
    if(!/,/.test(csv.split("\n")[0])) csv="email\n"+csv;              // bare email list → CSV
    else if(!/email/i.test(csv.split("\n")[0])) csv="email,name,tags\n"+csv;
    try{ const r=await api(`/brands/${S.bid}/mail/contacts`,"POST",{csv,tags}); toast(`Imported: ${r.added} new, ${r.updated} updated, ${r.skipped} skipped`); contacts(); }catch(e){ toast(e.message,true); }
  }
  async function unsub(id){ if(!confirm("Unsubscribe this contact? This cannot be undone by us.")) return; try{ await api(`/brands/${S.bid}/mail/contacts/${id}/unsubscribe`,"POST"); contacts(); }catch(e){ toast(e.message,true); } }
  async function campaigns(kind){
    const all=await api(`/brands/${S.bid}/mail/campaigns`); const rows=all.filter(c=>c.kind===kind);
    const b=document.getElementById("muBody");
    b.innerHTML=`${S.canEdit?`<div class="box"><h3>${kind==="sequence"?"New sequence":"New broadcast"}</h3><div class="row2"><div class="fl"><label>Goal</label><input id="muGoal" placeholder="${kind==="sequence"?"re-engage 2025 enquiries who never visited":"invite past enquiries to the Kokapet site-visit weekend"}"></div><div class="fl"><label>Send to tag(s), comma-separated (blank = everyone)</label><input id="muSeg" placeholder="enquiry-2026"></div></div>
      <div class="row2"><div class="fl"><label>Tone (optional)</label><input id="muTone" placeholder="warm, direct"></div><div class="fl" style="justify-content:flex-end"><button class="btn2 p" onclick="MailUI.draft('${kind}')">Draft with AI</button></div></div></div>`:""}
      <div id="muCur"></div>
      <div class="box"><h3>${kind==="sequence"?"Sequences":"Broadcasts"}</h3><div style="overflow-x:auto"><table><tr><th>Subject</th><th>Status</th><th>Sent</th><th>Opens</th><th>Clicks</th><th>Unsub</th><th></th></tr>${rows.map(c=>`<tr><td><b>${E(c.subject||"(untitled)")}</b>${c.kind==="sequence"?` <span class="pill">${c.steps} steps</span>`:""}</td><td><span class="pill ${c.status==="sent"?"ok":c.status==="sending"||c.status==="scheduled"?"warn":""}">${E(c.status)}</span></td><td>${c.stats.sent??0}</td><td>${c.stats.opens??0}${c.stats.open_rate?` (${c.stats.open_rate}%)`:""}</td><td>${c.stats.clicks??0}</td><td>${c.stats.unsubscribes??0}</td><td><button class="btn2" onclick="MailUI.open('${E(c.id)}')">Open</button></td></tr>`).join("")||`<tr><td colspan="7">Nothing yet.</td></tr>`}</table></div></div>`;
    if(S.cur&&rows.some(c=>c.id===S.cur)) open(S.cur);
  }
  async function draft(kind){
    const goal=document.getElementById("muGoal").value.trim(); if(goal.length<3) return toast("Describe the goal",true);
    const tags=(document.getElementById("muSeg").value||"").split(",").map(x=>x.trim()).filter(Boolean); const tone=document.getElementById("muTone").value;
    toast("Drafting…");
    try{ const r=await api(`/brands/${S.bid}/mail/draft`,"POST",{goal,kind,segment:{tags},tone}); S.cur=r.campaign.id; await campaigns(kind); }catch(e){ toast(e.message,true); }
  }
  async function open(id){
    S.cur=id; const c=await api(`/brands/${S.bid}/mail/campaigns/${id}`); const p=c.payload; const st=p.stats||{}; const editable=S.canEdit&&!["sending","sent"].includes(c.status);
    const el=document.getElementById("muCur"); if(!el) return;
    const steps=c.kind==="sequence"?(p.steps||[]):null;
    el.innerHTML=`<div class="box"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap"><h3 style="margin:0">${E(c.kind)} · ${E(c.subject||"")}</h3><span class="pill ${c.status==="sent"?"ok":""}">${E(c.status)}</span><span class="pill">${c.audience_size} recipient(s)</span>${(p.segment&&p.segment.tags&&p.segment.tags.length)?`<span class="pill">tags: ${E(p.segment.tags.join(", "))}</span>`:""}</div>
      <div class="tiles" style="margin-top:8px"><div class="tile"><b>${st.sent??0}</b><span>sent</span></div><div class="tile"><b>${st.open_rate??0}%</b><span>open rate</span></div><div class="tile"><b>${st.click_rate??0}%</b><span>click rate</span></div><div class="tile"><b>${st.unsubscribes??0}</b><span>unsubscribed</span></div><div class="tile"><b>${st.bounces??0}</b><span>bounced</span></div></div>
      ${steps?steps.map((s,i)=>`<div class="fl"><label>Step ${s.n} · day ${s.delay_days}</label>${editable?`<input data-ms="subject" data-i="${i}" value="${E(s.subject)}"><textarea data-ms="text" data-i="${i}" rows="5">${E(s.text)}</textarea><input type="number" min="0" data-ms="delay_days" data-i="${i}" value="${s.delay_days}" style="width:120px" title="delay in days">`:`<b>${E(s.subject)}</b><pre style="white-space:pre-wrap;font:inherit;margin:4px 0">${E(s.text)}</pre>`}</div>`).join("")
      :`<div class="row2"><div class="fl"><label>Subject</label><input id="muSubj" value="${E(p.subject)}" ${editable?"":"disabled"}></div><div class="fl"><label>A/B subject</label><input id="muSubjB" value="${E(p.subject_alt||"")}" ${editable?"":"disabled"}></div></div><div class="fl"><label>Preview text</label><input id="muPrev" value="${E(p.preview||"")}" ${editable?"":"disabled"}></div><div class="fl"><label>Body (HTML)</label><textarea id="muHtml" rows="7" ${editable?"":"disabled"}>${E(p.html||"")}</textarea></div>`}
      <div class="fl"><label>Preview as the recipient sees it</label><iframe title="preview" src="${apiBase()}/brands/${S.bid}/mail/campaigns/${id}/preview?t=${Date.now()}"></iframe></div>
      <div class="notice">Nothing goes out until you approve. Approval sends now (within today's cap: warm-up 20 → 40 → 80 → 120 → 160/day) or at a scheduled time; every email carries an unsubscribe link.</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">${editable?`<button class="btn2" onclick="MailUI.save('${id}')">Save edits</button>`:""}
        ${S.canEdit?`<input id="muTestTo" placeholder="you@company.com" style="width:220px"><button class="btn2" onclick="MailUI.test('${id}')">Send test</button>`:""}
        ${S.canEdit&&!["sending","sent"].includes(c.status)?`<input id="muWhen" type="datetime-local" style="width:210px"><button class="btn2 ok" onclick="MailUI.approve('${id}')">Approve & send</button>`:""}
        ${S.canEdit&&["sending","scheduled"].includes(c.status)?`<button class="btn2" onclick="MailUI.pause('${id}')">Pause</button>`:""}</div></div>`;
    el.scrollIntoView({behavior:"smooth",block:"start"});
  }
  function apiBase(){ return (typeof API!=="undefined"?API:"/api"); }
  async function save(id){
    const el=document.getElementById("muCur"); const body={};
    if(document.getElementById("muSubj")){ body.subject=document.getElementById("muSubj").value; body.preview=document.getElementById("muPrev").value; body.html=document.getElementById("muHtml").value; }
    else { const steps=[]; el.querySelectorAll("[data-ms]").forEach(x=>{ const i=+x.dataset.i; steps[i]=steps[i]||{}; steps[i][x.dataset.ms]=x.dataset.ms==="delay_days"?+x.value:x.value; }); body.steps=steps.filter(Boolean); }
    try{ await api(`/brands/${S.bid}/mail/campaigns/${id}`,"PUT",body); toast("Saved — needs a fresh approval"); open(id); }catch(e){ toast(e.message,true); }
  }
  async function test(id){ const to=(document.getElementById("muTestTo").value||"").trim(); if(!to) return toast("Enter your email",true); try{ await api(`/brands/${S.bid}/mail/campaigns/${id}/test`,"POST",{to}); toast(`Test sent to ${to}`); }catch(e){ toast(e.message,true); } }
  async function approve(id){
    const when=document.getElementById("muWhen").value; const schedule_at=when?Math.floor(new Date(when).getTime()/1000):null;
    if(!confirm(schedule_at?`Schedule this campaign for ${new Date(when).toLocaleString()}?`:"Send this campaign now to all matching contacts (within today's cap)?")) return;
    try{ const r=await api(`/brands/${S.bid}/mail/campaigns/${id}/approve`,"POST",{approve:true,schedule_at}); toast(r.status==="scheduled"?"Scheduled":`Sending${r.result?` — ${r.result.sent} sent, ${r.result.remaining_today} left today`:""}`); render(); }catch(e){ toast(e.message,true); }
  }
  async function pause(id){ try{ await api(`/brands/${S.bid}/mail/campaigns/${id}/pause`,"POST"); toast("Paused"); render(); }catch(e){ toast(e.message,true); } }
  window.MailUI={mount,go:t=>{S.tab=t;render();},importCsv,unsub,draft,open,save,test,approve,pause};
})();

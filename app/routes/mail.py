"""Built-in mailer routes: contacts, campaigns, sequences, approval-gated
sending, stats — plus the public tracking endpoints (open pixel, click
redirect, unsubscribe) that carry no PII and are HMAC-signed."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import Field

from ._shared import *  # noqa: F401,F403
from ..services import agency_pool, mailer

router = APIRouter()


class ContactsIn(BaseModel):
    contacts: list[dict] = []
    csv: str = ""
    tags: list[str] = []


class MailDraftIn(BaseModel):
    goal: str = Field(min_length=3, max_length=400)
    kind: str = "broadcast"          # broadcast | sequence
    segment: dict = {}               # {tags:[...], exclude:[...]}
    tone: str = ""


class MailEditIn(BaseModel):
    subject: str | None = None
    preview: str | None = None
    html: str | None = None
    text: str | None = None
    steps: list[dict] | None = None
    segment: dict | None = None


class MailActionIn(BaseModel):
    approve: bool = False
    schedule_at: float | None = None   # unix ts, optional


class TestSendIn(BaseModel):
    to: str


def _base_url(request: Request) -> str:
    pub = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    return pub or str(request.base_url).rstrip("/")


def _no_client(user):
    if user["role"] == "client":
        raise HTTPException(403, "Client logins can view mail but not change it")


# ---------------- contacts ----------------

@router.get("/api/brands/{bid}/mail/contacts")
def contacts(bid: str, tag: str = "", status: str = "", user=Depends(current_user)):
    _brand_or_404(bid, user)
    rows = mailer.list_contacts(bid, tag or None, status or None)
    tags = sorted({t for r in rows for t in r["tags"]})
    return {"count": len(rows), "tags": tags, "contacts": [{"id": r["id"], "email": r["email"], "status": r["status"], "tags": r["tags"],
                                                              "name": (r.get("payload") or {}).get("name"), "created_at": r.get("created_at")} for r in rows[:500]]}


@router.post("/api/brands/{bid}/mail/contacts")
def add_contacts(bid: str, body: ContactsIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _no_client(user)
    if body.csv.strip():
        return mailer.import_csv(bid, body.csv, body.tags)
    if not body.contacts:
        raise HTTPException(400, "Provide contacts or csv")
    rows = [{**c, "tags": list(c.get("tags") or []) + body.tags} for c in body.contacts[:5000]]
    return mailer.add_contacts(bid, rows, source="api")


@router.post("/api/brands/{bid}/mail/contacts/{contact_id}/unsubscribe")
def unsubscribe_contact(bid: str, contact_id: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    if not mailer.unsubscribe(bid, contact_id, reason="operator"):
        raise HTTPException(404, "Contact not found")
    return {"ok": True}


# ---------------- campaigns ----------------

@router.get("/api/brands/{bid}/mail/campaigns")
def campaigns(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    rows = db.list_docs("mail_campaigns", bid)
    return [{"id": r["id"], "kind": r["kind"], "status": r["status"], "subject": r.get("subject"),
             "steps": len((r["payload"] or {}).get("steps") or []), "segment": (r["payload"] or {}).get("segment"),
             "stats": (r["payload"] or {}).get("stats") or {}, "created_at": r.get("created_at")} for r in rows]


@router.get("/api/brands/{bid}/mail/campaigns/{cid}")
def campaign(bid: str, cid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    c = _doc_or_404("mail_campaigns", cid, bid)
    c["payload"]["stats"] = mailer.stats(bid, cid)
    c["audience_size"] = len(mailer.segment(bid, c["payload"].get("segment")))
    return c


@router.post("/api/brands/{bid}/mail/draft")
def draft(bid: str, body: MailDraftIn, user=Depends(current_user)):
    """AI drafts a broadcast (subject A/B, preview, HTML) or a 3–4 step sequence."""
    b = _brand_or_404(bid, user)
    _no_client(user)
    _gen_guard(bid)
    from ..services import brand_config
    cfg = brand_config.prompt_block(b)
    ctx = ai_engine._brand_context(b, with_memory=False)
    if body.kind == "sequence":
        sys = ("You write short, human cold/nurture email SEQUENCES that get replies. Plain text, no HTML, 60–120 words per step, "
               "one ask per email, {{first_name}} merge field. Never invent facts, prices or guarantees. Return STRICT JSON.")
        usr = (f"Brand: {ctx}\nClient config: {cfg}\nGoal: {body.goal}\nTone: {body.tone or 'warm, direct'}\n"
               "Return {\"steps\":[{\"delay_days\":0,\"subject\":\"...\",\"text\":\"...\"},{\"delay_days\":2,...},{\"delay_days\":4,...}]} (3–4 steps).")
    else:
        sys = ("You write marketing broadcast emails that people actually open. Return STRICT JSON. Never invent facts, prices or guarantees. "
               "HTML: simple semantic tags only (h1,h2,p,ul,li,a,strong) — no inline styles, no images, no scripts.")
        usr = (f"Brand: {ctx}\nClient config: {cfg}\nGoal: {body.goal}\nTone: {body.tone or 'brand voice'}\n"
               "Return {\"subject\":\"<=60 chars\",\"subject_alt\":\"A/B variant\",\"preview\":\"<=90 chars\",\"html\":\"...\",\"text\":\"plain-text version\"}. "
               "Use {{first_name}} once. One clear call-to-action link.")
    try:
        content = ai_engine._json_chat(sys + " " + ai_engine.ANTI_INJECTION, usr, max_tokens=2500)
    except Exception as e:
        raise HTTPException(502, f"Drafting failed: {e}")
    c = mailer.create_campaign(bid, body.kind, content, body.segment, body.goal)
    c["audience_size"] = len(mailer.segment(bid, body.segment))
    return {"campaign": c, "note": "Draft only — nothing is sent. Review, test-send to yourself, then approve."}


@router.put("/api/brands/{bid}/mail/campaigns/{cid}")
def edit(bid: str, cid: str, body: MailEditIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _no_client(user)
    c = _doc_or_404("mail_campaigns", cid, bid)
    if c.get("status") in ("sending", "sent"):
        raise HTTPException(409, "This campaign has started sending — duplicate it instead")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if "steps" in patch:
        patch["steps"] = [{"n": i + 1, "delay_days": max(0, int(s.get("delay_days") or 0)), "subject": str(s.get("subject") or "")[:200],
                           "text": str(s.get("text") or "")} for i, s in enumerate(patch["steps"][:8]) if isinstance(s, dict)]
    p = db.merge_payload("mail_campaigns", cid, patch)
    subj = p.get("subject") if c["kind"] == "broadcast" else ((p.get("steps") or [{}])[0].get("subject"))
    db.update_doc("mail_campaigns", cid, status="draft", subject=subj)   # any edit needs a fresh approval
    return db.get_doc("mail_campaigns", cid)


@router.get("/api/brands/{bid}/mail/campaigns/{cid}/preview", response_class=HTMLResponse)
def preview(bid: str, cid: str, step: int = 0, request: Request = None, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    c = _doc_or_404("mail_campaigns", cid, bid)
    fake = {"id": "test", "email": user.get("email", "you@example.com"), "payload": {"first_name": "Priya", "name": "Priya Sharma"}}
    try:
        subject, html_body, _ = mailer.render_html(b, c, fake, min(step, max(0, len(c["payload"].get("steps") or [1]) - 1)), _base_url(request))
    except IndexError:
        raise HTTPException(400, "No such step")
    return HTMLResponse(html_body, headers={"X-Subject": subject[:200]})


@router.post("/api/brands/{bid}/mail/campaigns/{cid}/test")
def test_send(bid: str, cid: str, body: TestSendIn, request: Request, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _no_client(user)
    _doc_or_404("mail_campaigns", cid, bid)
    if not mailer.EMAIL_RE.match(body.to or ""):
        raise HTTPException(400, "Enter a valid email address")
    try:
        return mailer.send_test(bid, cid, body.to, _base_url(request))
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"SMTP error: {str(e)[:200]}")


@router.post("/api/brands/{bid}/mail/campaigns/{cid}/approve")
def approve(bid: str, cid: str, body: MailActionIn, user=Depends(current_user)):
    """Approval is the gate: approved campaigns are sent by the pool (now) or the cron (scheduled)."""
    _brand_or_404(bid, user)
    _no_client(user)
    c = _doc_or_404("mail_campaigns", cid, bid)
    if not body.approve:
        raise HTTPException(403, "Sending real mail requires approve=true")
    if c.get("status") in ("sending", "sent"):
        raise HTTPException(409, f"Campaign is already {c['status']}")
    if not mailer.configured(mailer.smtp_creds(bid)):
        raise HTTPException(400, "SMTP is not connected for this client (Settings → Connections → SMTP)")
    if not mailer.segment(bid, c["payload"].get("segment")):
        raise HTTPException(400, "No subscribed contacts match this segment")
    patch = {"approval": {"by": user.get("uid"), "role": user.get("role"), "at": time.time()}}
    if body.schedule_at and body.schedule_at > time.time():
        patch["schedule_at"] = body.schedule_at
        db.merge_payload("mail_campaigns", cid, patch)
        db.update_doc("mail_campaigns", cid, status="scheduled")
        return {"ok": True, "status": "scheduled", "schedule_at": body.schedule_at}
    db.merge_payload("mail_campaigns", cid, patch)
    db.update_doc("mail_campaigns", cid, status="approved")
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    j = agency_pool.POOL.submit(bid, "mail_send", lambda log: mailer.send_batch(bid, cid, base, log=log))
    return {"ok": True, "status": "sending", "job_id": j["id"], "job_state": j["state"], "result": j.get("result")}


@router.post("/api/brands/{bid}/mail/campaigns/{cid}/pause")
def pause(bid: str, cid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _no_client(user)
    c = _doc_or_404("mail_campaigns", cid, bid)
    db.update_doc("mail_campaigns", cid, status="paused")
    return {"ok": True, "status": "paused", "was": c.get("status")}


@router.get("/api/brands/{bid}/mail/campaigns/{cid}/stats")
def campaign_stats(bid: str, cid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _doc_or_404("mail_campaigns", cid, bid)
    return mailer.stats(bid, cid)


@router.get("/api/brands/{bid}/mail/status")
def mail_status(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    creds = mailer.smtp_creds(bid)
    ok = mailer.configured(creds)
    return {"smtp_connected": ok, "from": creds.get("from_email") if ok else None,
            "daily_cap": mailer.daily_cap(bid, creds) if ok else None, "sent_today": mailer.sent_today(bid),
            "contacts": len(mailer.list_contacts(bid, status="subscribed")),
            "unsubscribed": len(mailer.list_contacts(bid, status="unsubscribed"))}


# ---------------- public tracking (no auth, signed tokens) ----------------

@router.get("/m/o/{token}.gif")
def track_open(token: str):
    mailer.record_event(token, "open")
    return Response(content=mailer.PIXEL, media_type="image/gif", headers={"Cache-Control": "no-store"})


@router.get("/m/c/{token}")
def track_click(token: str):
    t = mailer.verify(token)
    if not t or t["kind"] != "c":
        raise HTTPException(404, "Link expired")
    url = t["extra"]
    from ..core import guard
    ok, _ = guard.url_is_safe(url)
    if not ok:
        raise HTTPException(400, "Unsafe link")
    mailer.record_event(token, "click", {"url": url[:500]})
    return RedirectResponse(url, status_code=302)


@router.get("/m/u/{token}", response_class=HTMLResponse)
def track_unsub(token: str):
    t = mailer.record_event(token, "unsubscribe")
    if not t:
        return HTMLResponse("<p style='font-family:sans-serif'>This link is invalid.</p>", status_code=404)
    return HTMLResponse("<div style='font-family:sans-serif;max-width:480px;margin:60px auto;text-align:center'><h2>You're unsubscribed</h2><p>You won't receive further emails from this sender.</p></div>")

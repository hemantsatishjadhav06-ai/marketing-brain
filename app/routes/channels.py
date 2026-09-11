"""Growth tooling — Meta Ads, Google Ads, email marketing, SEO, WhatsApp.

One router over five channel services. Design rules, enforced here:
  - Credentials live per-brand in connector_settings; nothing live happens without them.
  - Planning / drafting / auditing / reading insights are free and need no approval.
  - Any money-moving ad action (launch-active, budget change) goes through
    guard.check_ad_action (human approval + budget ceiling; autopilot may never do it).
  - Email send / sequence-start and WhatsApp outbound are explicit human actions.
  - Everything defaults to a draft/plan the operator reviews first.
"""
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ._shared import *  # noqa: F401,F403
from ..core import guard
from ..services import meta_ads, google_ads, email_marketing, seo_tools, whatsapp

router = APIRouter()

CHANNELS = {
    "meta_ads": {"label": "Meta Ads", "guide": meta_ads.SETUP_GUIDE, "kind": "ads"},
    "google_ads": {"label": "Google Ads", "guide": google_ads.SETUP_GUIDE, "kind": "ads"},
    "mailchimp": {"label": "Mailchimp", "guide": email_marketing.SETUP_GUIDES["mailchimp"], "kind": "email"},
    "smartlead": {"label": "Smartlead", "guide": email_marketing.SETUP_GUIDES["smartlead"], "kind": "email"},
    "whatsapp": {"label": "WhatsApp", "guide": [
        "Create a WhatsApp Business app at developers.facebook.com (WhatsApp product).",
        "Get a permanent access_token and your phone_number_id.",
        'Save credentials as {"access_token":"...","phone_number_id":"..."}.',
        "Point the webhook at /api/whatsapp/webhook and set WHATSAPP_VERIFY_TOKEN.",
    ], "kind": "messaging"},
}


# ---------- schemas ----------
class ChannelConnectIn(BaseModel):
    channel: str
    credentials: dict


class AdPlanIn(BaseModel):
    objective: str = "OUTCOME_LEADS"
    daily_budget: float = Field(0, ge=0)
    currency: str = "INR"
    prompt: str = ""


class AdActionIn(BaseModel):
    campaign_id: str
    approve: bool = False


class EmailDraftIn(BaseModel):
    goal: str
    kind: str = "broadcast"
    list_id: str = ""


class EmailSendIn(BaseModel):
    email_campaign_id: str
    approve: bool = False
    schedule_iso: str = ""
    test_emails: list[str] = []


class SeoAuditIn(BaseModel):
    url: str


class SeoKeywordsIn(BaseModel):
    seeds: list[str] = []


class WhatsAppSendIn(BaseModel):
    to: str
    text: str = ""
    template: str = ""
    lang: str = "en_US"


def _creds(bid, channel):
    return db.get_connectors(bid).get(channel)


def _plan_json(system, user):
    return ai_engine._json_chat(system + " " + ai_engine.ANTI_INJECTION, user, max_tokens=2500)


# ---------- connect / status ----------
@router.get("/api/brands/{bid}/channels")
def channels_status(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    saved = db.get_connectors(bid)
    out = {}
    for ch, meta in CHANNELS.items():
        out[ch] = {"label": meta["label"], "kind": meta["kind"],
                   "connected": ch in saved, "setup_guide": meta["guide"]}
    out["_limits"] = {"max_daily_ad_budget": guard.max_daily_budget(),
                      "ad_spend_enabled": guard.ad_spend_enabled()}
    return out


@router.post("/api/brands/{bid}/channels/connect")
def connect_channel(bid: str, body: ChannelConnectIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _admin_or_owner(user, bid)
    if body.channel not in CHANNELS:
        raise HTTPException(400, f"Unknown channel. Supported: {list(CHANNELS)}")
    db.set_connector(bid, body.channel, body.credentials)
    return {"ok": True, "connected": body.channel}


def _admin_or_owner(user, bid):
    if user["role"] == "admin":
        return
    if user["role"] == "manager" and _can_see(user, bid):
        return  # an assigned account-manager runs this client's channels
    if user.get("brand_id") == bid and user["role"] in ("owner", "admin"):
        return
    raise HTTPException(403, "Only the master account or this company's owner can change connections")


# ---------- ADS (meta / google) ----------
def _ads_mod(network):
    if network == "meta":
        return meta_ads
    if network == "google":
        return google_ads
    raise HTTPException(404, "network must be 'meta' or 'google'")


@router.post("/api/brands/{bid}/ads/{network}/plan")
def ad_plan(bid: str, network: str, body: AdPlanIn, user=Depends(current_user)):
    """AI drafts a campaign. No spend; saved as a draft the operator reviews."""
    b = _brand_or_404(bid, user)
    _ads_mod(network)
    _gen_guard(bid)
    cap = guard.max_daily_budget()
    budget = min(body.daily_budget or cap / 2, cap)
    sys = (f"You are a senior performance marketer planning a {network.upper()} ads campaign. "
           "Return STRICT JSON only. Never invent prices, RERA numbers or guarantees — "
           "use only facts in the brand context.")
    usr = (f"Brand: {ai_engine._brand_context(b, with_memory=False)}\n"
           f"Objective: {body.objective}. Daily budget: {budget} {body.currency}. "
           f"Extra direction: {body.prompt[:500]}\n\n"
           "Return JSON: {\"name\":\"campaign name\",\"objective\":\"" + body.objective + "\","
           "\"audience\":\"one-line target audience\",\"targeting_summary\":\"geo/age/interests\","
           "\"optimization_goal\":\"LEAD_GENERATION|LINK_CLICKS|...\","
           "\"creative\":{\"primary_text\":\"...\",\"headline\":\"<=40 chars\",\"description\":\"...\",\"cta\":\"...\",\"link\":\"\"},"
           + ("\"keywords\":[{\"text\":\"...\",\"match\":\"PHRASE\"}],\"negative_keywords\":[\"...\"],\"rsa\":{\"headlines\":[\"<=30 chars\"],\"descriptions\":[\"<=90 chars\"]}" if network == "google" else "\"placements\":\"feed, reels, stories\"")
           + "}")
    try:
        plan = _plan_json(sys, usr)
    except Exception as e:
        raise HTTPException(502, f"Ad planning failed: {e}")
    plan["daily_budget"] = budget
    plan["currency"] = body.currency
    cid = db.insert_doc("campaigns", bid, plan, network=network, objective=body.objective,
                        status="draft", daily_budget=budget, currency=body.currency)
    return {"campaign_id": cid, "status": "draft", "plan": plan,
            "note": "Draft only — nothing is live and no money has moved. Launch creates it PAUSED; activating it requires your approval."}


@router.get("/api/brands/{bid}/ads/{network}/campaigns")
def ad_campaigns(bid: str, network: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return [c for c in db.list_docs("campaigns", bid) if c.get("network") == network]


@router.post("/api/brands/{bid}/ads/{network}/launch")
def ad_launch(bid: str, network: str, body: AdActionIn, user=Depends(current_user)):
    """Create the campaign PAUSED on the platform. Creating PAUSED spends nothing,
    but we still require the plan to be approved and the budget under the ceiling."""
    _brand_or_404(bid, user)
    mod = _ads_mod(network)
    c = _doc_or_404("campaigns", body.campaign_id, bid)
    ok, msg = guard.check_ad_action(c.get("daily_budget", 0), approved=body.approve, by_autopilot=False)
    if not ok:
        raise HTTPException(403, msg)
    creds = _creds(bid, f"{network}_ads")
    if not mod.configured(creds):
        raise HTTPException(400, f"{network.title()} Ads is not connected for this brand.")
    try:
        if network == "meta":
            res = mod.launch(creds, c["payload"], status="PAUSED")
        else:
            res = mod.launch_budget_and_campaign(creds, c["payload"])
    except Exception as e:
        db.update_doc("campaigns", body.campaign_id, status="failed")
        raise HTTPException(502, f"Launch failed: {e}")
    db.update_doc("campaigns", body.campaign_id, status="approved",
                  external_id=res.get("campaign") or res.get("campaign_id"),
                  payload={**c["payload"], "platform_ids": res})
    db.insert_doc("spend_log", bid, {"campaign_id": body.campaign_id, "platform_ids": res},
                  action="launch_paused", amount=0, actor=user.get("uid", ""))
    return {"ok": True, "status": "created_paused", "platform_ids": res}


@router.post("/api/brands/{bid}/ads/{network}/activate")
def ad_activate(bid: str, network: str, body: AdActionIn, user=Depends(current_user)):
    """Flip the created campaign ACTIVE — this is when money starts moving, so it is
    the hardest-gated action: explicit approval + budget under the ceiling."""
    _brand_or_404(bid, user)
    mod = _ads_mod(network)
    c = _doc_or_404("campaigns", body.campaign_id, bid)
    ok, msg = guard.check_ad_action(c.get("daily_budget", 0), approved=body.approve, by_autopilot=False)
    if not ok:
        raise HTTPException(403, msg)
    creds = _creds(bid, f"{network}_ads")
    if not mod.configured(creds):
        raise HTTPException(400, f"{network.title()} Ads is not connected.")
    ids = (c["payload"].get("platform_ids") or {})
    try:
        if network == "meta":
            mod.set_active(creds, ids, active=True)
        else:
            mod.set_enabled(creds, ids.get("campaign"), enabled=True)
    except Exception as e:
        raise HTTPException(502, f"Activation failed: {e}")
    db.update_doc("campaigns", body.campaign_id, status="live")
    db.insert_doc("spend_log", bid, {"campaign_id": body.campaign_id},
                  action="activate", amount=c.get("daily_budget", 0), actor=user.get("uid", ""))
    return {"ok": True, "status": "live"}


@router.post("/api/brands/{bid}/ads/{network}/pause")
def ad_pause(bid: str, network: str, body: AdActionIn, user=Depends(current_user)):
    """Pause spends nothing, so it needs no spend approval (autopilot may do this)."""
    _brand_or_404(bid, user)
    mod = _ads_mod(network)
    c = _doc_or_404("campaigns", body.campaign_id, bid)
    creds = _creds(bid, f"{network}_ads")
    ids = (c["payload"].get("platform_ids") or {})
    if mod.configured(creds) and ids:
        try:
            if network == "meta":
                mod.set_active(creds, ids, active=False)
            else:
                mod.set_enabled(creds, ids.get("campaign"), enabled=False)
        except Exception as e:
            raise HTTPException(502, f"Pause failed: {e}")
    db.update_doc("campaigns", body.campaign_id, status="paused")
    db.insert_doc("spend_log", bid, {"campaign_id": body.campaign_id}, action="pause", amount=0, actor=user.get("uid", ""))
    return {"ok": True, "status": "paused"}


@router.get("/api/brands/{bid}/ads/{network}/insights/{campaign_id}")
def ad_insights(bid: str, network: str, campaign_id: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    mod = _ads_mod(network)
    c = _doc_or_404("campaigns", campaign_id, bid)
    creds = _creds(bid, f"{network}_ads")
    if not mod.configured(creds):
        raise HTTPException(400, f"{network.title()} Ads is not connected.")
    ext = c.get("external_id") or (c["payload"].get("platform_ids") or {}).get("campaign_id")
    try:
        if network == "meta":
            return mod.insights(creds, ext)
        return mod.report(creds, f"SELECT metrics.cost_micros, metrics.clicks, metrics.conversions, metrics.ctr FROM campaign WHERE campaign.id = {ext}")
    except Exception as e:
        raise HTTPException(502, f"Insights failed: {e}")


# ---------- EMAIL ----------
@router.get("/api/brands/{bid}/email/{provider}/audiences")
def email_audiences(bid: str, provider: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    creds = _creds(bid, provider)
    if not email_marketing.configured(provider, creds):
        raise HTTPException(400, f"{provider} is not connected.")
    if provider != "mailchimp":
        raise HTTPException(400, "Audiences are a Mailchimp concept; Smartlead uses lead lists per campaign.")
    try:
        return email_marketing.mc_audiences(creds)
    except Exception as e:
        raise HTTPException(502, f"Could not load audiences: {e}")


@router.post("/api/brands/{bid}/email/{provider}/draft")
def email_draft(bid: str, provider: str, body: EmailDraftIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if provider not in email_marketing.PROVIDERS:
        raise HTTPException(404, "provider must be mailchimp or smartlead")
    _gen_guard(bid)
    if body.kind == "sequence" or provider == "smartlead":
        sys = ("You write high-converting cold-email SEQUENCES. Return STRICT JSON. "
               "Never invent facts, prices or guarantees.")
        usr = (f"Brand: {ai_engine._brand_context(b, with_memory=False)}\nGoal: {body.goal[:400]}\n"
               "Return JSON {\"steps\":[{\"seq_delay_in_days\":0,\"subject\":\"...\",\"email_body\":\"plain text with {{first_name}}\"}]} (3–4 steps).")
    else:
        sys = ("You write marketing broadcast emails. Return STRICT JSON. Never invent facts.")
        usr = (f"Brand: {ai_engine._brand_context(b, with_memory=False)}\nGoal: {body.goal[:400]}\n"
               "Return JSON {\"subject\":\"...\",\"preview\":\"...\",\"html\":\"<h1>..</h1><p>..</p>\"}.")
    try:
        content = _plan_json(sys, usr)
    except Exception as e:
        raise HTTPException(502, f"Email drafting failed: {e}")
    kind = "sequence" if (body.kind == "sequence" or provider == "smartlead") else "broadcast"
    eid = db.insert_doc("email_campaigns", bid, {**content, "goal": body.goal[:400], "list_id": body.list_id},
                        provider=provider, kind=kind, status="draft")
    return {"email_campaign_id": eid, "status": "draft", "content": content,
            "note": "Draft only — no mail has been sent. Sending requires your approval."}


@router.post("/api/brands/{bid}/email/{provider}/send")
def email_send(bid: str, provider: str, body: EmailSendIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    ec = _doc_or_404("email_campaigns", body.email_campaign_id, bid)
    creds = _creds(bid, provider)
    if not email_marketing.configured(provider, creds):
        raise HTTPException(400, f"{provider} is not connected.")
    p = ec["payload"]
    # test sends are safe and need no approval
    if body.test_emails and provider == "mailchimp":
        pass
    elif not body.approve:
        raise HTTPException(403, "Sending real email requires approval (approve=true).")
    try:
        if provider == "mailchimp":
            if not p.get("campaign_id"):
                from_name = (b.get("name") or "Team")
                reply_to = (b.get("profile") or {}).get("contact_email") or "noreply@example.com"
                created = email_marketing.mc_create_campaign(creds, p.get("list_id") or body.email_campaign_id[:0] or _require_list(p),
                                                             p.get("subject", "Update"), from_name, reply_to, p.get("html", ""))
                p["campaign_id"] = created["campaign_id"]
                db.update_doc("email_campaigns", body.email_campaign_id, payload=p, external_id=p["campaign_id"])
            if body.test_emails:
                email_marketing.mc_send_test(creds, p["campaign_id"], body.test_emails)
                return {"ok": True, "status": "test_sent"}
            email_marketing.mc_send(creds, p["campaign_id"], body.schedule_iso or None)
        else:  # smartlead sequence
            if not p.get("sl_campaign_id"):
                camp = email_marketing.sl_create_campaign(creds, p.get("goal", "Sequence")[:60])
                scid = camp.get("id") or camp.get("campaign_id") or (camp.get("data") or {}).get("id")
                email_marketing.sl_set_sequence(creds, scid, p.get("steps", []))
                p["sl_campaign_id"] = scid
                db.update_doc("email_campaigns", body.email_campaign_id, payload=p, external_id=str(scid))
            email_marketing.sl_start(creds, p["sl_campaign_id"])
    except Exception as e:
        db.update_doc("email_campaigns", body.email_campaign_id, status="failed")
        raise HTTPException(502, f"Send failed: {e}")
    db.update_doc("email_campaigns", body.email_campaign_id, status="sent")
    return {"ok": True, "status": "sent"}


def _require_list(p):
    if not p.get("list_id"):
        raise HTTPException(400, "Pick a Mailchimp audience (list_id) before sending.")
    return p["list_id"]


# ---------- SEO ----------
@router.post("/api/brands/{bid}/seo/audit")
def seo_audit(bid: str, body: SeoAuditIn, user=Depends(current_user)):
    """Live technical + on-page audit of a page. Read-only; no site changes."""
    _brand_or_404(bid, user)
    try:
        rep = seo_tools.audit(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Audit failed: {e}")
    db.insert_doc("seo_audits", bid, rep, url=rep.get("url", body.url)[:500], score=rep.get("score", 0))
    return rep


@router.get("/api/brands/{bid}/seo/audits")
def seo_audits(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("seo_audits", bid)


@router.post("/api/brands/{bid}/seo/keywords")
def seo_keywords(bid: str, body: SeoKeywordsIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    creds = _creds(bid, "google_ads")
    if google_ads.configured(creds) and body.seeds:
        try:
            return {"source": "google_ads", "ideas": google_ads.keyword_ideas(creds, body.seeds)}
        except Exception:
            pass  # fall through to LLM ideas
    _gen_guard(bid)
    sys = "You are an SEO keyword strategist. Return STRICT JSON. Ground to the brand; no invented facts."
    usr = (f"Brand: {ai_engine._brand_context(b, with_memory=False)}\nSeed topics: {', '.join(body.seeds) or 'derive from the brand'}\n"
           "Return JSON {\"keywords\":[{\"keyword\":\"...\",\"intent\":\"informational|commercial|transactional\",\"difficulty\":\"low|med|high\",\"why\":\"...\"}]} (12 items).")
    try:
        return {"source": "ai", **_plan_json(sys, usr)}
    except Exception as e:
        raise HTTPException(502, f"Keyword research failed: {e}")


# ---------- WHATSAPP ----------
@router.post("/api/brands/{bid}/whatsapp/send")
def whatsapp_send(bid: str, body: WhatsAppSendIn, user=Depends(current_user)):
    """Outbound WhatsApp — an explicit human action (templates open a conversation;
    session text only works inside the 24h window). Autopilot never sends blasts."""
    _brand_or_404(bid, user)
    creds = _creds(bid, "whatsapp")
    if not whatsapp.configured(creds):
        raise HTTPException(400, "WhatsApp is not connected.")
    try:
        if body.template:
            res = whatsapp.send_template(creds, body.to, body.template, body.lang)
        elif body.text:
            res = whatsapp.send_text(creds, body.to, body.text)
        else:
            raise HTTPException(400, "Provide text or template.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"WhatsApp send failed: {e}")
    return {"ok": True, "result": res}


@router.get("/api/whatsapp/webhook")
def whatsapp_verify(request: Request):
    """Meta webhook verification handshake."""
    from fastapi.responses import PlainTextResponse
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == whatsapp.verify_token() and whatsapp.verify_token():
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(403, "verification failed")


@router.post("/api/whatsapp/webhook")
async def whatsapp_inbound(request: Request):
    """Inbound messages → stored in the brand's inbox + keyword-trigger handling.
    Unauthenticated (Meta calls it); the phone_number_id maps to the brand."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}
    pnid = _pnid_from_payload(body)
    bid = _brand_by_whatsapp_pnid(pnid) if pnid else None
    for msg in whatsapp.parse_webhook(body):
        if not bid:
            continue
        try:
            _record_whatsapp_inbound(bid, msg)
        except Exception as e:
            guard.log.warning("whatsapp inbound handling failed: %s", e)
    return {"ok": True}


def _pnid_from_payload(body):
    try:
        return body["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
    except Exception:
        return None


def _brand_by_whatsapp_pnid(pnid):
    for b in db.list_brands():
        creds = db.get_connectors(b["id"]).get("whatsapp")
        if creds and str(creds.get("phone_number_id")) == str(pnid):
            return b["id"]
    return None


def _record_whatsapp_inbound(bid, msg):
    """Store the inbound message in the brand's inbox and, when it is a known keyword
    trigger (PRICE/PDF/LOCATION/...), tag it so the Brain drafts the right reply. The
    operator sends drafted replies from the inbox — nothing auto-sends here."""
    from ..services import inbox
    text = msg.get("text", "")
    trig = whatsapp.detect_trigger(text)
    label = f"[trigger:{trig[0]}] {text}" if trig else text
    inbox.record_inbound(bid, "whatsapp", msg.get("from", ""), label, msg.get("name", ""))

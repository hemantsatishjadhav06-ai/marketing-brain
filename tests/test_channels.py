"""Growth tooling — Meta/Google Ads, email, SEO, WhatsApp.

Spend safety is the point: every money-moving ad action must be blocked without a
human approval, above the budget ceiling, or from autopilot. No test makes a real
network call or spends real money — platform calls are monkeypatched; the live SEO
audit runs against an in-test HTML fixture.
"""
from __future__ import annotations

import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "channels.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ.setdefault("MAX_DAILY_AD_BUDGET", "5000")
os.environ.pop("DIRECT_ACCESS", None)
os.environ.pop("AD_SPEND_DISABLED", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.core import auth, database as db, guard  # noqa: E402
from app.main import app  # noqa: E402
from app.services import workspace as ws, meta_ads, seo_tools, whatsapp, email_marketing  # noqa: E402
from app.routes import channels  # noqa: E402

client = TestClient(app)


def _brand(name="Co"):
    return db.create_brand(name + uuid.uuid4().hex[:6], ws.slugify(name + uuid.uuid4().hex[:6]), "", {}, "")


def _user(role, bid=""):
    uid = db.create_user(f"{role}-{uuid.uuid4().hex[:8]}@t.local", auth.hash_pw("pw12345678"), role=role, brand_id=bid)
    return {"Authorization": "Bearer " + auth.make_token(uid, role, bid)}


@pytest.fixture(autouse=True)
def _mock_ai(monkeypatch):
    # planning must never hit a real model
    monkeypatch.setattr(channels.ai_engine, "_json_chat",
                        lambda *a, **k: {"name": "Test campaign", "objective": "OUTCOME_LEADS",
                                         "creative": {"primary_text": "hi", "headline": "h"},
                                         "subject": "S", "html": "<p>x</p>", "steps": [{"subject": "a", "email_body": "b"}],
                                         "keywords": [{"keyword": "k", "intent": "commercial"}]})


# ---------------- guard unit ----------------

def test_ADS_check_ad_action_blocks_unapproved():
    ok, _ = guard.check_ad_action(1000, approved=False, by_autopilot=False)
    assert not ok


def test_ADS_check_ad_action_blocks_autopilot():
    ok, msg = guard.check_ad_action(1000, approved=True, by_autopilot=True)
    assert not ok and "utopilot" in msg


def test_ADS_check_ad_action_blocks_over_cap():
    ok, msg = guard.check_ad_action(999999, approved=True, by_autopilot=False)
    assert not ok and "ceiling" in msg


def test_ADS_check_ad_action_allows_approved_under_cap():
    ok, _ = guard.check_ad_action(1000, approved=True, by_autopilot=False)
    assert ok


# ---------------- ads routes ----------------

def _draft_campaign(bid, h, network="meta", budget=1000):
    r = client.post(f"/api/brands/{bid}/ads/{network}/plan",
                    json={"objective": "OUTCOME_LEADS", "daily_budget": budget}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "draft"
    return r.json()["campaign_id"]


def test_ADS_plan_creates_draft_no_spend():
    bid = _brand(); h = _user("owner", bid)
    cid = _draft_campaign(bid, h)
    c = db.get_doc("campaigns", cid)
    assert c["status"] == "draft" and c["daily_budget"] == 1000
    assert db.list_docs("spend_log", bid) == []


def test_ADS_launch_without_approval_blocked():
    bid = _brand(); h = _user("owner", bid); cid = _draft_campaign(bid, h)
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "act_1"})
    r = client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": False}, headers=h)
    assert r.status_code == 403 and "approv" in r.text.lower()


def test_ADS_launch_over_cap_blocked():
    bid = _brand(); h = _user("owner", bid); cid = _draft_campaign(bid, h, budget=5000)
    # force the stored budget above the ceiling
    db.update_doc("campaigns", cid, daily_budget=999999)
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "act_1"})
    r = client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=h)
    assert r.status_code == 403 and "ceiling" in r.text.lower()


def test_ADS_launch_not_connected_blocked():
    bid = _brand(); h = _user("owner", bid); cid = _draft_campaign(bid, h)
    r = client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=h)
    assert r.status_code == 400 and "not connected" in r.text.lower()


def test_ADS_approved_launch_creates_paused_then_activate_goes_live(monkeypatch):
    bid = _brand(); h = _user("owner", bid); cid = _draft_campaign(bid, h)
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "act_1", "page_id": "p1"})
    monkeypatch.setattr(meta_ads, "launch", lambda creds, plan, status="PAUSED": {"campaign_id": "C1", "adset_id": "A1"})
    r = client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "created_paused"
    assert db.get_doc("campaigns", cid)["status"] == "approved"
    activated = {}
    monkeypatch.setattr(meta_ads, "set_active", lambda creds, ids, active=True: activated.update({"ids": ids, "active": active}) or {})
    r2 = client.post(f"/api/brands/{bid}/ads/meta/activate", json={"campaign_id": cid, "approve": True}, headers=h)
    assert r2.status_code == 200 and r2.json()["status"] == "live"
    assert db.get_doc("campaigns", cid)["status"] == "live"
    assert activated["active"] is True
    log = db.list_docs("spend_log", bid)
    assert any(x["action"] == "activate" for x in log)


def test_ADS_activate_without_approval_blocked(monkeypatch):
    bid = _brand(); h = _user("owner", bid); cid = _draft_campaign(bid, h)
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "act_1"})
    monkeypatch.setattr(meta_ads, "launch", lambda *a, **k: {"campaign_id": "C1"})
    client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=h)
    r = client.post(f"/api/brands/{bid}/ads/meta/activate", json={"campaign_id": cid, "approve": False}, headers=h)
    assert r.status_code == 403


def test_ADS_kill_switch_blocks_everything(monkeypatch):
    monkeypatch.setenv("AD_SPEND_DISABLED", "true")
    bid = _brand(); h = _user("owner", bid); cid = _draft_campaign(bid, h)
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "act_1"})
    r = client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=h)
    assert r.status_code == 403 and "disabled" in r.text.lower()


# ---------------- tenant isolation ----------------

def test_CHANNELS_cross_brand_blocked():
    a = _brand(); b = _brand(); ha = _user("owner", a)
    cid = _draft_campaign(a, ha)
    hb = _user("owner", b)
    assert client.get(f"/api/brands/{a}/channels", headers=hb).status_code == 403
    assert client.post(f"/api/brands/{a}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=hb).status_code == 403
    assert client.post(f"/api/brands/{a}/channels/connect", json={"channel": "whatsapp", "credentials": {}}, headers=hb).status_code == 403


def test_CHANNELS_client_role_cannot_connect():
    bid = _brand(); hc = _user("client", bid)
    r = client.post(f"/api/brands/{bid}/channels/connect", json={"channel": "meta_ads", "credentials": {"x": "y"}}, headers=hc)
    assert r.status_code == 403


# ---------------- email ----------------

def test_EMAIL_draft_then_send_requires_approval():
    bid = _brand(); h = _user("owner", bid)
    r = client.post(f"/api/brands/{bid}/email/mailchimp/draft", json={"goal": "spring launch", "kind": "broadcast", "list_id": "L1"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "draft"
    eid = r.json()["email_campaign_id"]
    # connected, but not approved
    db.set_connector(bid, "mailchimp", {"api_key": "k-us1"})
    r2 = client.post(f"/api/brands/{bid}/email/mailchimp/send", json={"email_campaign_id": eid, "approve": False}, headers=h)
    assert r2.status_code == 403


def test_EMAIL_send_not_connected_blocked():
    bid = _brand(); h = _user("owner", bid)
    eid = client.post(f"/api/brands/{bid}/email/smartlead/draft", json={"goal": "cold", "kind": "sequence"}, headers=h).json()["email_campaign_id"]
    r = client.post(f"/api/brands/{bid}/email/smartlead/send", json={"email_campaign_id": eid, "approve": True}, headers=h)
    assert r.status_code == 400 and "not connected" in r.text.lower()


def test_EMAIL_approved_send_calls_provider(monkeypatch):
    bid = _brand(); h = _user("owner", bid)
    eid = client.post(f"/api/brands/{bid}/email/mailchimp/draft", json={"goal": "g", "list_id": "L1"}, headers=h).json()["email_campaign_id"]
    db.set_connector(bid, "mailchimp", {"api_key": "k-us1"})
    monkeypatch.setattr(email_marketing, "mc_create_campaign", lambda *a, **k: {"campaign_id": "MC1"})
    sent = {}
    monkeypatch.setattr(email_marketing, "mc_send", lambda creds, cid, sched=None: sent.update({"cid": cid}) or {"ok": True})
    r = client.post(f"/api/brands/{bid}/email/mailchimp/send", json={"email_campaign_id": eid, "approve": True}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "sent" and sent["cid"] == "MC1"


# ---------------- SEO (live against a fixture) ----------------

GOOD_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Neopolis — Ultra-Luxury Apartments in Kokapet, West Hyderabad</title>
<meta name=description content='Neopolis offers 3.5 and 4 BHK ultra-luxury hanging apartments in Kokapet, priced from Rs 2.7 Cr onwards with a 7.5-acre central park.'>
<link rel=canonical href='https://neopolis.example/'>
<script type='application/ld+json'>{"@type":"Product"}</script>
<meta property='og:title' content='Neopolis'><meta property='og:image' content='https://x/y.jpg'>
</head><body><h1>Ultra-luxury hanging apartments</h1><h2>Configurations</h2>
<p>%s</p><a href='/pricing'>Pricing</a><a href='/gallery'>Gallery</a><a href='/contact'>Contact</a>
<img src='a.jpg' alt='tower'></body></html>""" % ("word " * 350)

BAD_HTML = "<html><head></head><body><h1>a</h1><h1>b</h1><p>thin</p></body></html>"


def test_SEO_audit_scores_good_page_high(monkeypatch):
    monkeypatch.setattr(seo_tools, "_fetch", lambda url: (200, GOOD_HTML, {}, "https://neopolis.example/"))
    bid = _brand(); h = _user("owner", bid)
    r = client.post(f"/api/brands/{bid}/seo/audit", json={"url": "https://neopolis.example/"}, headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["score"] >= 85, j["score"]
    assert j["counts"]["fail"] <= 1
    assert db.list_docs("seo_audits", bid)[0]["score"] == j["score"]


def test_SEO_audit_flags_bad_page(monkeypatch):
    monkeypatch.setattr(seo_tools, "_fetch", lambda url: (200, BAD_HTML, {}, "http://x.example/"))
    bid = _brand(); h = _user("owner", bid)
    j = client.post(f"/api/brands/{bid}/seo/audit", json={"url": "http://x.example/"}, headers=h).json()
    assert j["score"] < 60
    names = {c["name"] for c in j["fix_first"]}
    assert "Meta description" in names or "Title tag" in names


def test_SEO_audit_rejects_unsafe_url():
    bid = _brand(); h = _user("owner", bid)
    r = client.post(f"/api/brands/{bid}/seo/audit", json={"url": "http://169.254.169.254/"}, headers=h)
    assert r.status_code == 400


def test_SEO_keywords_ai_fallback():
    bid = _brand(); h = _user("owner", bid)
    r = client.post(f"/api/brands/{bid}/seo/keywords", json={"seeds": ["luxury apartments hyderabad"]}, headers=h)
    assert r.status_code == 200 and r.json()["source"] == "ai" and r.json()["keywords"]


# ---------------- WhatsApp ----------------

def test_WA_send_not_connected_blocked():
    bid = _brand(); h = _user("owner", bid)
    r = client.post(f"/api/brands/{bid}/whatsapp/send", json={"to": "9199", "text": "hi"}, headers=h)
    assert r.status_code == 400


def test_WA_detect_trigger():
    assert whatsapp.detect_trigger("PRICE")[0] == "PRICE"
    assert whatsapp.detect_trigger("what is the PRICE please")[0] == "PRICE"
    assert whatsapp.detect_trigger("hello there") is None


def test_WA_webhook_verify_handshake(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "secret123")
    r = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "secret123", "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    bad = client.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_WA_webhook_inbound_routes_to_brand_and_records():
    bid = _brand(); _user("owner", bid)
    db.set_connector(bid, "whatsapp", {"access_token": "t", "phone_number_id": "PN123"})
    payload = {"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": "PN123"},
        "contacts": [{"wa_id": "9199", "profile": {"name": "Asha"}}],
        "messages": [{"from": "9199", "id": "m1", "type": "text", "text": {"body": "PRICE"}}]}}]}]}
    r = client.post("/api/whatsapp/webhook", json=payload)
    assert r.status_code == 200
    from app.services import inbox
    convos = inbox.list_conversations(bid)
    assert convos, "inbound WhatsApp message was not recorded"


def test_WA_webhook_unknown_number_is_ignored_safely():
    r = client.post("/api/whatsapp/webhook", json={"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": "UNKNOWN"},
        "messages": [{"from": "1", "type": "text", "text": {"body": "hi"}}]}}]}]})
    assert r.status_code == 200


# ---------------- status ----------------

def test_CHANNELS_status_shape():
    bid = _brand(); h = _user("owner", bid)
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "act_1"})
    j = client.get(f"/api/brands/{bid}/channels", headers=h).json()
    assert j["meta_ads"]["connected"] is True and j["whatsapp"]["connected"] is False
    assert j["_limits"]["max_daily_ad_budget"] == 5000
    assert set(["meta_ads", "google_ads", "mailchimp", "smartlead", "whatsapp"]).issubset(j.keys())

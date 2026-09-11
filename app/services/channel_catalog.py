"""Every distribution channel the product can connect to — one honest catalogue.

Each entry says what the channel can do TODAY (`status`: live | partial |
manual), which credentials it needs and how to get them, and how to verify
the connection (`probe`). "manual" channels still work end-to-end through
simulated publishing + the manual checklist; they just need a human to press
"post" on the platform.

Probes are read-only API calls that prove a token works and name the
connected account. They never publish, send or spend.
"""
from __future__ import annotations

import httpx

GRAPH = "https://graph.facebook.com/v21.0"

CATALOG = {
    # ---------------- social publishing ----------------
    "instagram": {
        "label": "Instagram", "group": "social", "status": "live",
        "can": ["publish images, carousels, reels (public image URL)", "read profile"],
        "cannot": ["stories via API", "DM automation (needs Messenger platform review)"],
        "fields": [{"key": "access_token", "label": "Long-lived Page access token", "secret": True},
                   {"key": "ig_user_id", "label": "IG Business Account ID"}],
        "steps": ["Switch the Instagram account to Business/Creator and link it to a Facebook Page.",
                  "developers.facebook.com → your app → add Instagram Graph API.",
                  "Generate a long-lived Page token with instagram_basic, instagram_content_publish, pages_read_engagement.",
                  "GET /me/accounts → page → instagram_business_account → copy the id."],
        "docs": "https://developers.facebook.com/docs/instagram-platform/content-publishing",
    },
    "facebook": {
        "label": "Facebook Page", "group": "social", "status": "live",
        "can": ["publish photo/link posts", "read page"],
        "cannot": ["groups posting"],
        "fields": [{"key": "access_token", "label": "Long-lived Page access token", "secret": True},
                   {"key": "page_id", "label": "Page ID"}],
        "steps": ["developers.facebook.com → app with pages_manage_posts + pages_read_engagement.",
                  "Generate a long-lived Page access token for the page you post from.",
                  "Copy the Page ID from the page's About section."],
        "docs": "https://developers.facebook.com/docs/pages-api/posts",
    },
    "linkedin": {
        "label": "LinkedIn", "group": "social", "status": "live",
        "can": ["publish text posts as a member", "read profile"],
        "cannot": ["company-page posting without Marketing Developer Platform approval", "images (roadmap)"],
        "fields": [{"key": "access_token", "label": "Member access token (w_member_social)", "secret": True},
                   {"key": "author_urn", "label": "Author URN (urn:li:person:…)"}],
        "steps": ["developer.linkedin.com → app → request 'Share on LinkedIn' + 'Sign In with LinkedIn using OpenID Connect'.",
                  "Complete OAuth to get a member token with w_member_social + openid profile.",
                  "GET /v2/userinfo → sub → author_urn = urn:li:person:<sub>."],
        "docs": "https://learn.microsoft.com/linkedin/consumer/integrations/self-serve/share-on-linkedin",
    },
    "twitter": {
        "label": "X (Twitter)", "group": "social", "status": "manual",
        "can": ["simulated publish + manual checklist"],
        "cannot": ["live posting (needs paid X API tier; connector on roadmap)"],
        "fields": [{"key": "api_key", "label": "API key", "secret": True}, {"key": "api_secret", "label": "API secret", "secret": True},
                   {"key": "access_token", "label": "Access token", "secret": True}, {"key": "access_secret", "label": "Access secret", "secret": True}],
        "steps": ["developer.x.com → Basic tier or above.", "Enable OAuth 1.0a user context, Read/Write."],
        "docs": "https://developer.x.com/en/docs/x-api",
    },
    "youtube": {
        "label": "YouTube", "group": "social", "status": "manual",
        "can": ["scripts, titles, tags, descriptions, thumbnail text", "simulated publish + checklist"],
        "cannot": ["video upload via API (roadmap: YouTube Data API v3 OAuth)"],
        "fields": [{"key": "channel_id", "label": "Channel ID"}],
        "steps": ["YouTube Studio → Settings → Channel → Advanced → copy Channel ID."],
        "docs": "https://developers.google.com/youtube/v3",
    },
    "google_business": {
        "label": "Google Business Profile", "group": "social", "status": "manual",
        "can": ["post copy + offer posts as a checklist"],
        "cannot": ["API posting (needs Business Profile API approval)"],
        "fields": [{"key": "location_id", "label": "Location ID"}],
        "steps": ["business.google.com → your location → copy the ID from the URL."],
        "docs": "https://developers.google.com/my-business",
    },
    # ---------------- paid media ----------------
    "meta_ads": {
        "label": "Meta Ads", "group": "ads", "status": "live",
        "can": ["plan campaigns (audiences, budgets, creatives)", "create PAUSED campaigns", "activate/pause with approval", "read insights"],
        "cannot": ["raise budgets without a human", "bypass MAX_DAILY_AD_BUDGET"],
        "fields": [{"key": "access_token", "label": "System-user token (ads_management, ads_read)", "secret": True},
                   {"key": "ad_account_id", "label": "Ad account ID (act_…)"}, {"key": "page_id", "label": "Page ID to advertise from"}],
        "steps": ["business.facebook.com → Business settings → System users → generate token with ads_management + ads_read.",
                  "Ads Manager → account dropdown → copy act_ID.", "Assign the ad account and page to the system user."],
        "docs": "https://developers.facebook.com/docs/marketing-apis",
    },
    "google_ads": {
        "label": "Google Ads", "group": "ads", "status": "partial",
        "can": ["keyword ideas", "GAQL reports", "create PAUSED search campaigns with a basic-access developer token"],
        "cannot": ["launch without an approved developer token"],
        "fields": [{"key": "developer_token", "label": "Developer token", "secret": True}, {"key": "client_id", "label": "OAuth client ID"},
                   {"key": "client_secret", "label": "OAuth client secret", "secret": True}, {"key": "refresh_token", "label": "OAuth refresh token", "secret": True},
                   {"key": "customer_id", "label": "Customer ID (123-456-7890)"}, {"key": "login_customer_id", "label": "Manager (MCC) ID, optional"}],
        "steps": ["ads.google.com → Tools → API Center → apply for a developer token.",
                  "console.cloud.google.com → OAuth client (Desktop) → get a refresh token with the adwords scope.",
                  "Copy the customer ID from the top-right of Google Ads."],
        "docs": "https://developers.google.com/google-ads/api/docs/start",
    },
    # ---------------- email ----------------
    "mailchimp": {
        "label": "Mailchimp", "group": "email", "status": "live",
        "can": ["list audiences", "draft campaigns", "send / schedule with approval"],
        "cannot": [],
        "fields": [{"key": "api_key", "label": "API key (ends in -usXX)", "secret": True}],
        "steps": ["Mailchimp → Account → Extras → API keys → create.", "Create at least one Audience."],
        "docs": "https://mailchimp.com/developer/marketing/",
    },
    "smartlead": {
        "label": "Smartlead", "group": "email", "status": "live",
        "can": ["create sequences", "add leads", "start with approval"],
        "cannot": [],
        "fields": [{"key": "api_key", "label": "API key", "secret": True}],
        "steps": ["Smartlead → Settings → API → copy key.", "Connect and warm at least one mailbox."],
        "docs": "https://api.smartlead.ai/reference",
    },
    # ---------------- messaging ----------------
    "whatsapp": {
        "label": "WhatsApp Business", "group": "messaging", "status": "live",
        "can": ["send session + template messages", "receive inbound via webhook", "keyword triggers → inbox"],
        "cannot": ["auto-reply without an operator (by design)"],
        "fields": [{"key": "access_token", "label": "Permanent access token", "secret": True},
                   {"key": "phone_number_id", "label": "Phone number ID"}, {"key": "waba_id", "label": "WABA ID, optional"}],
        "steps": ["developers.facebook.com → app → WhatsApp product.", "Add a phone number, copy phone_number_id.",
                  "System-user token with whatsapp_business_messaging.",
                  "Webhook: /api/whatsapp/webhook with WHATSAPP_VERIFY_TOKEN."],
        "docs": "https://developers.facebook.com/docs/whatsapp/cloud-api",
    },
    # ---------------- data ----------------
    "airtable": {
        "label": "Airtable", "group": "data", "status": "live",
        "can": ["sync approvals, runs, content to a base"],
        "cannot": [],
        "fields": [{"key": "api_key", "label": "Personal access token", "secret": True}, {"key": "base_id", "label": "Base ID"}],
        "steps": ["airtable.com/create/tokens → token with data.records:read/write.", "Copy the base ID (app…)."],
        "docs": "https://airtable.com/developers/web/api/introduction",
    },
    "webhook": {
        "label": "Outbound webhook (Zapier / Make / n8n)", "group": "data", "status": "live",
        "can": ["receive approved creatives + publish events as JSON"],
        "cannot": [],
        "fields": [{"key": "url", "label": "HTTPS endpoint"}, {"key": "secret", "label": "Signing secret, optional", "secret": True}],
        "steps": ["Create a catch hook in Zapier/Make/n8n and paste the URL."],
        "docs": "",
    },
}
GROUPS = [("social", "Social publishing"), ("ads", "Paid media"), ("email", "Email"), ("messaging", "Messaging"), ("data", "Data & automation")]


def public(brand_connected: dict | None = None) -> list:
    conn = brand_connected or {}
    out = []
    for cid, c in CATALOG.items():
        creds = conn.get(cid) or {}
        out.append({"id": cid, **{k: v for k, v in c.items()},
                    "connected": cid in conn,
                    "last_test": creds.get("_status") if isinstance(creds, dict) else None})
    return out


def required_fields(cid: str) -> list:
    return [f["key"] for f in CATALOG.get(cid, {}).get("fields", []) if not f.get("label", "").lower().endswith("optional")]


def _get(url, **kw):
    with httpx.Client(timeout=20) as cli:
        r = cli.get(url, **kw)
        return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text[:200]})


def probe(cid: str, creds: dict) -> dict:
    """Verify credentials with a read-only call. Returns {ok, account, detail}."""
    c = CATALOG.get(cid)
    if not c:
        return {"ok": False, "detail": "unknown channel"}
    missing = [k for k in required_fields(cid) if not (creds or {}).get(k)]
    if missing:
        return {"ok": False, "detail": f"missing: {', '.join(missing)}"}
    try:
        if cid == "instagram":
            st, j = _get(f"{GRAPH}/{creds['ig_user_id']}", params={"fields": "username,name", "access_token": creds["access_token"]})
            return {"ok": st == 200, "account": j.get("username") or j.get("name"), "detail": j.get("error", {}).get("message", "") if st != 200 else "token valid"}
        if cid == "facebook":
            st, j = _get(f"{GRAPH}/{creds['page_id']}", params={"fields": "name,fan_count", "access_token": creds["access_token"]})
            return {"ok": st == 200, "account": j.get("name"), "detail": j.get("error", {}).get("message", "") if st != 200 else "token valid"}
        if cid == "meta_ads":
            acct = creds["ad_account_id"] if creds["ad_account_id"].startswith("act_") else "act_" + creds["ad_account_id"]
            st, j = _get(f"{GRAPH}/{acct}", params={"fields": "name,currency,account_status,amount_spent", "access_token": creds["access_token"]})
            return {"ok": st == 200, "account": f"{j.get('name')} ({j.get('currency')})" if st == 200 else None,
                    "detail": j.get("error", {}).get("message", "") if st != 200 else f"account status {j.get('account_status')}"}
        if cid == "whatsapp":
            st, j = _get(f"{GRAPH}/{creds['phone_number_id']}", params={"fields": "display_phone_number,verified_name,quality_rating", "access_token": creds["access_token"]})
            return {"ok": st == 200, "account": f"{j.get('verified_name')} {j.get('display_phone_number')}" if st == 200 else None,
                    "detail": j.get("error", {}).get("message", "") if st != 200 else f"quality {j.get('quality_rating')}"}
        if cid == "linkedin":
            st, j = _get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": "Bearer " + creds["access_token"]})
            return {"ok": st == 200, "account": j.get("name"), "detail": "token valid" if st == 200 else f"HTTP {st}"}
        if cid == "mailchimp":
            key = creds["api_key"]
            dc = key.split("-")[-1] if "-" in key else "us1"
            st, j = _get(f"https://{dc}.api.mailchimp.com/3.0/ping", auth=("anystring", key))
            return {"ok": st == 200, "account": dc, "detail": j.get("health_status") or j.get("detail") or f"HTTP {st}"}
        if cid == "smartlead":
            st, j = _get("https://server.smartlead.ai/api/v1/campaigns", params={"api_key": creds["api_key"]})
            n = len(j) if isinstance(j, list) else None
            return {"ok": st == 200, "account": f"{n} campaigns" if n is not None else None, "detail": "key valid" if st == 200 else f"HTTP {st}"}
        if cid == "google_ads":
            from . import google_ads
            tok = google_ads._access_token(creds)
            return {"ok": bool(tok), "account": creds.get("customer_id"), "detail": "OAuth refresh OK (developer token not exercised)"}
        if cid == "airtable":
            st, j = _get(f"https://api.airtable.com/v0/meta/bases/{creds['base_id']}/tables", headers={"Authorization": "Bearer " + creds["api_key"]})
            return {"ok": st == 200, "account": f"{len(j.get('tables', []))} tables" if st == 200 else None, "detail": "token valid" if st == 200 else f"HTTP {st}"}
        if cid == "webhook":
            from ..core import guard
            ok, why = guard.url_is_safe(creds["url"])
            return {"ok": ok and creds["url"].startswith("https://"), "account": creds["url"][:60], "detail": why or "URL accepted (no call made)"}
        return {"ok": True, "account": None, "detail": f"{c['label']} is a manual channel — credentials stored for the checklist"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:200]}

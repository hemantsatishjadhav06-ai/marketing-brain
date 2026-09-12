"""Email marketing — Mailchimp (broadcast) + Smartlead (cold sequences).

Everything up to the send is safe (audiences, drafting content, adding leads,
building sequence steps). The ONLY calls that actually send mail —
Mailchimp campaign send/schedule and Smartlead campaign START — are isolated so a
route can gate them behind human approval. Live only when the provider's API key
is saved.
"""
from __future__ import annotations

import httpx

PROVIDERS = ("mailchimp", "smartlead")

SETUP_GUIDES = {
    "mailchimp": [
        "Create a Mailchimp account and an Audience (list).",
        "Generate an API key (Account → Extras → API keys). The key ends in '-usXX' — that suffix is your data center.",
        'Save credentials as {"api_key":"...-us21"}. The data center is read from the key.',
    ],
    "smartlead": [
        "Create a Smartlead account and connect at least one sending mailbox (warmed).",
        "Get your API key (Settings → API).",
        'Save credentials as {"api_key":"..."}.',
    ],
}


def configured(provider, creds) -> bool:
    return bool(creds and creds.get("api_key"))


# ---------------- Mailchimp ----------------

def _mc_base(creds):
    key = creds["api_key"]
    dc = key.split("-")[-1] if "-" in key else "us1"
    return f"https://{dc}.api.mailchimp.com/3.0", ("anystring", key)


def mc_audiences(creds) -> dict:
    base, auth = _mc_base(creds)
    with httpx.Client(timeout=30) as cli:
        r = cli.get(f"{base}/lists", auth=auth, params={"count": 100, "fields": "lists.id,lists.name,lists.stats.member_count"})
        r.raise_for_status()
        return r.json()


def mc_create_campaign(creds, list_id, subject, from_name, reply_to, html) -> dict:
    """Create a regular campaign and set its content. Does NOT send."""
    base, auth = _mc_base(creds)
    with httpx.Client(timeout=40) as cli:
        r = cli.post(f"{base}/campaigns", auth=auth, json={
            "type": "regular", "recipients": {"list_id": list_id},
            "settings": {"subject_line": subject, "from_name": from_name,
                         "reply_to": reply_to, "title": subject[:60]}})
        r.raise_for_status()
        cid = r.json()["id"]
        c = cli.put(f"{base}/campaigns/{cid}/content", auth=auth, json={"html": html})
        c.raise_for_status()
        return {"campaign_id": cid}


def mc_send_test(creds, campaign_id, emails) -> dict:
    base, auth = _mc_base(creds)
    with httpx.Client(timeout=30) as cli:
        r = cli.post(f"{base}/campaigns/{campaign_id}/actions/test", auth=auth,
                     json={"test_emails": emails, "send_type": "html"})
        r.raise_for_status()
        return {"ok": True}


def mc_send(creds, campaign_id, schedule_iso=None) -> dict:
    """📧 SENDS (or schedules) the campaign to the whole audience. Gate behind approval."""
    base, auth = _mc_base(creds)
    with httpx.Client(timeout=40) as cli:
        if schedule_iso:
            r = cli.post(f"{base}/campaigns/{campaign_id}/actions/schedule", auth=auth,
                         json={"schedule_time": schedule_iso})
        else:
            r = cli.post(f"{base}/campaigns/{campaign_id}/actions/send", auth=auth)
        r.raise_for_status()
        return {"ok": True, "scheduled": bool(schedule_iso)}


# ---------------- Smartlead ----------------

SL = "https://server.smartlead.ai/api/v1"


def _sl(creds):
    return {"api_key": creds["api_key"]}


def sl_create_campaign(creds, name) -> dict:
    with httpx.Client(timeout=30) as cli:
        r = cli.post(f"{SL}/campaigns/create", params=_sl(creds), json={"name": name})
        r.raise_for_status()
        return r.json()


def sl_set_sequence(creds, campaign_id, steps) -> dict:
    """steps: [{seq_delay_in_days, subject, email_body}]. Drafting — does not send."""
    seq = [{"seq_number": i + 1, "seq_delay_in_days": s.get("seq_delay_in_days", 1 if i else 0),
            "subject": s.get("subject", ""), "email_body": s.get("email_body", "")}
           for i, s in enumerate(steps)]
    with httpx.Client(timeout=40) as cli:
        r = cli.post(f"{SL}/campaigns/{campaign_id}/sequences", params=_sl(creds),
                     json={"sequences": seq})
        r.raise_for_status()
        return r.json()


def sl_add_leads(creds, campaign_id, leads) -> dict:
    with httpx.Client(timeout=40) as cli:
        r = cli.post(f"{SL}/campaigns/{campaign_id}/leads", params=_sl(creds),
                     json={"lead_list": leads})
        r.raise_for_status()
        return r.json()


def sl_start(creds, campaign_id) -> dict:
    """📧 STARTS sending the sequence. Gate behind approval."""
    with httpx.Client(timeout=30) as cli:
        r = cli.post(f"{SL}/campaigns/{campaign_id}/status", params=_sl(creds),
                     json={"status": "START"})
        r.raise_for_status()
        return {"ok": True}

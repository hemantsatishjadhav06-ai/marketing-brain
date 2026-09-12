"""WhatsApp Business — Meta Cloud API (graph.facebook.com).

Send template + session messages with the customer's own WhatsApp Business
credentials; parse the inbound webhook into (contact, text, kind); map keyword
triggers (PRICE / PDF / LOCATION / BOOK / CALL / DETAILS / INTERESTED) to a
mapped auto-reply + lead capture. Live only when credentials are saved; nothing
is sent otherwise.

Note on the graphiti reference: getzep/graphiti is a temporal knowledge-graph
memory library, not a WhatsApp SDK — it is not used here. Conversation memory is
already handled by the brand-memory system; WhatsApp threads live in the existing
conversations/messages tables.
"""
from __future__ import annotations

import os

import httpx

GRAPH = "https://graph.facebook.com/v21.0"

# keyword -> (intent, what the auto-reply should do)
TRIGGERS = {
    "PRICE": "share the price range and offer to connect with the team for an exact quote",
    "PDF": "send the brochure/mapped document and capture the lead",
    "BROCHURE": "send the brochure/mapped document and capture the lead",
    "LOCATION": "share the location/Google-Maps pin and nearest landmarks",
    "BOOK": "offer available site-visit / call slots and capture the lead",
    "CALL": "offer a callback and capture the phone number",
    "DETAILS": "share key project details (configs, sizes, price range) concisely",
    "INTERESTED": "acknowledge, qualify lightly, and route to the team",
}


def configured(creds) -> bool:
    return bool(creds and creds.get("access_token") and creds.get("phone_number_id"))


def send_text(creds, to: str, text: str) -> dict:
    """Send a free-form session message (allowed within the 24h customer window)."""
    if not configured(creds):
        raise ValueError("WhatsApp is not connected — save access_token + phone_number_id first.")
    pnid = creds["phone_number_id"]
    with httpx.Client(timeout=30) as cli:
        r = cli.post(f"{GRAPH}/{pnid}/messages",
                     headers={"Authorization": f"Bearer {creds['access_token']}"},
                     json={"messaging_product": "whatsapp", "to": to, "type": "text",
                           "text": {"body": text[:4000]}})
        r.raise_for_status()
        return r.json()


def send_template(creds, to: str, template: str, lang: str = "en_US", components=None) -> dict:
    """Send an approved template (required to OPEN a conversation outside the 24h window)."""
    if not configured(creds):
        raise ValueError("WhatsApp is not connected — save access_token + phone_number_id first.")
    pnid = creds["phone_number_id"]
    body = {"messaging_product": "whatsapp", "to": to, "type": "template",
            "template": {"name": template, "language": {"code": lang}}}
    if components:
        body["template"]["components"] = components
    with httpx.Client(timeout=30) as cli:
        r = cli.post(f"{GRAPH}/{pnid}/messages",
                     headers={"Authorization": f"Bearer {creds['access_token']}"}, json=body)
        r.raise_for_status()
        return r.json()


def parse_webhook(payload: dict):
    """Turn a Cloud API webhook body into a list of inbound {from, name, text, kind}.
    Ignores status-only callbacks. Never raises on a malformed body."""
    out = []
    try:
        for entry in payload.get("entry", []):
            for ch in entry.get("changes", []):
                v = ch.get("value", {})
                contacts = {c.get("wa_id"): (c.get("profile") or {}).get("name", "")
                            for c in v.get("contacts", [])}
                for m in v.get("messages", []):
                    frm = m.get("from", "")
                    if m.get("type") == "text":
                        text = (m.get("text") or {}).get("body", "")
                    elif m.get("type") == "button":
                        text = (m.get("button") or {}).get("text", "")
                    elif m.get("type") == "interactive":
                        inter = m.get("interactive") or {}
                        text = ((inter.get("button_reply") or inter.get("list_reply") or {}).get("title", ""))
                    else:
                        text = f"[{m.get('type', 'message')}]"
                    out.append({"from": frm, "name": contacts.get(frm, ""),
                                "text": text, "kind": m.get("type", "text"),
                                "message_id": m.get("id", "")})
    except Exception:
        pass
    return out


def detect_trigger(text: str):
    """Return (keyword, instruction) if the message is a known trigger word, else None."""
    t = (text or "").strip().upper()
    # exact word or the word as the whole message
    for kw, instr in TRIGGERS.items():
        if t == kw or kw in t.split():
            return kw, instr
    return None


def verify_token() -> str:
    return os.environ.get("WHATSAPP_VERIFY_TOKEN", "")

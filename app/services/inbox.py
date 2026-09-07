"""Communication inbox — one place for every customer conversation.

The vision's Communication Engine (§9) is a single inbox spanning WhatsApp,
Instagram, Facebook, email and website chat, where the brain drafts a reply in
the brand's voice and a human sends it. This module is the durable core of that
engine: contacts group into conversations, conversations hold messages, and the
brain drafts — but never sends — a reply.

Two deliberate boundaries keep this honest and safe:

  * Inbound messages arrive through an authenticated ingest endpoint. A real
    platform webhook (Meta, Twilio) is a thin bridge that authenticates and
    POSTs here; wiring a specific platform needs that platform's credentials
    and, for Meta, app review — neither of which lives in this repo yet.
  * Outbound replies are drafted by the brain and always wait for a human
    (§15). Actual delivery to a channel is a pluggable step: with no channel
    connector configured the send is recorded as *simulated* rather than
    silently pretending a message left the building.

Everything persists through the same document helpers as the rest of the app,
so it works unchanged on Supabase REST, Postgres or SQLite.
"""
from __future__ import annotations

import time

from ..core import database as db

CONVERSATIONS = "conversations"
MESSAGES = "messages"

# The five channels the Communication Engine is meant to span (§9). WhatsApp is
# the first target for live delivery; the rest ingest and draft today and gain
# live send as each platform's bridge is wired.
CHANNELS = ("whatsapp", "instagram", "facebook", "email", "webchat")


def _clean(text):
    return " ".join((text or "").split())


# ---------- inbound ----------

def record_inbound(brand_id, channel, contact_ref, text, contact_name=""):
    """Record a customer message, creating the conversation if it is the first.

    Returns ``(conversation, message)`` as decoded documents.
    """
    channel = (channel or "").strip().lower()
    if channel not in CHANNELS:
        raise ValueError(f"unknown channel '{channel}'")
    contact_ref = _clean(contact_ref)
    text = _clean(text)
    if not contact_ref or not text:
        raise ValueError("contact_ref and text are required")

    convo = _find_conversation(brand_id, channel, contact_ref)
    now = time.time()
    if convo is None:
        cid = db.insert_doc(
            CONVERSATIONS, brand_id,
            {
                "contact_ref": contact_ref,
                "contact_name": _clean(contact_name) or contact_ref,
                "channel": channel,
                "last_text": text,
                "last_direction": "in",
                "last_at": now,
                "unread": 1,
            },
            channel=channel, contact_ref=contact_ref, status="open",
        )
        convo = db.get_doc(CONVERSATIONS, cid)
    else:
        cid = convo["id"]
        payload = dict(convo.get("payload") or {})
        if _clean(contact_name):
            payload["contact_name"] = _clean(contact_name)
        payload.update({
            "last_text": text, "last_direction": "in", "last_at": now,
            "unread": int(payload.get("unread", 0)) + 1,
        })
        db.update_doc(CONVERSATIONS, cid, payload=payload, status="open")
        convo["payload"] = payload

    mid = db.insert_doc(
        MESSAGES, brand_id,
        {"text": text, "channel": channel, "author": payload_name(convo), "ts": now},
        conversation_id=cid, direction="in", status="received",
    )
    return convo, db.get_doc(MESSAGES, mid)


def payload_name(convo):
    return (convo.get("payload") or {}).get("contact_name") or "customer"


def _find_conversation(brand_id, channel, contact_ref):
    rows = db.list_docs(CONVERSATIONS, brand_id, channel=channel, contact_ref=contact_ref)
    return rows[0] if rows else None


# ---------- reads ----------

def list_conversations(brand_id, status=None):
    """Conversation summaries, most recently active first."""
    where = {"status": status} if status else {}
    rows = db.list_docs(CONVERSATIONS, brand_id, **where)
    rows.sort(key=lambda r: (r.get("payload") or {}).get("last_at", r.get("created_at", 0)), reverse=True)
    return [_summary(r) for r in rows]


def _summary(convo):
    p = convo.get("payload") or {}
    return {
        "id": convo["id"],
        "channel": convo.get("channel"),
        "status": convo.get("status"),
        "contact_ref": p.get("contact_ref"),
        "contact_name": p.get("contact_name"),
        "last_text": p.get("last_text"),
        "last_direction": p.get("last_direction"),
        "last_at": p.get("last_at"),
        "unread": int(p.get("unread", 0)),
    }


def list_messages(brand_id, conversation_id):
    """All messages in a conversation, oldest first (chat order)."""
    rows = db.list_docs(MESSAGES, brand_id, conversation_id=conversation_id)
    rows.sort(key=lambda r: r.get("created_at", 0))
    out = []
    for r in rows:
        p = r.get("payload") or {}
        out.append({
            "id": r["id"],
            "direction": r.get("direction"),
            "status": r.get("status"),
            "text": p.get("text"),
            "author": p.get("author"),
            "ts": p.get("ts") or r.get("created_at"),
        })
    return out


def mark_read(brand_id, conversation_id):
    convo = db.get_doc(CONVERSATIONS, conversation_id)
    if not convo:
        return
    payload = dict(convo.get("payload") or {})
    if payload.get("unread"):
        payload["unread"] = 0
        db.update_doc(CONVERSATIONS, conversation_id, payload=payload)


# ---------- drafting (the brain writes, a human sends) ----------

def draft_reply(brand, convo):
    """Have the brain draft a reply to the latest customer message.

    Persists the draft as an outbound message with status ``draft`` and returns
    it. Nothing is sent — a human approves the draft with :func:`send`.
    """
    brand_id = brand["id"]
    convo_id = convo["id"]
    transcript = list_messages(brand_id, convo_id)
    if not transcript:
        raise ValueError("no messages to reply to")

    text = _generate(brand, convo, transcript)
    mid = db.insert_doc(
        MESSAGES, brand_id,
        {"text": text, "channel": convo.get("channel"), "author": brand["name"], "ts": time.time(),
         "drafted": True},
        conversation_id=convo_id, direction="out", status="draft",
    )
    return db.get_doc(MESSAGES, mid)


def _generate(brand, convo, transcript):
    """Call the LLM to write the reply. Isolated so tests can monkeypatch it."""
    from ..ai import engine

    lines = []
    for m in transcript[-12:]:
        who = "Customer" if m["direction"] == "in" else brand["name"]
        lines.append(f"{who}: {m['text']}")
    convo_text = "\n".join(lines)

    system = (
        f"You are the customer-conversation voice for {brand['name']} on "
        f"{convo.get('channel', 'chat')}. Reply to the latest customer message in the "
        "brand's voice. Follow the brand's fact rules strictly: quote prices only as "
        "ranges and offer to have the team confirm exact figures, never invent "
        "guarantees, availability, or legal claims, and always keep the door open to "
        "connect with the team. Be concise, warm and specific — one short paragraph "
        "suitable for a direct message.\n\n"
        f"Brand context: {engine._brand_context(brand)}"
    )
    reply = engine._chat(
        [{"role": "system", "content": system}, {"role": "user", "content": convo_text}],
        max_tokens=400, temperature=0.6,
    )
    return _clean(reply)


# ---------- send (human-approved) ----------

def send(brand, message_id, edited_text=""):
    """Approve and send a drafted reply.

    If the human edited the text before sending, the change is filed as a brand
    correction so the brain drafts closer next time (§15 feedback loop). Actual
    channel delivery is pluggable: with no connector for the channel, the send
    is recorded as ``simulated`` rather than pretending it was delivered.
    Returns the updated message document.
    """
    brand_id = brand["id"]
    msg = db.get_doc(MESSAGES, message_id)
    if not msg or msg.get("brand_id") != brand_id:
        raise ValueError("message not found for this brand")
    if msg.get("direction") != "out":
        raise ValueError("only an outbound draft can be sent")

    payload = dict(msg.get("payload") or {})
    original = payload.get("text", "")
    edited_text = _clean(edited_text)
    if edited_text and edited_text != _clean(original):
        _file_correction(brand_id, original, edited_text)
        payload["text"] = edited_text
        payload["edited"] = True

    channel = payload.get("channel") or ""
    delivery = _deliver(brand, channel, payload.get("text", ""))
    payload["delivery"] = delivery
    payload["sent_at"] = time.time()
    db.update_doc(MESSAGES, message_id, payload=payload, status="sent")

    convo_id = msg.get("conversation_id")
    convo = db.get_doc(CONVERSATIONS, convo_id) if convo_id else None
    if convo:
        cp = dict(convo.get("payload") or {})
        cp.update({"last_text": payload.get("text", ""), "last_direction": "out",
                   "last_at": payload["sent_at"]})
        db.update_doc(CONVERSATIONS, convo_id, payload=cp)
    return db.get_doc(MESSAGES, message_id)


def discard(brand, message_id):
    """Throw away a draft the human doesn't want to send."""
    brand_id = brand["id"]
    msg = db.get_doc(MESSAGES, message_id)
    if not msg or msg.get("brand_id") != brand_id:
        raise ValueError("message not found for this brand")
    if msg.get("status") != "draft":
        raise ValueError("only a draft can be discarded")
    db.delete_doc(MESSAGES, message_id)
    return {"ok": True, "discarded": message_id}


def _deliver(brand, channel, text):
    """Send to the channel if a connector is wired, else record a simulated send.

    This is the single seam where a live WhatsApp / Instagram / email bridge
    plugs in. Until one is configured for the brand + channel, delivery is
    honestly marked simulated so nothing claims to have shipped when it hasn't.
    """
    try:
        creds = db.get_connectors(brand["id"]).get(channel)
    except Exception:
        creds = None
    if creds:
        # A future channel adapter delivers here using `creds`. Kept explicit so
        # it is obvious this path is not yet implemented for any live platform.
        return {"mode": "connector", "channel": channel, "delivered": False,
                "note": "connector present; live send adapter not yet implemented"}
    return {"mode": "simulated", "channel": channel, "delivered": False}


def _file_correction(brand_id, original, edited):
    try:
        from . import memory
        memory.remember(
            brand_id,
            f"When replying to customers, prefer this phrasing: '{edited}' "
            f"(a human rewrote the draft '{original[:160]}').",
            kind="correction", weight=1.5, source="inbox",
        )
    except Exception:
        pass

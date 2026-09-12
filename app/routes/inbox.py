"""Communication inbox routes (§9).

One inbox across channels: ingest inbound customer messages, list and read
conversations, have the brain draft a reply, and — only on a human's say-so —
send it. Every endpoint is brand-scoped and ownership-checked exactly like the
rest of the API.
"""
from fastapi import APIRouter, Depends

from ._shared import *  # noqa: F401,F403  (current_user, _brand_or_404, _doc_or_404, HTTPException, db, ...)
from ..services import inbox

router = APIRouter()


class InboundIn(BaseModel):
    channel: str
    contact_ref: str
    text: str
    contact_name: str = ""


class SendIn(BaseModel):
    text: str = ""  # optional edited text; empty sends the draft as written


@router.post("/api/brands/{bid}/inbox/inbound")
def ingest_inbound(bid: str, body: InboundIn, user=Depends(current_user)):
    """Record an inbound customer message.

    A channel bridge (WhatsApp/Meta/Twilio/website widget) authenticates and
    POSTs here; the operator can also post directly. Creates the conversation on
    the first message from a contact.
    """
    _brand_or_404(bid, user)
    try:
        convo, msg = inbox.record_inbound(bid, body.channel, body.contact_ref, body.text, body.contact_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "conversation_id": convo["id"], "message_id": msg["id"]}


@router.get("/api/brands/{bid}/inbox")
def list_inbox(bid: str, status: str = None, user=Depends(current_user)):
    """Conversation list for the brand, most recently active first."""
    _brand_or_404(bid, user)
    convos = inbox.list_conversations(bid, status=status)
    return {"conversations": convos, "channels": list(inbox.CHANNELS)}


@router.get("/api/brands/{bid}/inbox/{cid}")
def get_conversation(bid: str, cid: str, user=Depends(current_user)):
    """One conversation with its full message thread (marks it read)."""
    _brand_or_404(bid, user)
    _doc_or_404("conversations", cid, bid)
    inbox.mark_read(bid, cid)
    return {"id": cid, "messages": inbox.list_messages(bid, cid)}


@router.post("/api/brands/{bid}/inbox/{cid}/draft")
def draft(bid: str, cid: str, user=Depends(current_user)):
    """Have the brain draft a reply to the latest customer message.

    The draft is stored and returned; it is NOT sent — a human sends it.
    """
    brand = _brand_or_404(bid, user)
    _doc_or_404("conversations", cid, bid)
    convo = db.get_doc("conversations", cid)
    try:
        msg = inbox.draft_reply(brand, convo)
    except ValueError as e:
        raise HTTPException(400, str(e))
    p = msg.get("payload") or {}
    return {"ok": True, "message_id": msg["id"], "status": msg.get("status"), "text": p.get("text")}


@router.post("/api/brands/{bid}/inbox/messages/{mid}/send")
def send_message(bid: str, mid: str, body: SendIn, user=Depends(current_user)):
    """Approve and send a drafted reply (optionally edited first)."""
    brand = _brand_or_404(bid, user)
    _doc_or_404("messages", mid, bid)
    try:
        msg = inbox.send(brand, mid, edited_text=body.text)
    except ValueError as e:
        raise HTTPException(400, str(e))
    p = msg.get("payload") or {}
    return {"ok": True, "message_id": mid, "status": msg.get("status"),
            "text": p.get("text"), "delivery": p.get("delivery")}


@router.delete("/api/brands/{bid}/inbox/messages/{mid}")
def discard_message(bid: str, mid: str, user=Depends(current_user)):
    """Discard a draft the human doesn't want to send."""
    brand = _brand_or_404(bid, user)
    _doc_or_404("messages", mid, bid)
    try:
        return inbox.discard(brand, mid)
    except ValueError as e:
        raise HTTPException(400, str(e))

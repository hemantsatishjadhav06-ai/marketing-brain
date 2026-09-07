"""Coverage for the Communication inbox (§9).

Exercises the real database layer against a temporary SQLite file — the two new
document tables, the conversation/message flow, brand isolation, and the
draft-then-human-send model. The LLM call is monkeypatched so the draft step is
deterministic and offline.
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "inbox_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.core import database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import inbox, memory as mem  # noqa: E402

client = TestClient(app)


@pytest.fixture
def brand():
    return db.create_brand("Neopolis Infra LLP", "neopolis-infra", "https://neopolisinfra.com", {})


@pytest.fixture(autouse=True)
def _open_access(monkeypatch):
    monkeypatch.setenv("DIRECT_ACCESS", "true")


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch):
    """No network in the draft step — return a canned, on-brand reply."""
    monkeypatch.setattr(
        "app.ai.engine._chat",
        lambda *a, **k: "Yes, the Kokapet 3 BHK is available. Landlord-share is fully "
                        "registerable; the team can confirm the exact price for your unit.",
    )


def _inbound(bid, **over):
    body = {"channel": "whatsapp", "contact_ref": "+919000000001", "text": "Is the Kokapet 3 BHK available?"}
    body.update(over)
    return client.post(f"/api/brands/{bid}/inbox/inbound", json=body)


# ------------------------------------------------------------------ inbound

def test_inbound_creates_conversation_and_message(brand):
    r = _inbound(brand)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] and data["conversation_id"] and data["message_id"]

    lst = client.get(f"/api/brands/{brand}/inbox").json()
    assert len(lst["conversations"]) == 1
    convo = lst["conversations"][0]
    assert convo["channel"] == "whatsapp"
    assert convo["unread"] == 1
    assert convo["contact_ref"] == "+919000000001"


def test_second_message_reuses_conversation_and_bumps_unread(brand):
    _inbound(brand)
    _inbound(brand, text="And what is the price range?")
    convos = client.get(f"/api/brands/{brand}/inbox").json()["conversations"]
    assert len(convos) == 1
    assert convos[0]["unread"] == 2


def test_unknown_channel_rejected(brand):
    r = _inbound(brand, channel="carrier-pigeon")
    assert r.status_code == 400


# --------------------------------------------------------------- read thread

def test_get_conversation_returns_thread_and_marks_read(brand):
    cid = _inbound(brand).json()["conversation_id"]
    convo = client.get(f"/api/brands/{brand}/inbox/{cid}").json()
    assert convo["id"] == cid
    assert len(convo["messages"]) == 1
    assert convo["messages"][0]["direction"] == "in"
    # reading clears the unread badge
    convos = client.get(f"/api/brands/{brand}/inbox").json()["conversations"]
    assert convos[0]["unread"] == 0


# ------------------------------------------------------------------- drafting

def test_draft_creates_outbound_draft_without_sending(brand):
    cid = _inbound(brand).json()["conversation_id"]
    r = client.post(f"/api/brands/{brand}/inbox/{cid}/draft")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "draft"
    assert "Kokapet" in d["text"]
    # the thread now holds the inbound plus a drafted (not sent) reply
    msgs = client.get(f"/api/brands/{brand}/inbox/{cid}").json()["messages"]
    assert [m["direction"] for m in msgs] == ["in", "out"]
    assert msgs[1]["status"] == "draft"


def test_send_marks_sent_and_records_simulated_delivery(brand):
    cid = _inbound(brand).json()["conversation_id"]
    mid = client.post(f"/api/brands/{brand}/inbox/{cid}/draft").json()["message_id"]
    r = client.post(f"/api/brands/{brand}/inbox/messages/{mid}/send", json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "sent"
    assert out["delivery"]["mode"] == "simulated"  # no live connector wired
    assert out["delivery"]["delivered"] is False


def test_edited_send_files_a_correction(brand):
    cid = _inbound(brand).json()["conversation_id"]
    mid = client.post(f"/api/brands/{brand}/inbox/{cid}/draft").json()["message_id"]
    edited = "Yes! It's available — shall I have our team call you with the exact price?"
    client.post(f"/api/brands/{brand}/inbox/messages/{mid}/send", json={"text": edited})
    corrections = [m for m in mem.recall(brand) if m["kind"] == "correction"]
    assert any("call you" in c["content"] for c in corrections)


def test_discard_removes_draft(brand):
    cid = _inbound(brand).json()["conversation_id"]
    mid = client.post(f"/api/brands/{brand}/inbox/{cid}/draft").json()["message_id"]
    assert client.delete(f"/api/brands/{brand}/inbox/messages/{mid}").status_code == 200
    msgs = client.get(f"/api/brands/{brand}/inbox/{cid}").json()["messages"]
    assert all(m["direction"] == "in" for m in msgs)


# --------------------------------------------------------------- isolation

def test_one_brand_cannot_read_anothers_conversation(brand):
    cid = _inbound(brand).json()["conversation_id"]
    other = db.create_brand("Rival Realty", "rival-realty", "https://example.com", {})
    r = client.get(f"/api/brands/{other}/inbox/{cid}")
    assert r.status_code == 404
    # and cannot send another brand's draft
    mid = client.post(f"/api/brands/{brand}/inbox/{cid}/draft").json()["message_id"]
    r2 = client.post(f"/api/brands/{other}/inbox/messages/{mid}/send", json={})
    assert r2.status_code == 404

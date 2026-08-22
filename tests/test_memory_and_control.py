"""Coverage for brand memory, run history, operating mode and the approval queue.

These exercise the real database layer against a temporary SQLite file, so the
schema and the document helpers are covered too — not just the pure functions.
"""
from __future__ import annotations

import io
import os
import tempfile

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "mem_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.core import database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import memory as mem  # noqa: E402

client = TestClient(app)


@pytest.fixture
def brand():
    return db.create_brand("Testco Realty", "testco-realty", "https://example.com", {})


@pytest.fixture(autouse=True)
def _open_access(monkeypatch):
    """Authenticate these tests without a token.

    Set per-test rather than at import: DIRECT_ACCESS is read per request, and
    setting it globally leaked into test_smoke's auth assertions.
    """
    monkeypatch.setenv("DIRECT_ACCESS", "true")


# ------------------------------------------------------------------- memory

def test_remember_and_recall_orders_by_authority(brand):
    mem.remember(brand, "A learned thing.", kind="learning")
    mem.remember(brand, "A hard rule.", kind="rule")
    mem.remember(brand, "A correction.", kind="correction")
    kinds = [m["kind"] for m in mem.recall(brand)]
    assert kinds == ["rule", "correction", "learning"]


def test_repeating_a_memory_reinforces_instead_of_duplicating(brand):
    mem.remember(brand, "Say it once.", kind="rule", weight=1)
    mem.remember(brand, "say it ONCE.", kind="rule", weight=2)  # same text, different case
    rows = mem.recall(brand)
    assert len(rows) == 1
    assert rows[0]["hits"] == 2
    assert rows[0]["weight"] == pytest.approx(3.0)


def test_blank_content_is_not_stored(brand):
    assert mem.remember(brand, "   ") is None
    assert mem.recall(brand) == []


def test_unknown_kind_falls_back_to_learning(brand):
    mem.remember(brand, "Something.", kind="nonsense")
    assert mem.recall(brand)[0]["kind"] == "learning"


def test_rejection_is_captured_as_a_correction(brand):
    mem.capture_approval(brand, {"id": "c1", "payload": {"title": "Diwali post", "format": "post"}},
                         "changes_requested", note="we don't do festive")
    row = mem.recall(brand)[0]
    assert row["kind"] == "correction"
    assert "Diwali post" in row["content"]
    assert "we don't do festive" in row["content"]


def test_approval_is_captured_as_a_learning(brand):
    mem.capture_approval(brand, {"id": "c2", "payload": {"title": "Scarcity angle", "format": "post"}},
                         "approved")
    row = mem.recall(brand)[0]
    assert row["kind"] == "learning"
    assert "Scarcity angle" in row["content"]


def test_context_block_is_empty_without_memory(brand):
    assert mem.context_block(brand) == ""


def test_context_block_labels_each_kind(brand):
    mem.remember(brand, "Never say luxury twice.", kind="rule")
    block = mem.context_block(brand)
    assert "BRAND MEMORY" in block
    assert "[RULE] Never say luxury twice." in block


def test_memory_reaches_the_prompt_context(brand):
    from app.ai import engine
    mem.remember(brand, "Never say luxury twice.", kind="rule")
    ctx = engine._brand_context(db.get_brand(brand))
    assert "Never say luxury twice." in ctx


def test_forget_removes_a_memory(brand):
    mid = mem.remember(brand, "Temporary.", kind="rule")
    assert mem.forget(mid) is True
    assert mem.recall(brand) == []


def test_recall_is_scoped_to_one_brand(brand):
    other = db.create_brand("Other Co", "other-co", "https://other.example", {})
    mem.remember(brand, "Belongs to the first brand.", kind="rule")
    assert mem.recall(other) == []


# -------------------------------------------------------------- run history

def test_run_history_records_outcome_and_duration(brand):
    rid = mem.start_run(brand, "blueprint", creative_id="c9")
    mem.finish_run(rid, "done", result={"asset": "x.png"})
    rows = mem.history(brand)
    assert len(rows) == 1
    assert rows[0]["status"] == "done"
    assert rows[0]["payload"]["result"] == {"asset": "x.png"}
    assert "duration_s" in rows[0]["payload"]


def test_failed_run_keeps_the_error(brand):
    rid = mem.start_run(brand, "revise")
    mem.finish_run(rid, "error", error="fal timed out")
    assert mem.history(brand)[0]["payload"]["error"] == "fal timed out"


def test_finish_run_tolerates_a_missing_id():
    mem.finish_run(None, "done")  # must not raise


# ---------------------------------------------------------------- API layer

def test_mode_defaults_to_auto_and_persists():
    bid = client.post("/api/brands", json={"name": "Modeco", "website": "https://m.example"}).json()["id"]
    assert client.get(f"/api/brands/{bid}/mode").json()["mode"] == "auto"
    assert client.post(f"/api/brands/{bid}/mode", json={"mode": "manual"}).status_code == 200
    assert client.get(f"/api/brands/{bid}/mode").json()["mode"] == "manual"


def test_unknown_mode_is_rejected():
    bid = client.post("/api/brands", json={"name": "Modeco2", "website": "https://m2.example"}).json()["id"]
    assert client.post(f"/api/brands/{bid}/mode", json={"mode": "turbo"}).status_code == 400


def test_memory_api_round_trip():
    bid = client.post("/api/brands", json={"name": "Apico", "website": "https://a.example"}).json()["id"]
    assert client.post(f"/api/brands/{bid}/memory",
                       json={"content": "Rule one.", "kind": "rule", "weight": 4}).status_code == 200
    listing = client.get(f"/api/brands/{bid}/memory").json()
    assert listing["count"] == 1
    mid = listing["memory"][0]["id"]
    assert client.delete(f"/api/brands/{bid}/memory/{mid}").status_code == 200
    assert client.get(f"/api/brands/{bid}/memory").json()["count"] == 0


def test_memory_api_rejects_bad_input():
    bid = client.post("/api/brands", json={"name": "Badin", "website": "https://b.example"}).json()["id"]
    assert client.post(f"/api/brands/{bid}/memory", json={"content": "  "}).status_code == 400
    assert client.post(f"/api/brands/{bid}/memory",
                       json={"content": "x", "kind": "nope"}).status_code == 400


def test_approval_queue_reports_counts():
    body = client.get("/api/approvals").json()
    assert set(body) == {"waiting_for_approval", "changes_requested", "counts"}
    assert set(body["counts"]) == {"waiting", "changes_requested"}


def test_profile_endpoint_reports_stored_data_counts():
    bid = client.post("/api/brands", json={"name": "Profco", "website": "https://p.example"}).json()["id"]
    body = client.get(f"/api/brands/{bid}/profile").json()
    assert body["name"] == "Profco"
    assert set(body["counts"]) == {"ideas", "creatives", "calendar", "runs"}


def test_profiles_roster_lists_brands():
    body = client.get("/api/profiles").json()
    assert body["count"] >= 1
    assert "counts" in body["profiles"][0]


def test_revise_requires_an_instruction():
    bid = client.post("/api/brands", json={"name": "Revco", "website": "https://r.example"}).json()["id"]
    cid = db.insert_doc("creatives", bid, {"title": "A post"}, channel="instagram", format="post")
    assert client.post(f"/api/brands/{bid}/creatives/{cid}/revise",
                       json={"instruction": "   "}).status_code == 400


def test_revise_files_the_instruction_as_a_correction(monkeypatch):
    import threading
    monkeypatch.setattr(threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda s: None})())
    bid = client.post("/api/brands", json={"name": "Revco2", "website": "https://r2.example"}).json()["id"]
    cid = db.insert_doc("creatives", bid, {"title": "A post"}, channel="instagram", format="post")
    r = client.post(f"/api/brands/{bid}/creatives/{cid}/revise",
                    json={"instruction": "Make the headline shorter", "remember": True})
    assert r.status_code == 200
    assert any("Make the headline shorter" in m["content"] for m in mem.recall(bid))


# --------------------------------------------------------------- logo upload

def _png(size=(400, 160)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", size, (0, 24, 72, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_logo_upload_stores_path_and_b64():
    bid = client.post("/api/brands", json={"name": "Logoco", "website": "https://l.example"}).json()["id"]
    r = client.post(f"/api/brands/{bid}/logo", files={"file": ("logo.png", _png(), "image/png")})
    assert r.status_code == 200
    kit = (db.get_brand(bid).get("profile") or {}).get("brand_kit") or {}
    assert kit["logo"] == "brand/logo.png"
    assert kit["logo_b64"]


def test_logo_upload_rejects_non_images():
    bid = client.post("/api/brands", json={"name": "Logoco2", "website": "https://l2.example"}).json()["id"]
    assert client.post(f"/api/brands/{bid}/logo",
                       files={"file": ("a.txt", b"hello", "text/plain")}).status_code == 400
    assert client.post(f"/api/brands/{bid}/logo",
                       files={"file": ("a.png", b"not-an-image", "image/png")}).status_code == 400
    assert client.post(f"/api/brands/{bid}/logo",
                       files={"file": ("a.png", b"", "image/png")}).status_code == 400

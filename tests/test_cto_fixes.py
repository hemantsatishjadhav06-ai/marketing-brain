"""Regression tests for the CTO launch-day fixes (named per CTO §81: MODULE_scenario_expected).

Each test pins a defect that was either found live on prod or in the audit:
publish idempotency, idea-state IDOR, workspace tenant scoping, PBKDF2 hashing +
rehash-on-login, token revocation on user deletion, cost guard on the expensive
generation routes, and unsafe competitor URLs rejected at creation.
"""
from __future__ import annotations

import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "cto_fixes.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ.pop("DIRECT_ACCESS", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.core import auth, database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import workspace as ws  # noqa: E402

client = TestClient(app)


def _brand(name):
    return db.create_brand(name, ws.slugify(name), "", {}, "")


def _user(role, bid=""):
    email = f"{role}-{uuid.uuid4().hex[:8]}@t.local"
    uid = db.create_user(email, auth.hash_pw("pw-" + email), role=role, brand_id=bid)
    return uid, email, {"Authorization": "Bearer " + auth.make_token(uid, role, bid)}


def _creative(bid):
    return db.insert_doc("creatives", bid, {"title": "t", "caption": "c", "format": "post"}, channel="instagram", format="post")


# ---------------------------------------------------------------- idempotency

def test_PUBLISH_duplicate_simulated_request_single_row():
    bid = _brand("Idem " + uuid.uuid4().hex[:6]); _, _, h = _user("owner", bid); cid = _creative(bid)
    body = {"creative_id": cid, "channel": "instagram", "mode": "simulated"}
    r1 = client.post(f"/api/brands/{bid}/publish", json=body, headers=h); assert r1.status_code == 200
    r2 = client.post(f"/api/brands/{bid}/publish", json=body, headers=h); assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"], "second identical request must return the existing row"
    assert len(client.get(f"/api/brands/{bid}/publish", headers=h).json()) == 1


def test_PUBLISH_live_republish_of_published_creative_blocked():
    bid = _brand("Idem2 " + uuid.uuid4().hex[:6]); _, _, h = _user("owner", bid); cid = _creative(bid)
    db.insert_doc("publish_queue", bid, {"ok": True}, creative_id=cid, channel="instagram", mode="live", status="published")
    r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "channel": "instagram", "mode": "live"}, headers=h)
    assert r.status_code == 409


# ---------------------------------------------------------------- IDOR

def test_IDOR_idea_state_cross_brand_blocked():
    a = _brand("A " + uuid.uuid4().hex[:6]); b = _brand("B " + uuid.uuid4().hex[:6])
    _, _, ha = _user("owner", a)
    iid_b = db.insert_doc("ideas", b, {"title": "b-idea"}, channel="instagram", state="new")
    r = client.post(f"/api/brands/{a}/ideas/{iid_b}/state", json={"state": "approved"}, headers=ha)
    assert r.status_code == 404
    assert db.get_doc("ideas", iid_b)["state"] == "new", "B's idea must be untouched"


def test_IDEA_state_value_validated():
    a = _brand("A2 " + uuid.uuid4().hex[:6]); _, _, ha = _user("owner", a)
    iid = db.insert_doc("ideas", a, {"title": "x"}, channel="instagram", state="new")
    assert client.post(f"/api/brands/{a}/ideas/{iid}/state", json={"state": "published"}, headers=ha).status_code == 400
    assert client.post(f"/api/brands/{a}/ideas/{iid}/state", json={"state": "approved"}, headers=ha).status_code == 200


# ---------------------------------------------------------------- workspace tenant scoping

def test_TENANT_workspace_file_of_other_brand_blocked():
    a = _brand("WsA " + uuid.uuid4().hex[:6]); b = _brand("WsB " + uuid.uuid4().hex[:6])
    ba, bb = db.get_brand(a), db.get_brand(b)
    ws.write_json(bb["slug"], "brand-profile/profile.json", {"secret": "B-only"})
    ws.write_json(ba["slug"], "brand-profile/profile.json", {"secret": "A-only"})
    _, _, ha = _user("client", a)
    assert client.get(f"/workspaces/{bb['slug']}/brand-profile/profile.json", headers=ha).status_code == 404
    r = client.get(f"/workspaces/{ba['slug']}/brand-profile/profile.json", headers=ha)
    assert r.status_code == 200 and "A-only" in r.text
    _, _, hadmin = _user("admin")
    assert client.get(f"/workspaces/{bb['slug']}/brand-profile/profile.json", headers=hadmin).status_code == 200


# ---------------------------------------------------------------- password hashing

def test_AUTH_password_hash_is_pbkdf2_and_verifies():
    h = auth.hash_pw("correct horse")
    assert h.startswith("pbkdf2$") and auth.check_pw("correct horse", h) and not auth.check_pw("wrong", h)
    assert not auth.needs_rehash(h)


def test_AUTH_legacy_hash_still_verifies_and_is_rehashed_on_login():
    import hashlib
    email = f"legacy-{uuid.uuid4().hex[:8]}@t.local"; pw = "LegacyPass123"
    legacy = "abcd1234:" + hashlib.sha256(("abcd1234" + pw).encode()).hexdigest()
    assert auth.check_pw(pw, legacy) and auth.needs_rehash(legacy)
    uid = db.create_user(email, legacy, role="admin")
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200
    assert db.get_user_by_email(email)["pw_hash"].startswith("pbkdf2$"), "login must upgrade the legacy hash"
    assert client.post("/api/auth/login", json={"email": email, "password": pw}).status_code == 200


# ---------------------------------------------------------------- revocation

def test_AUTH_deleted_user_token_revoked():
    uid, _, h = _user("admin")
    assert client.get("/api/auth/me", headers=h).status_code == 200
    db.delete_user(uid)
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_AUTH_role_change_takes_effect_without_new_token():
    bid = _brand("Role " + uuid.uuid4().hex[:6]); uid, _, h = _user("admin")
    # demote the admin to a client of one brand; the old admin token must lose admin rights immediately
    with db._lock, db._conn() as c:
        c.execute("UPDATE users SET role='client', brand_id=? WHERE id=?", (bid, uid))
    assert client.get("/api/users", headers=h).status_code == 403


# ---------------------------------------------------------------- cost guard on expensive routes

def test_COST_guard_gates_studio_and_revise_routes(monkeypatch):
    from app.core import guard
    monkeypatch.setattr(guard, "check_generation", lambda bid: (False, "daily cap reached"))
    bid = _brand("Cost " + uuid.uuid4().hex[:6]); _, _, h = _user("owner", bid); cid = _creative(bid)
    assert client.post(f"/api/brands/{bid}/studio/moodboard", json={"topic": "x", "format": "post"}, headers=h).status_code == 429
    assert client.post(f"/api/brands/{bid}/studio/carousel", json={"prompts": ["a"]}, headers=h).status_code == 429
    assert client.post(f"/api/brands/{bid}/creatives/{cid}/revise", json={"instruction": "make it blue", "remember": False}, headers=h).status_code == 429
    assert client.post(f"/api/brands/{bid}/creatives/{cid}/proceed", headers=h).status_code == 429


def test_COST_guard_gates_background_image_loop(monkeypatch):
    from app.core import guard
    from app.routes import _shared
    monkeypatch.setattr(guard, "check_generation", lambda bid: (False, "daily cap reached"))
    bid = _brand("CostBg " + uuid.uuid4().hex[:6]); b = db.get_brand(bid); cid = _creative(bid)
    called = {"n": 0}
    monkeypatch.setattr(_shared.ai_engine, "generate_image", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or b"x")
    with pytest.raises(RuntimeError, match="daily cap"):
        _shared._generate_image(b, cid)
    assert called["n"] == 0, "the paid model must not be called once the cap is hit"


# ---------------------------------------------------------------- SSRF at creation

@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8000/", "file:///etc/passwd", "http://10.0.0.5/"])
def test_SSRF_private_competitor_url_rejected_at_creation(url):
    bid = _brand("Ssrf " + uuid.uuid4().hex[:6]); _, _, h = _user("owner", bid)
    r = client.post(f"/api/brands/{bid}/competitors", json={"url": url, "name": "x"}, headers=h)
    assert r.status_code == 400
    assert client.get(f"/api/brands/{bid}/competitors", headers=h).json() == []


def test_ALGO_audit_score_derived_when_model_omits_it():
    from app.ai import engine
    out = engine._harden_audit({"signals": [{"signal": "watch_time", "score": 8}, {"signal": "send_trigger", "score": 4},
                                            {"signal": "save_value", "score": 6}], "verdict": "ok"})
    # (8*2 + 4*2 + 6*1) / (10*2 + 10*2 + 10*1) = 30/50 → 59
    assert out["algo_score"] == 59 and out["score"] == 59
    assert engine._harden_audit({"overall_score": 42})["algo_score"] == 42
    assert engine._harden_audit("garbage")["algo_score"] is None

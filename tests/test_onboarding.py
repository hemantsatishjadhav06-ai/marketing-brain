"""Coverage for self-serve multi-company onboarding.

Exercises the real DB layer against a temp SQLite file: company signup (and its
gate), user invites + accept, password reset, the master companies overview, and
cross-company isolation (an owner cannot manage another company).
"""
from __future__ import annotations

import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "onb_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.core import database as db  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _master(monkeypatch):
    # Default: authenticated as the master (admin) account.
    monkeypatch.setenv("DIRECT_ACCESS", "true")


def _u():
    """A unique token so tests never collide on a shared/dirty database."""
    return uuid.uuid4().hex[:8]


def _signup(monkeypatch, name=None, email=None, pw="supersecret1"):
    monkeypatch.setenv("SIGNUPS_OPEN", "true")
    name = name or ("Co " + _u())
    email = email or ("owner+" + _u() + "@test.co")
    r = client.post("/api/signup", json={"company_name": name, "email": email,
                                        "password": pw, "website": "https://acme.test"})
    return r, email


# ------------------------------------------------------------------ signup

def test_signup_closed_by_default(monkeypatch):
    monkeypatch.setenv("SIGNUPS_OPEN", "false")
    r = client.post("/api/signup", json={"company_name": "X", "email": f"x+{_u()}@x.test", "password": "supersecret1"})
    assert r.status_code == 403


def test_signup_creates_company_and_owner(monkeypatch):
    r, email = _signup(monkeypatch)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["role"] == "owner" and d["brand_id"] and d["token"]
    lr = client.post("/api/auth/login", json={"email": email, "password": "supersecret1"})
    assert lr.status_code == 200 and lr.json()["role"] == "owner"


def test_signup_rejects_short_password(monkeypatch):
    monkeypatch.setenv("SIGNUPS_OPEN", "true")
    r = client.post("/api/signup", json={"company_name": "Y", "email": f"y+{_u()}@y.test", "password": "short"})
    assert r.status_code == 400


def test_master_companies_overview(monkeypatch):
    name = "Beta Homes " + _u()
    r, email = _signup(monkeypatch, name=name)
    comps = client.get("/api/companies").json()["companies"]
    beta = [c for c in comps if c["name"] == name]
    assert beta and beta[0]["owner"] == email and beta[0]["user_count"] == 1


# ------------------------------------------------------------------ invites

def test_invite_and_accept(monkeypatch):
    bid = _signup(monkeypatch)[0].json()["brand_id"]
    invitee = f"agent+{_u()}@test.co"
    inv = client.post(f"/api/brands/{bid}/invites", json={"email": invitee, "role": "client"})
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]
    acc = client.post("/api/invites/accept", json={"token": token, "password": "anothersecret1"})
    assert acc.status_code == 200 and acc.json()["brand_id"] == bid
    lr = client.post("/api/auth/login", json={"email": invitee, "password": "anothersecret1"})
    assert lr.status_code == 200 and lr.json()["brand_id"] == bid and lr.json()["role"] == "client"


def test_invite_token_cannot_be_reused(monkeypatch):
    bid = _signup(monkeypatch)[0].json()["brand_id"]
    token = client.post(f"/api/brands/{bid}/invites", json={"email": f"a+{_u()}@test.co", "role": "client"}).json()["token"]
    assert client.post("/api/invites/accept", json={"token": token, "password": "anothersecret1"}).status_code == 200
    again = client.post("/api/invites/accept", json={"token": token, "password": "anothersecret1"})
    assert again.status_code == 400


# ------------------------------------------------------------- password reset

def test_password_reset_flow(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_TOKENS", "true")
    _, email = _signup(monkeypatch, pw="firstsecret1")
    fr = client.post("/api/auth/forgot", json={"email": email})
    assert fr.status_code == 200 and fr.json().get("reset_token")
    tok = fr.json()["reset_token"]
    rr = client.post("/api/auth/reset", json={"token": tok, "password": "brandnewsecret1"})
    assert rr.status_code == 200
    assert client.post("/api/auth/login", json={"email": email, "password": "firstsecret1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "brandnewsecret1"}).status_code == 200


def test_forgot_unknown_email_is_quiet(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_TOKENS", "true")
    r = client.post("/api/auth/forgot", json={"email": f"nobody+{_u()}@nowhere.test"})
    assert r.status_code == 200 and "reset_token" not in r.json()


# ------------------------------------------------------------- isolation

def test_owner_cannot_manage_another_company(monkeypatch):
    a = _signup(monkeypatch)[0].json()
    b = _signup(monkeypatch)[0].json()
    # act as company A's owner (no master bypass)
    monkeypatch.setenv("DIRECT_ACCESS", "")
    hdr = {"Authorization": "Bearer " + a["token"]}
    own = client.post(f"/api/brands/{a['brand_id']}/invites", json={"email": f"t+{_u()}@test.co"}, headers=hdr)
    assert own.status_code == 200, own.text
    other = client.post(f"/api/brands/{b['brand_id']}/invites", json={"email": f"x+{_u()}@test.co"}, headers=hdr)
    assert other.status_code == 403

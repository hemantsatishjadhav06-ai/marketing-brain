"""Coverage for self-serve multi-company onboarding.

Exercises the real DB layer against a temp SQLite file: company signup (and its
gate), user invites + accept, password reset, the master companies overview, and
cross-company isolation (an owner cannot manage another company).
"""
from __future__ import annotations

import os
import tempfile

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


def _signup(monkeypatch, name="Acme Realty", email="owner@acme.test", pw="supersecret1"):
    monkeypatch.setenv("SIGNUPS_OPEN", "true")
    return client.post("/api/signup", json={"company_name": name, "email": email,
                                            "password": pw, "website": "https://acme.test"})


# ------------------------------------------------------------------ signup

def test_signup_closed_by_default(monkeypatch):
    monkeypatch.setenv("SIGNUPS_OPEN", "false")
    r = client.post("/api/signup", json={"company_name": "X", "email": "x@x.test", "password": "supersecret1"})
    assert r.status_code == 403


def test_signup_creates_company_and_owner(monkeypatch):
    r = _signup(monkeypatch)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["role"] == "owner" and d["brand_id"] and d["token"]
    # owner can log in
    lr = client.post("/api/auth/login", json={"email": "owner@acme.test", "password": "supersecret1"})
    assert lr.status_code == 200 and lr.json()["role"] == "owner"


def test_signup_rejects_short_password(monkeypatch):
    monkeypatch.setenv("SIGNUPS_OPEN", "true")
    r = client.post("/api/signup", json={"company_name": "Y", "email": "y@y.test", "password": "short"})
    assert r.status_code == 400


def test_master_companies_overview(monkeypatch):
    _signup(monkeypatch, name="Beta Homes", email="own@beta.test")
    comps = client.get("/api/companies").json()["companies"]
    beta = [c for c in comps if c["name"] == "Beta Homes"]
    assert beta and beta[0]["owner"] == "own@beta.test" and beta[0]["user_count"] == 1


# ------------------------------------------------------------------ invites

def test_invite_and_accept(monkeypatch):
    bid = _signup(monkeypatch, name="Gamma Estates", email="own@gamma.test").json()["brand_id"]
    inv = client.post(f"/api/brands/{bid}/invites", json={"email": "agent@gamma.test", "role": "client"})
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]
    acc = client.post("/api/invites/accept", json={"token": token, "password": "anothersecret1"})
    assert acc.status_code == 200 and acc.json()["brand_id"] == bid
    # invited user can now log in, scoped to the company
    lr = client.post("/api/auth/login", json={"email": "agent@gamma.test", "password": "anothersecret1"})
    assert lr.status_code == 200 and lr.json()["brand_id"] == bid and lr.json()["role"] == "client"


def test_invite_token_cannot_be_reused(monkeypatch):
    bid = _signup(monkeypatch, name="Delta Devs", email="own@delta.test").json()["brand_id"]
    token = client.post(f"/api/brands/{bid}/invites", json={"email": "a@delta.test", "role": "client"}).json()["token"]
    assert client.post("/api/invites/accept", json={"token": token, "password": "anothersecret1"}).status_code == 200
    again = client.post("/api/invites/accept", json={"token": token, "password": "anothersecret1"})
    assert again.status_code == 400


# ------------------------------------------------------------- password reset

def test_password_reset_flow(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_TOKENS", "true")
    _signup(monkeypatch, name="Epsilon", email="own@epsilon.test", pw="firstsecret1")
    fr = client.post("/api/auth/forgot", json={"email": "own@epsilon.test"})
    assert fr.status_code == 200 and fr.json().get("reset_token")
    tok = fr.json()["reset_token"]
    rr = client.post("/api/auth/reset", json={"token": tok, "password": "brandnewsecret1"})
    assert rr.status_code == 200
    # old password fails, new one works
    assert client.post("/api/auth/login", json={"email": "own@epsilon.test", "password": "firstsecret1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "own@epsilon.test", "password": "brandnewsecret1"}).status_code == 200


def test_forgot_unknown_email_is_quiet(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_TOKENS", "true")
    r = client.post("/api/auth/forgot", json={"email": "nobody@nowhere.test"})
    assert r.status_code == 200 and "reset_token" not in r.json()


# ------------------------------------------------------------- isolation

def test_owner_cannot_manage_another_company(monkeypatch):
    # two companies
    a = _signup(monkeypatch, name="OrgA", email="own@orga.test").json()
    b = _signup(monkeypatch, name="OrgB", email="own@orgb.test").json()
    # now act as OrgA's owner (no master bypass)
    monkeypatch.setenv("DIRECT_ACCESS", "")
    hdr = {"Authorization": "Bearer " + a["token"]}
    # can invite to own company
    own = client.post(f"/api/brands/{a['brand_id']}/invites", json={"email": "t@orga.test"}, headers=hdr)
    assert own.status_code == 200, own.text
    # cannot invite to the other company
    other = client.post(f"/api/brands/{b['brand_id']}/invites", json={"email": "x@orgb.test"}, headers=hdr)
    assert other.status_code == 403

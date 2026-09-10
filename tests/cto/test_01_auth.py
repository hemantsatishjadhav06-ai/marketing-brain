"""01 AUTH — credentials, tokens, throttling, reset flow. Auth is enforced (no DIRECT_ACCESS)."""
from __future__ import annotations

import base64
import json
import time

import pytest

from app.core import auth, database as db
from app.services import onboarding

from .conftest import client, hdr, make_admin, signup_org, u


# ------------------------------------------------------------------ login

def AUTH_invalid_password_rejected(org_a):
    r = client.post("/api/auth/login", json={"email": org_a["email"], "password": "definitely-wrong"})
    assert r.status_code == 401
    assert "token" not in r.json()


def AUTH_unknown_user_rejected():
    r = client.post("/api/auth/login", json={"email": f"ghost+{u()}@cto.test", "password": "whatever1"})
    assert r.status_code == 401


def AUTH_unknown_and_wrong_password_are_indistinguishable(org_a):
    a = client.post("/api/auth/login", json={"email": org_a["email"], "password": "wrong"})
    b = client.post("/api/auth/login", json={"email": f"ghost+{u()}@cto.test", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json(), "login error text leaks whether the account exists"


def AUTH_login_missing_fields_422():
    assert client.post("/api/auth/login", json={"email": "x@y.z"}).status_code == 422
    assert client.post("/api/auth/login", json={}).status_code == 422


def AUTH_valid_login_returns_scoped_token(org_a):
    r = client.post("/api/auth/login", json={"email": org_a["email"], "password": org_a["password"]})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers=hdr(r.json()["token"])).json()
    assert me["role"] == "owner" and me["brand_id"] == org_a["brand_id"]


# ------------------------------------------------------------------ signup validation

def AUTH_duplicate_email_signup_rejected(org_a):
    with pytest.raises(ValueError, match="already exists"):
        onboarding.signup("Dup Co", "", org_a["email"], "supersecret1")


def AUTH_duplicate_email_case_insensitive(org_a):
    with pytest.raises(ValueError, match="already exists"):
        onboarding.signup("Dup Co", "", org_a["email"].upper(), "supersecret1")


def AUTH_weak_password_signup_rejected():
    with pytest.raises(ValueError, match="8 characters"):
        onboarding.signup("Weak Co", "", f"w+{u()}@cto.test", "short")


def AUTH_missing_password_signup_rejected():
    with pytest.raises(ValueError):
        onboarding.signup("NoPw Co", "", f"n+{u()}@cto.test", "")


@pytest.mark.defect
def AUTH_invalid_email_format_rejected():
    """DEFECT: onboarding.signup accepts any string as an email (no format check)."""
    with pytest.raises(ValueError):
        onboarding.signup("Bad Email Co", "", "not-an-email-" + u(), "supersecret1")


def AUTH_signup_endpoint_closed_without_flag():
    r = client.post("/api/signup", json={"company_name": "X", "email": f"x+{u()}@cto.test", "password": "supersecret1"})
    assert r.status_code == 403


@pytest.mark.defect
def AUTH_admin_user_create_enforces_password_policy(admin, org_a):
    """DEFECT: POST /api/users has no password-length check (signup requires >= 8)."""
    r = client.post("/api/users", headers=hdr(admin["token"]),
                    json={"email": f"weak+{u()}@cto.test", "password": "x", "role": "client",
                          "brand_id": org_a["brand_id"]})
    assert r.status_code == 400, f"1-char password accepted for a new user: {r.text}"


def AUTH_admin_user_create_duplicate_email_400(admin, org_a):
    r = client.post("/api/users", headers=hdr(admin["token"]),
                    json={"email": org_a["email"], "password": "longenough1", "role": "client",
                          "brand_id": org_a["brand_id"]})
    assert r.status_code == 400


# ------------------------------------------------------------------ tokens

def AUTH_no_token_401():
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/brands").status_code == 401


@pytest.mark.parametrize("bad", ["", "Bearer", "Bearer ", "Bearer garbage", "Basic abc", "Bearer a.b.c.d"])
def AUTH_malformed_token_401(bad):
    r = client.get("/api/auth/me", headers={"Authorization": bad})
    assert r.status_code == 401


def AUTH_tampered_signature_401(org_a):
    tok = org_a["token"]
    raw, sig = tok.rsplit(".", 1)
    flipped = ("0" if sig[-1] != "0" else "1")
    tampered = raw + "." + sig[:-1] + flipped
    assert client.get("/api/auth/me", headers=hdr(tampered)).status_code == 401


def AUTH_tampered_payload_401(org_a, admin):
    """Re-encode the payload with role=admin but keep the original signature."""
    raw, sig = org_a["token"].rsplit(".", 1)
    payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    payload["role"] = "admin"
    forged_raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    r = client.get("/api/auth/me", headers=hdr(forged_raw + "." + sig))
    assert r.status_code == 401


def AUTH_expired_token_401(org_a):
    payload = {"uid": org_a["user_id"], "role": "owner", "brand_id": org_a["brand_id"], "exp": time.time() - 5}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    expired = raw + "." + auth._sign(raw)
    assert client.get("/api/auth/me", headers=hdr(expired)).status_code == 401


def AUTH_token_signed_with_other_secret_401(org_a):
    import hashlib, hmac
    raw = org_a["token"].rsplit(".", 1)[0]
    foreign_sig = hmac.new(b"some-other-secret", raw.encode(), hashlib.sha256).hexdigest()[:40]
    assert client.get("/api/auth/me", headers=hdr(raw + "." + foreign_sig)).status_code == 401


@pytest.mark.defect
def AUTH_token_of_deleted_user_is_revoked(admin, org_a):
    """DEFECT: verify_token never consults the users table — a deleted user's token
    keeps working for the remaining TOKEN_TTL (30 days)."""
    tok = org_a["token"]
    assert client.get("/api/auth/me", headers=hdr(tok)).status_code == 200
    assert client.delete(f"/api/users/{org_a['user_id']}", headers=hdr(admin["token"])).status_code == 200
    assert db.get_user_by_email(org_a["email"]) is None
    r = client.get(f"/api/brands/{org_a['brand_id']}", headers=hdr(tok))
    assert r.status_code == 401, f"deleted user still authenticated: {r.status_code}"


@pytest.mark.defect
def AUTH_password_reset_invalidates_existing_sessions(org_a):
    """DEFECT: a reset (the 'my account was stolen' path) leaves old tokens valid."""
    old = org_a["token"]
    onboarding.request_reset(org_a["email"])
    rows = [r for r in db.list_docs("password_resets", "") if (r.get("payload") or {}).get("email") == org_a["email"]]
    onboarding.reset_password(rows[0]["token"], "afterreset99")
    assert client.get("/api/auth/me", headers=hdr(old)).status_code == 401


# ------------------------------------------------------------------ rate limiting

def AUTH_login_rate_limited_after_10_from_one_ip():
    ip = "203.0.113.77"
    codes = [client.post("/api/auth/login", json={"email": "no@no.test", "password": "x"},
                         headers={"X-Forwarded-For": ip}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def AUTH_rate_limit_also_blocks_correct_password(org_a):
    ip = "203.0.113.250"
    for _ in range(10):
        client.post("/api/auth/login", json={"email": org_a["email"], "password": "bad"},
                    headers={"X-Forwarded-For": ip})
    r = client.post("/api/auth/login", json={"email": org_a["email"], "password": org_a["password"]},
                    headers={"X-Forwarded-For": ip})
    assert r.status_code == 429, "throttle must not have a correct-password side channel"


@pytest.mark.defect
def AUTH_login_rate_limit_not_bypassable_by_xff_spoofing():
    """DEFECT: guard.client_ip trusts the FIRST X-Forwarded-For hop, which the
    attacker controls. Rotating XFF per request never trips the limiter."""
    codes = []
    for n in range(1, 31):
        codes.append(client.post("/api/auth/login", json={"email": "no@no.test", "password": "x"},
                                 headers={"X-Forwarded-For": f"198.51.100.{n}, 10.0.0.1"}).status_code)
    assert 429 in codes, f"30 attempts from one socket with rotating XFF: {codes}"


def AUTH_login_without_xff_uses_socket_ip():
    codes = [client.post("/api/auth/login", json={"email": "no@no.test", "password": "x"}).status_code
             for _ in range(11)]
    assert codes[10] == 429


# ------------------------------------------------------------------ forgot / reset

def AUTH_forgot_never_leaks_existence(org_a):
    known = client.post("/api/auth/forgot", json={"email": org_a["email"]})
    unknown = client.post("/api/auth/forgot", json={"email": f"nobody+{u()}@cto.test"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"ok": True}  # AUTH_DEV_TOKENS is unset: no token leaks


def AUTH_reset_invalid_token_400():
    r = client.post("/api/auth/reset", json={"token": "nope" + u(), "password": "brandnew123"})
    assert r.status_code == 400


def AUTH_reset_token_single_use(org_a):
    client.post("/api/auth/forgot", json={"email": org_a["email"]})
    rows = [r for r in db.list_docs("password_resets", "") if (r.get("payload") or {}).get("email") == org_a["email"]]
    assert rows, "reset row not written"
    tok = rows[0]["token"]
    assert client.post("/api/auth/reset", json={"token": tok, "password": "brandnew123"}).status_code == 200
    again = client.post("/api/auth/reset", json={"token": tok, "password": "another123"})
    assert again.status_code == 400
    assert client.post("/api/auth/login", json={"email": org_a["email"], "password": "brandnew123"},
                       headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": org_a["email"], "password": "another123"},
                       headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 401


def AUTH_reset_expired_token_400(org_a):
    client.post("/api/auth/forgot", json={"email": org_a["email"]})
    rows = [r for r in db.list_docs("password_resets", "") if (r.get("payload") or {}).get("email") == org_a["email"]]
    with db._lock, db._conn() as c:
        c.execute("UPDATE password_resets SET created_at=? WHERE id=?", (time.time() - 7200, rows[0]["id"]))
    r = client.post("/api/auth/reset", json={"token": rows[0]["token"], "password": "brandnew123"})
    assert r.status_code == 400 and "expired" in r.text


def AUTH_reset_weak_password_400(org_a):
    client.post("/api/auth/forgot", json={"email": org_a["email"]})
    rows = [r for r in db.list_docs("password_resets", "") if (r.get("payload") or {}).get("email") == org_a["email"]]
    r = client.post("/api/auth/reset", json={"token": rows[0]["token"], "password": "short"})
    assert r.status_code == 400

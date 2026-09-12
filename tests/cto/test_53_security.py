"""53 SECURITY — injection storage, SSRF, path traversal, upload handling, limiter spoofing."""
from __future__ import annotations

import os

import pytest

from app.core import database as db
from app.services import memory as mem, workspace as ws

from .conftest import client, hdr, png_bytes, seed_idea, signup_org, u

SQLI = "Acme'); DROP TABLE brands;--"
XSS = "<script>alert(1)</script>"


@pytest.fixture
def org():
    return signup_org("Acme Widgets")


def _table_exists(name):
    with db._conn() as c:
        return c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


# ------------------------------------------------------------ SQL injection

def SEC_sqli_brand_name_stored_literally(admin):
    r = client.post("/api/brands", json={"name": SQLI, "website": "https://sq.invalid"}, headers=hdr(admin["token"]))
    assert r.status_code == 200 and r.json()["name"] == SQLI
    assert _table_exists("brands") and db.get_brand(r.json()["id"])["name"] == SQLI
    assert "sqlite" not in r.text.lower() and "syntax" not in r.text.lower()


def SEC_sqli_login_email_rejected_quietly(org):
    for payload in ("' OR '1'='1", "' OR 1=1 --", f"{org['email']}' --", "admin'/*"):
        r = client.post("/api/auth/login", json={"email": payload, "password": "x"}, headers={"X-Forwarded-For": "203.0.113.50"})
        assert r.status_code == 401 and "sqlite" not in r.text.lower()
    assert _table_exists("users")


def SEC_sqli_idea_state_no_error_leak(org):
    iid = seed_idea(org["brand_id"])
    state = "'; DROP TABLE ideas;--"
    r = client.post(f"/api/brands/{org['brand_id']}/ideas/{iid}/state", json={"state": state}, headers=hdr(org["token"]))
    assert r.status_code in (200, 400) and _table_exists("ideas")
    assert "sqlite" not in r.text.lower() and "syntax" not in r.text.lower()
    stored = db.get_doc("ideas", iid)["state"]
    assert stored in (state, "proposed")  # either stored literally (parameterised) or refused by the vocabulary check


def SEC_sqli_in_query_filters_is_parameterised(org):
    seed_idea(org["brand_id"])
    assert db.list_docs("ideas", org["brand_id"], channel="x' OR '1'='1") == []
    assert db.get_doc_by("users", email="x' OR '1'='1") is None
    assert client.get(f"/api/brands/{org['brand_id']}/inbox?status=open' OR '1'='1", headers=hdr(org["token"])).json()["conversations"] == []


# ------------------------------------------------------------ XSS storage (rendering is frontend scope)

def SEC_xss_brand_name_stored_raw(admin):
    r = client.post("/api/brands", json={"name": XSS, "website": "https://x.invalid"}, headers=hdr(admin["token"]))
    assert r.status_code == 200 and r.json()["name"] == XSS
    assert r.headers["content-type"].startswith("application/json")
    # rendered later by web/js/app.js via innerHTML (brand pickers, dashboard, approvals) — see report


def SEC_xss_memory_note_stored_raw(org):
    r = client.post(f"/api/brands/{org['brand_id']}/memory", json={"content": XSS, "kind": "rule"}, headers=hdr(org["token"]))
    assert r.status_code == 200
    assert mem.recall(org["brand_id"])[0]["content"] == XSS


def SEC_xss_inbox_message_stored_raw(org):
    r = client.post(f"/api/brands/{org['brand_id']}/inbox/inbound",
                    json={"channel": "whatsapp", "contact_ref": "+1", "text": XSS, "contact_name": XSS}, headers=hdr(org["token"]))
    assert r.status_code == 200
    thread = client.get(f"/api/brands/{org['brand_id']}/inbox/{r.json()['conversation_id']}", headers=hdr(org["token"])).json()
    assert thread["messages"][0]["text"] == XSS


# ------------------------------------------------------------ SSRF

@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8000/", "http://[::1]/", "http://0.0.0.0/", "file:///etc/passwd"])
def SEC_ssrf_competitor_url_never_fetched(org, url):
    """The _no_network fixture turns any httpx.Client() into an AssertionError, so a
    fetch of the internal URL would surface as a 500/exception here."""
    r = client.post(f"/api/brands/{org['brand_id']}/competitors", json={"url": url}, headers=hdr(org["token"]))
    assert r.status_code in (200, 400, 422)
    if r.status_code == 200:
        assert r.json()["payload"].get("_scrape_ok") is False


@pytest.mark.defect
@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8000/"])
def SEC_ssrf_internal_url_rejected_with_4xx(org, url):
    """DEFECT (app/routes/competitors.py add_competitor): guard.url_is_safe blocks the
    fetch, but the request still succeeds — an internal URL is stored as a competitor and
    a battlecard is hallucinated for it. Should be a 400 before any work happens."""
    r = client.post(f"/api/brands/{org['brand_id']}/competitors", json={"url": url}, headers=hdr(org["token"]))
    assert r.status_code == 400, f"internal URL accepted: {r.status_code}, stored={db.list_docs('competitors', org['brand_id'])[:1]}"


def SEC_ssrf_brand_website_scrape_blocked(admin):
    r = client.post("/api/brands", json={"name": "Loop " + u(), "website": "http://127.0.0.1:8000/"}, headers=hdr(admin["token"]))
    bid = r.json()["id"]
    r = client.post(f"/api/brands/{bid}/scrape", headers=hdr(admin["token"]))
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["errors"]


# ------------------------------------------------------------ path traversal

@pytest.mark.parametrize("path", [
    "/workspaces/../../etc/passwd", "/workspaces/..%2F..%2Fetc%2Fpasswd", "/workspaces/%2e%2e/%2e%2e/etc/passwd",
    "/workspaces/x/../../../../etc/passwd", "/workspaces//etc/passwd", "/workspaces/%2fetc%2fpasswd",
])
def SEC_path_traversal_workspaces_blocked(org, path):
    r = client.get(path, headers=hdr(org["token"]))
    assert r.status_code == 404, f"{path} -> {r.status_code}"
    assert "root:" not in r.text


def SEC_logo_filename_traversal_ignored(org):
    bid = org["brand_id"]
    r = client.post(f"/api/brands/{bid}/logo", files={"file": ("../../x.png", png_bytes(), "image/png")}, headers=hdr(org["token"]))
    assert r.status_code == 200 and r.json()["logo"] == "brand/logo.png"
    root = os.path.abspath(ws.WORKSPACES_ROOT)
    assert not os.path.exists(os.path.join(root, "..", "x.png")) and not os.path.exists(os.path.join(root, "x.png"))
    assert os.path.isfile(os.path.join(ws.brand_dir(org["brand"]["slug"]), "brand", "logo.png"))


def SEC_logo_rejects_disguised_non_image(org):
    r = client.post(f"/api/brands/{org['brand_id']}/logo", files={"file": ("evil.png", b"<html><script>1</script>", "image/png")}, headers=hdr(org["token"]))
    assert r.status_code == 400


def SEC_logo_rejects_oversize(org):
    r = client.post(f"/api/brands/{org['brand_id']}/logo", files={"file": ("big.png", b"\x89PNG" + b"0" * (5 * 1024 * 1024 + 1), "image/png")}, headers=hdr(org["token"]))
    assert r.status_code == 400


@pytest.mark.defect
def SEC_svg_logo_with_script_not_served_from_app_origin(org):
    """DEFECT (app/routes/pipeline.py upload_logo + app/main.py _workspace_router): SVG
    is accepted with no sanitisation and skips the image check; it is then served from
    the app origin as image/svg+xml — a stored XSS for any authenticated viewer who opens
    the asset URL (and the workspace router lets *every* tenant open it)."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.cookie)</script></svg>'
    r = client.post(f"/api/brands/{org['brand_id']}/logo", files={"file": ("logo.svg", svg, "image/svg+xml")}, headers=hdr(org["token"]))
    assert r.status_code == 400, "SVG containing <script> was accepted"
    served = client.get(f"/workspaces/{org['brand']['slug']}/brand/logo.svg", headers=hdr(org["token"]))
    assert not (served.status_code == 200 and b"<script" in served.content and "svg" in served.headers.get("content-type", ""))


# ------------------------------------------------------------ limiter spoofing (also in AUTH_)

@pytest.mark.defect
def SEC_login_limiter_xff_spoof(org):
    """DEFECT (app/core/guard.py client_ip): first XFF hop is attacker-chosen."""
    codes = [client.post("/api/auth/login", json={"email": org["email"], "password": "bad"},
                         headers={"X-Forwarded-For": f"10.9.{n // 250}.{n % 250 + 1}"}).status_code for n in range(25)]
    assert 429 in codes, "25 wrong passwords against one account from one socket, never throttled"


def SEC_per_account_limiter_blocks_credential_spray(org):
    """FIXED: the limiter used to key on IP only, so 10 attempts from each of N IPs
    against ONE account all went through (credential stuffing/spray). A per-account
    throttle now trips regardless of how many source addresses are used."""
    codes = []
    for ip in range(3):
        for _ in range(10):
            codes.append(client.post("/api/auth/login", json={"email": org["email"], "password": "bad"},
                                     headers={"X-Forwarded-For": f"203.0.113.{100 + ip}"}).status_code)
    assert 429 in codes and codes.count(401) < 30, f"spray across 3 IPs never throttled: {codes}"


def SEC_cors_allows_any_origin_with_bearer_scheme():
    r = client.options("/api/brands", headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "GET",
                                               "Access-Control-Request-Headers": "authorization"})
    assert r.headers.get("access-control-allow-origin") == "*"
    # Tokens are bearer headers, not cookies, so '*' cannot ride an ambient session — noted, not a defect.

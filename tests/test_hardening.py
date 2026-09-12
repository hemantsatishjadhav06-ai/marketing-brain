"""Coverage for the audit hardening: SSRF URL guard, rate limiter, generation
kill-switch + per-brand daily cap, login throttling, and the developer-field
sanitisation on /api/projects."""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "hard_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.core import database as db, guard  # noqa: E402
from app.services import projects  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------- SSRF guard

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data",
    "http://10.1.2.3", "http://192.168.0.1", "http://[::1]/", "ftp://8.8.8.8",
    "file:///etc/passwd", "http://0.0.0.0",
])
def test_url_guard_blocks_unsafe(url):
    ok, _ = guard.url_is_safe(url)
    assert ok is False


def test_url_guard_allows_public_ip():
    ok, _ = guard.url_is_safe("https://8.8.8.8/")
    assert ok is True


# ---------------------------------------------------------------- rate limiter

def test_rate_limiter_window():
    k = "unit-test-key"
    guard._hits.pop(k, None)
    assert guard.rate_ok(k, 2, 100) is True
    assert guard.rate_ok(k, 2, 100) is True
    assert guard.rate_ok(k, 2, 100) is False


# ---------------------------------------------------- generation kill + budget

def test_generation_kill_switch(monkeypatch):
    monkeypatch.setenv("GENERATION_DISABLED", "true")
    assert guard.generation_enabled() is False
    ok, msg = guard.check_generation("brand-x")
    assert ok is False and "disabled" in msg.lower()


def test_generation_daily_cap(monkeypatch):
    monkeypatch.delenv("GENERATION_DISABLED", raising=False)
    monkeypatch.setenv("GEN_DAILY_CAP", "2")
    bid = "cap-brand-" + os.urandom(3).hex()
    assert guard.check_generation(bid)[0] is True   # 1
    assert guard.check_generation(bid)[0] is True   # 2
    assert guard.check_generation(bid)[0] is False  # 3 > cap


# ---------------------------------------------------------------- login throttle

def test_login_is_rate_limited_in_prod_mode(monkeypatch):
    monkeypatch.setenv("DIRECT_ACCESS", "")   # simulate a public/prod instance
    guard._hits.pop("login:203.0.113.7", None)
    hdr = {"X-Forwarded-For": "203.0.113.7"}
    codes = [client.post("/api/auth/login", json={"email": "no@no.test", "password": "x"}, headers=hdr).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10   # first 10 attempts hit the credential check
    assert codes[10] == 429           # 11th is throttled
    guard._hits.pop("login:203.0.113.7", None)


# ------------------------------------------------------- developer-field leak

def test_projects_directory_has_no_placeholder_developer():
    d = projects.directory()
    bad = ("reputed", "tier-1", "tier 1", "grade-a", "grade a", "leading", "renowned")
    for p in d["projects"]:
        dev = (p.get("developer") or "").lower()
        assert not dev.startswith(bad), f"placeholder developer leaked: {p.get('developer')!r}"

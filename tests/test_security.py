"""Regression tests for the security defects the audit surfaced.

Each test reproduces the original exploit, so a regression fails loudly rather
than silently reopening the hole.
"""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "sec_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.core import database as db  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _open_access(monkeypatch):
    monkeypatch.setenv("DIRECT_ACCESS", "true")


@pytest.fixture
def two_brands():
    a = client.post("/api/brands", json={"name": "Alpha Co", "website": "https://a.example"}).json()["id"]
    b = client.post("/api/brands", json={"name": "Beta Co", "website": "https://b.example"}).json()["id"]
    return a, b


# --------------------------------------------------- cross-brand data access

def test_cannot_approve_another_brands_creative(two_brands):
    a, b = two_brands
    cid = db.insert_doc("creatives", b, {"title": "Beta secret"}, channel="instagram", format="post")
    r = client.post(f"/api/brands/{a}/creatives/{cid}/approval", json={"state": "approved", "comment": ""})
    assert r.status_code == 404, "one brand approved another brand's creative"


def test_cannot_revise_another_brands_creative(two_brands):
    a, b = two_brands
    cid = db.insert_doc("creatives", b, {"title": "Beta secret"}, channel="instagram", format="post")
    r = client.post(f"/api/brands/{a}/creatives/{cid}/revise", json={"instruction": "change it"})
    assert r.status_code == 404


def test_cannot_publish_another_brands_creative(two_brands):
    a, b = two_brands
    cid = db.insert_doc("creatives", b, {"title": "Beta secret"}, channel="instagram", format="post")
    r = client.post(f"/api/brands/{a}/publish", json={"creative_id": cid})
    assert r.status_code == 404


def test_own_creative_is_still_reachable(two_brands):
    a, _ = two_brands
    cid = db.insert_doc("creatives", a, {"title": "Alpha's own"}, channel="instagram", format="post")
    r = client.post(f"/api/brands/{a}/creatives/{cid}/approval", json={"state": "approved", "comment": ""})
    assert r.status_code == 200


# --------------------------------------------------------- path containment

@pytest.mark.parametrize("relpath", [
    "../../../../tmp/pwned.txt",
    "../escape.txt",
    "channel/../../../../tmp/pwned2.txt",
])
def test_workspace_writes_cannot_escape_the_root(relpath, tmp_path, monkeypatch):
    from app.services import workspace as ws
    # WORKSPACES_ROOT is read at import, so patch the attribute, not the env var
    monkeypatch.setattr(ws, "WORKSPACES_ROOT", str(tmp_path))
    with pytest.raises(ValueError):
        ws.write_text("brandx", relpath, "owned")


def test_legitimate_workspace_write_still_works(tmp_path, monkeypatch):
    from app.services import workspace as ws
    monkeypatch.setattr(ws, "WORKSPACES_ROOT", str(tmp_path))
    path = ws.write_text("brandx", "blog/creatives/post.md", "hello")
    assert os.path.isfile(path)
    assert str(tmp_path) in os.path.realpath(path)


def test_safe_path_rejects_absolute_paths(tmp_path, monkeypatch):
    from app.services import workspace as ws
    monkeypatch.setattr(ws, "WORKSPACES_ROOT", str(tmp_path))
    with pytest.raises(ValueError):
        ws.safe_path("brandx", "/etc/passwd")


# -------------------------------------------------------- deployment config

def test_render_yaml_never_ships_the_auth_bypass():
    import pathlib
    cfg = pathlib.Path("render.yaml").read_text()
    assert 'key: DIRECT_ACCESS' in cfg
    bypass_block = cfg.split("key: DIRECT_ACCESS", 1)[1][:80]
    assert '"true"' not in bypass_block, "render.yaml would deploy with authentication disabled"


def test_render_yaml_sets_a_signing_key():
    import pathlib
    cfg = pathlib.Path("render.yaml").read_text()
    assert "SECRET_KEY" in cfg, "without SECRET_KEY the app signs tokens with a hard-coded default"


def test_render_yaml_provisions_an_admin():
    """Turning the bypass off without an admin locks everyone out."""
    import pathlib
    cfg = pathlib.Path("render.yaml").read_text()
    assert "ADMIN_EMAIL" in cfg and "ADMIN_PASSWORD" in cfg


# ------------------------------------------------- Railway deployment config

def test_railway_config_declares_a_start_command_and_healthcheck():
    """Without these Railway builds an image it cannot start or verify."""
    import json, pathlib
    cfg = json.loads(pathlib.Path("railway.json").read_text())
    start = cfg["deploy"]["startCommand"]
    assert "app.main:app" in start
    assert "$PORT" in start or "${PORT" in start, "must bind the port Railway assigns"
    assert cfg["deploy"]["healthcheckPath"] == "/api/health"


def test_the_auth_bypass_cannot_boot_on_a_public_host(monkeypatch):
    """The render.yaml test only guarded Render; this guards every host."""
    from app.routes import _shared
    monkeypatch.setenv("DIRECT_ACCESS", "true")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "brain.up.railway.app")
    with pytest.raises(RuntimeError, match="unauthenticated admin"):
        _shared._assert_auth_is_enabled()


def test_the_auth_bypass_is_still_allowed_locally(monkeypatch):
    from app.routes import _shared
    monkeypatch.setenv("DIRECT_ACCESS", "true")
    for var in ("RAILWAY_PUBLIC_DOMAIN", "RENDER_EXTERNAL_HOSTNAME", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    _shared._assert_auth_is_enabled()  # must not raise


def test_a_public_host_with_auth_on_boots_fine(monkeypatch):
    from app.routes import _shared
    monkeypatch.setenv("DIRECT_ACCESS", "false")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "brain.up.railway.app")
    _shared._assert_auth_is_enabled()

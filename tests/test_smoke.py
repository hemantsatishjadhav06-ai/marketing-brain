"""Smoke tests for the rewritten Marketing Brain package."""
import os

os.environ.setdefault("DB_PATH", "data/test_mb.db")
os.environ.setdefault("WORKSPACES_ROOT", "data/test_ws")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_openapi_has_routes():
    paths = client.get("/openapi.json").json()["paths"]
    assert len(paths) >= 40


def test_login_rejects_bad_credentials():
    r = client.post("/api/auth/login", json={"email": "a@b.c", "password": "nope"})
    assert r.status_code == 401


def test_protected_route_requires_auth():
    r = client.get("/api/brands")
    assert r.status_code in (401, 403)

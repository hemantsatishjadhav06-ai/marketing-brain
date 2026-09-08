"""Regression: GET /api/playbook must return the catalog, not 500.

A route handler named `playbook` in growth.py shadowed the imported `playbook`
service module, so `playbook.catalog()` raised
`AttributeError: 'function' object has no attribute 'catalog'` and the public
endpoint 500'd in production. This locks the behaviour in.
"""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "pbcat_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_playbook_catalog_is_public_and_shaped():
    r = client.get("/api/playbook")  # public endpoint, no auth
    assert r.status_code == 200, r.text
    body = r.json()
    assert "systems" in body and isinstance(body["systems"], list) and body["systems"]

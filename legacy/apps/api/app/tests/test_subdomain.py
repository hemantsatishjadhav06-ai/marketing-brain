"""Subdomain middleware reserved-list."""
from __future__ import annotations

from app.core.subdomain import RESERVED


def test_reserved_includes_api_and_www():
    for w in ("api", "www", "app", "admin"):
        assert w in RESERVED

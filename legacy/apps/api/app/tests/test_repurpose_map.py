"""Repurpose map covers the channels we ship Phase 2."""
from __future__ import annotations

from app.agents.repurpose import REPURPOSE_MAP, _build_payload


class _Item:
    def __init__(self, content_type, payload=None, angle=""):
        self.content_type = content_type
        self.payload = payload or {}
        self.angle = angle


def test_blog_fans_out_to_three():
    assert len(REPURPOSE_MAP["blog"]) >= 3
    assert ("x", "post") in REPURPOSE_MAP["blog"]


def test_carousel_to_static_post():
    targets = REPURPOSE_MAP["carousel"]
    assert ("instagram", "static_post") in targets


def test_build_payload_for_blog_target_has_sections():
    parent = _Item("static_post", {"headline": "Foo", "caption": "Bar"}, angle="Foo")
    p = _build_payload(parent, "blog", "blog")
    assert "sections" in p and isinstance(p["sections"], list)


def test_build_payload_for_email_target_has_blocks():
    parent = _Item("static_post", {"caption": "Foo", "cta": "Shop"}, angle="Foo")
    p = _build_payload(parent, "email", "email")
    assert "blocks" in p and any(b.get("type") == "cta" for b in p["blocks"])

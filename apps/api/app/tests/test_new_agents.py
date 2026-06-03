"""The 5 spec-mandated agents shipped in v0.6 — fallbacks respect limits."""
from __future__ import annotations

from app.agents.community import _fallback as community_fb
from app.agents.pinterest import _fallback as pin_fb
from app.agents.seo_geo import _fallback as seo_fb
from app.agents.whatsapp import BODY_LIMIT, BUTTON_LIMIT, FOOTER_LIMIT, HEADER_LIMIT, _fallback as wa_fb
from app.agents.x_post import X_LIMIT, _fallback as x_fb


class _Brand:
    sport = "tennis"
    name = "Test Brand"


def test_community_fallback_has_answer_and_tldr():
    out = community_fb(_Brand(), "string tension")
    assert len(out["answer"].split()) >= 50
    assert out["tldr"]
    assert "platform_hint" in out


def test_x_post_under_limit():
    out = x_fb(_Brand(), "footwork")
    assert len(out["text"]) <= X_LIMIT
    assert isinstance(out.get("hashtags"), list)


def test_pinterest_title_under_100():
    out = pin_fb(_Brand(), "grip size")
    assert len(out["title"]) <= 100
    assert len(out["description"]) <= 500


def test_seo_geo_has_schema_jsonld_and_geo_block():
    out = seo_fb(_Brand(), "string tension", None)
    assert out["schema_jsonld"]["@type"] == "Article"
    assert "geo_answer_block" in out
    assert out["geo_queries"]


def test_whatsapp_respects_all_limits():
    out = wa_fb(_Brand(), "weekly drop", None)
    assert len(out["body"]) <= BODY_LIMIT
    assert len(out["header"]["text"]) <= HEADER_LIMIT
    assert out["footer"] is None or len(out["footer"]) <= FOOTER_LIMIT
    for b in out["buttons"]:
        assert len(b["text"]) <= BUTTON_LIMIT

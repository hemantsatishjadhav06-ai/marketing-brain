"""A/B helper produces distinct variants without an LLM key."""
from __future__ import annotations

from app.agents._ab import (
    _swap_cta,
    make_b_variant_for_blog,
    make_b_variant_for_caption,
    make_b_variant_for_email,
)


def test_swap_cta_changes_action_to_curiosity_and_back():
    assert _swap_cta("Shop now").lower() != "shop now"
    assert "later" in _swap_cta("Tap to shop today.").lower() or "60-second" in _swap_cta("Tap to shop today.").lower()


def test_b_caption_changes_headline():
    a = {"headline": "Best string tension for control.", "caption": "Here's why.", "cta": "Shop now"}
    b = make_b_variant_for_caption(brand_sport="tennis", brand_voice="", angle="string tension", a_payload=a)
    assert b["headline"] != a["headline"]


def test_b_email_changes_subject():
    a = {"subject_line": "Why we love this grip.", "preheader": "60-second read.", "blocks": [{"type": "cta", "text": "Shop"}]}
    b = make_b_variant_for_email(brand_sport="tennis", brand_voice="", angle="grip", a_payload=a)
    assert b["subject_line"] != a["subject_line"]


def test_b_blog_changes_title():
    a = {"title": "How to choose grip size", "meta_description": "A 5-minute guide."}
    b = make_b_variant_for_blog(brand_sport="tennis", brand_voice="", angle="grip", a_payload=a)
    assert b["title"] != a["title"]

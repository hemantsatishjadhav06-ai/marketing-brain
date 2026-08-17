"""Offline coverage for the Neopolis end-to-end harness.

The harness itself makes live OpenRouter + fal.ai calls; here both are stubbed so
CI proves the wiring (agent team -> blueprint -> slides -> renders -> artefacts)
without a key and without spending anything.
"""
from __future__ import annotations

import json

import pytest

from app.ai import brain, engine
from scripts import e2e_neopolis as e2e

FAKE_JSON = {
    "core_idea": "Only 5 homes per floor",
    "post_caption": "Hook line\n3.5 & 4 BHK from Rs 2.7 Cr, Kokapet.",
    "hashtags": ["kokapet", "hyderabadrealestate"],
    "static_image_prompt": "Concept B. Deep navy field, champagne-gold headline...",
    "developer": "Reputed developer",
    "scenes": [],
    "caption": "Publish-ready carousel caption",
    "slides": [
        {"n": n, "headline": f"Slide {n}", "body": "one line", "visual_direction": "v", "design_notes": "d"}
        for n in range(1, 7)
    ],
    "title": "Kokapet Luxury Apartments: The Neopolis Case",
    "slug": "kokapet-luxury-apartments",
    "meta_description": "meta",
    "body_markdown": "## Heading\n" + ("word " * 400),
    "faq": [{"q": "q", "a": "a"}],
    "cta": "Book a site visit.",
    "image_prompt": "Hero image prompt",
}


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("FAL_KEY", "test")
    monkeypatch.setattr(engine, "_chat", lambda *a, **k: "agent prose")
    monkeypatch.setattr(engine, "_json_chat", lambda *a, **k: json.loads(json.dumps(FAKE_JSON)))
    monkeypatch.setattr(brain, "fal_image", lambda *a, **k: "https://fal.invalid/asset.png")
    monkeypatch.setattr(e2e, "download", lambda url, dest: (dest.write_bytes(b"\x89PNG"), dest)[1])
    return tmp_path


def test_preflight_reports_missing_keys(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("FAL_KEY", raising=False)
    problems = e2e.preflight(["post", "carousel", "blog"], want_images=True)
    assert len(problems) == 2
    assert any("OPENROUTER_API_KEY" in p for p in problems)
    assert any("FAL_KEY" in p for p in problems)


def test_preflight_clean_when_both_keys_present(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("FAL_KEY", "test")
    assert e2e.preflight(list(e2e.STAGES), want_images=True) == []


def test_blog_only_does_not_need_fal(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("FAL_KEY", raising=False)
    assert e2e.preflight(["blog"], want_images=False) == []


def test_post_stage_renders_and_saves(stubbed):
    out = e2e.run_post(stubbed, want_images=True)
    assert out["caption"].startswith("Hook line")
    assert out["image_file"]
    assert (stubbed / "post-blueprint.json").exists()
    assert (stubbed / "post-creative.png").exists()


def test_carousel_stage_renders_every_slide(stubbed):
    out = e2e.run_carousel(stubbed, want_images=True)
    assert out["slide_count"] == 6
    assert len(out["slides"]) == 6
    assert all(s["image_file"] for s in out["slides"])
    assert (stubbed / "carousel-package.json").exists()
    assert (stubbed / "carousel-slide6.png").exists()


def test_blog_stage_writes_markdown_and_hero(stubbed):
    out = e2e.run_blog(stubbed, want_images=True)
    assert out["slug"] == "kokapet-luxury-apartments"
    assert out["word_count"] > 300
    assert out["hero_file"]
    body = (stubbed / "blog-article.md").read_text()
    assert body.startswith("# Kokapet Luxury Apartments")


def test_no_images_flag_skips_every_fal_call(stubbed, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("fal must not be called with --no-images")

    monkeypatch.setattr(brain, "fal_image", boom)
    assert "image_file" not in e2e.run_post(stubbed, want_images=False)
    assert e2e.run_carousel(stubbed, want_images=False)["slides"] == []
    assert "hero_file" not in e2e.run_blog(stubbed, want_images=False)


def test_summary_is_written_for_failures(stubbed):
    e2e.summarise(stubbed, {"post": {"error": "RuntimeError: FAL_KEY is not set"}})
    text = (stubbed / "SUMMARY.md").read_text()
    assert "post — FAILED" in text
    assert "FAL_KEY is not set" in text

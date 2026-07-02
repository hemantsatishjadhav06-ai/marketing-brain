"""Unit tests for the scoring engine (pure functions, no DB needed for most)."""
from __future__ import annotations

from app.services.scoring import (
    WEIGHTS,
    score_brand_fit,
    score_business_value,
    score_evergreen_value,
    score_inventory_relevance,
    score_risk_penalty,
)


class _FakeBrain:
    """Lightweight stand-in for BrandBrain in pure-function tests."""

    def __init__(self, seo_keywords=None, banned_phrases=None):
        self.seo_keywords = seo_keywords or []
        self.banned_phrases = banned_phrases or []


class _FakeProduct:
    def __init__(self, sku, margin, *, is_dead_stock=False, is_bestseller=False, is_new=False, is_discounted=False):
        self.sku = sku
        self.margin = margin
        self.is_dead_stock = is_dead_stock
        self.is_bestseller = is_bestseller
        self.is_new = is_new
        self.is_discounted = is_discounted


def test_weights_sum_to_100():
    assert sum(abs(w) for w in WEIGHTS.values()) == 100


def test_evergreen_tutorial_beats_news():
    ev_tut, _ = score_evergreen_value("How to choose grip size — beginner guide", "static_post")
    ev_news, _ = score_evergreen_value("Breaking: new release just dropped", "static_post")
    assert ev_tut > ev_news


def test_business_value_zero_products():
    v, _ = score_business_value([])
    assert v == 50.0  # neutral


def test_business_value_scales_with_margin():
    low, _ = score_business_value([_FakeProduct("a", 20)])
    high, _ = score_business_value([_FakeProduct("b", 200)])
    assert high > low


def test_inventory_dead_stock_wins():
    v, notes = score_inventory_relevance([_FakeProduct("x", 100, is_dead_stock=True)])
    assert v >= 90
    assert any("DEAD STOCK" in n for n in notes)


def test_brand_fit_overlap_beats_no_overlap():
    brain = _FakeBrain(seo_keywords=["string", "grip", "footwork"])
    hit, _ = score_brand_fit("How to choose string tension", "Grip 101", brain)
    miss, _ = score_brand_fit("Random unrelated topic about cooking", "Pasta 101", brain)
    assert hit > miss


def test_risk_penalty_triggers_on_banned_phrase():
    brain = _FakeBrain(banned_phrases=["guaranteed wins", "best ever"])
    pen, notes = score_risk_penalty("This guarantees you the best ever serve", "Tip", brain)
    assert pen > 0
    assert any("banned" in n for n in notes)


def test_risk_penalty_zero_when_clean():
    brain = _FakeBrain(banned_phrases=["bad phrase"])
    pen, _ = score_risk_penalty("Clean copy about a serve", "Tip", brain)
    assert pen == 0

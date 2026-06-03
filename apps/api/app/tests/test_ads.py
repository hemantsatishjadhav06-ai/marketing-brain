"""AdsAgent fallback produces 3 distinct variants for A/B/C."""
from __future__ import annotations

from app.agents.ads import _google_fallback, _meta_fallback


class _Brand:
    sport = "tennis"
    name = "Test"


def test_meta_fallback_three_variants():
    out = _meta_fallback(_Brand(), "string tension", None)
    assert len(out["variants"]) == 3
    labels = {v["label"] for v in out["variants"]}
    assert labels == {"A", "B", "C"}


def test_meta_variant_headlines_distinct():
    out = _meta_fallback(_Brand(), "string tension", None)
    headlines = [v["headline"] for v in out["variants"]]
    assert len(set(headlines)) == 3


def test_google_search_fallback_has_short_headlines():
    out = _google_fallback(_Brand(), "string tension", None)
    for v in out["variants"]:
        assert len(v["headline"]) <= 40

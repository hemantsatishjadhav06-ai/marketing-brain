"""Pure-function unit tests for the brain-refine helpers."""
from __future__ import annotations

from app.services.brain_refine import _flatten_payload, _tokens


def test_flatten_pulls_nested_strings():
    payload = {
        "title": "Grip basics",
        "sections": [{"h2": "Why grip matters", "body": "It changes everything."}],
        "extra": {"deep": ["string tension", "string gauge"]},
    }
    flat = _flatten_payload(payload).lower()
    assert "grip" in flat and "string tension" in flat and "everything" in flat


def test_tokens_drops_stopwords():
    out = set(_tokens("The grip and the string tension are everything for your serve"))
    assert "grip" in out
    assert "string" in out
    assert "tension" in out
    assert "the" not in out
    assert "and" not in out
    assert "are" not in out


def test_tokens_min_length():
    # 3+ chars only — drops "is", "of"
    out = set(_tokens("It is a guide of fundamentals"))
    assert "guide" in out
    assert "is" not in out
    assert "of" not in out

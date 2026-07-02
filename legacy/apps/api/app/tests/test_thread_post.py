"""Thread-post deterministic fallback respects platform char limits."""
from __future__ import annotations

from app.agents.thread_post import LI_LIMIT, X_LIMIT, _fallback


class _Brand:
    sport = "tennis"
    name = "Test"


def test_x_thread_under_limit():
    out = _fallback(_Brand(), "string tension", "x")
    for p in out["posts"]:
        assert len(p["text"]) <= X_LIMIT
    assert out["posts"][0]["is_hook"] is True
    assert out["posts"][-1]["is_cta"] is True


def test_linkedin_thread_uses_larger_limit():
    out = _fallback(_Brand(), "string tension", "linkedin")
    for p in out["posts"]:
        assert len(p["text"]) <= LI_LIMIT


def test_at_least_5_posts():
    out = _fallback(_Brand(), "x", "x")
    assert len(out["posts"]) >= 5

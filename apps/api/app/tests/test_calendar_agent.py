"""Calendar agent honours per-channel cadence caps."""
from __future__ import annotations

from app.agents.calendar import CHANNEL_DAILY_CAP, LONG_FORM_TYPES, MAX_LONG_FORM_PER_DAY


def test_caps_present_for_major_channels():
    for p in ("instagram", "youtube", "blog", "email", "x", "linkedin"):
        assert p in CHANNEL_DAILY_CAP
        assert CHANNEL_DAILY_CAP[p] >= 1


def test_blog_is_long_form_capped_at_one_per_day():
    assert "blog" in LONG_FORM_TYPES
    assert MAX_LONG_FORM_PER_DAY == 1


def test_youtube_long_is_long_form():
    assert "youtube_long" in LONG_FORM_TYPES

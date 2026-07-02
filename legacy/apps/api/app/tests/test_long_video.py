"""LongVideoAgent helpers."""
from __future__ import annotations

from app.agents.long_video import _fallback, _youtube_chapters


class _Brand:
    sport = "tennis"
    name = "Test"


def test_fallback_assigns_chapter_starts():
    out = _fallback(_Brand(), "footwork drills")
    starts = [ch["start_s"] for ch in out["chapters"]]
    assert starts == sorted(starts)
    assert starts[0] >= 5.0   # leaves room for an intro
    # at least 3 chapters
    assert len(out["chapters"]) >= 3


def test_youtube_chapters_first_line_is_intro():
    out = _fallback(_Brand(), "footwork")
    yt = _youtube_chapters(out["chapters"])
    lines = yt.splitlines()
    assert lines[0].startswith("0:00")
    assert all(":" in ln for ln in lines)

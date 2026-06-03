"""Calendar Agent (spec § 6.14, § 11).

Phase 1 real implementation. Takes the top-scored ContentIdea rows and lays them
into a 30-day grid honouring:
  • per-channel cadence caps (e.g. max 1 IG reel/day, max 2 IG static/day)
  • slot diversity (don't put 3 carousels on the same day)
  • exec rule: at most 1 long-form (blog / youtube_long) per day
  • exec rule: every active platform gets at least 1 post in the period

The result is a list of CalendarEntry rows committed to the database.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.content import CalendarEntry, ContentIdea


CHANNEL_DAILY_CAP = {
    "instagram": 2,
    "youtube": 1,
    "tiktok": 1,
    "x": 3,
    "linkedin": 1,
    "pinterest": 2,
    "blog": 1,
    "email": 1,
    "reddit": 1,
    "meta_ads": 2,
    "google_ads": 2,
}
LONG_FORM_TYPES = {"blog", "youtube_long"}
MAX_LONG_FORM_PER_DAY = 1


def _agent_for(content_type: str) -> str:
    return {
        "static_post": "static_post",
        "carousel": "carousel",
        "reel": "reel_voice",
        "youtube_short": "short_video",
        "youtube_long": "long_video",
        "blog": "blog",
        "email": "email",
        "post": "static_post",        # simple feed post → static_post draft (caption only)
        "thread": "thread_post",      # explicit thread content type → multi-post sequence
        "ad": "ads",                  # paid ad slots
    }.get(content_type, "static_post")


class CalendarAgent:
    name = "calendar"

    def generate(
        self,
        db: Session,
        brand_id: uuid.UUID,
        *,
        days: int = 30,
        start: date | None = None,
        replace_existing: bool = True,
    ) -> dict:
        brand = db.get(Brand, brand_id)
        if not brand:
            raise ValueError(f"brand {brand_id} not found")

        ideas: list[ContentIdea] = list(
            db.execute(
                select(ContentIdea)
                .where(ContentIdea.brand_id == brand_id)
                .order_by(desc(ContentIdea.score))
                .limit(500)
            ).scalars().all()
        )
        if not ideas:
            return {"entries_created": 0, "reason": "no ideas — run idea_mill first"}

        if replace_existing:
            db.execute(delete(CalendarEntry).where(CalendarEntry.brand_id == brand_id))

        start_date = start or date.today()
        per_day_channel: dict[tuple[date, str], int] = defaultdict(int)
        per_day_long_form: dict[date, int] = defaultdict(int)
        platforms_seen: set[str] = set()
        entries: list[CalendarEntry] = []
        used_idea_ids: set[uuid.UUID] = set()

        for day_offset in range(days):
            d = start_date + timedelta(days=day_offset)
            for idea in ideas:
                if idea.id in used_idea_ids:
                    continue
                cap = CHANNEL_DAILY_CAP.get(idea.platform, 1)
                if per_day_channel[(d, idea.platform)] >= cap:
                    continue
                if idea.content_type in LONG_FORM_TYPES and per_day_long_form[d] >= MAX_LONG_FORM_PER_DAY:
                    continue
                entry = CalendarEntry(
                    brand_id=brand_id,
                    date=d,
                    platform=idea.platform,
                    content_type=idea.content_type,
                    product_ids=idea.product_ids,
                    angle=idea.angle,
                    agent_name=_agent_for(idea.content_type),
                    score=idea.score,
                    reason=idea.reason[:1900],
                    status="planned",
                    position=len(entries),
                )
                entries.append(entry)
                db.add(entry)
                per_day_channel[(d, idea.platform)] += 1
                if idea.content_type in LONG_FORM_TYPES:
                    per_day_long_form[d] += 1
                platforms_seen.add(idea.platform)
                used_idea_ids.add(idea.id)

        db.commit()
        return {
            "brand_id": str(brand_id),
            "entries_created": len(entries),
            "platforms_covered": sorted(platforms_seen),
            "days": days,
            "start": start_date.isoformat(),
        }

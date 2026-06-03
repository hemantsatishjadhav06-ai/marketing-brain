"""Thread Post Agent — multi-post sequence for X / LinkedIn.

Payload shape:
{
  "platform_hint": "x" | "linkedin",
  "posts": [
    {"index": 0, "text": "hook tweet — pattern break", "is_hook": true},
    {"index": 1, "text": "body 1"}, ...
    {"index": N, "text": "CTA + link in bio", "is_cta": true}
  ],
  "hashtags": [str],
  "summary": str    # for the calendar preview
}

The X publisher posts the first and threads replies; the LinkedIn publisher
posts each as a comment to the first.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult, render_cross_sport_clause
from app.models.brand import Brand, BrandBrain
from app.models.content import CalendarEntry, ContentItem, ContentVariant
from app.models.products import Product
from app.pipeline.llm_gateway import LLMTier, complete


X_LIMIT = 270   # leave room for thread numbering
LI_LIMIT = 2900


def _fallback(brand: Brand, angle: str, platform: str) -> dict:
    limit = X_LIMIT if platform == "x" else LI_LIMIT
    base = [
        f"Most {brand.sport} players get this wrong about {angle}.",
        "Here's what we found after running the drills for a season.",
        "1) Start with the smallest unit of the technique.",
        "2) Repeat it cold — no warm-up first.",
        "3) Add resistance, not speed.",
        "4) Track one variable per week. That's it.",
        "Save this. Try one thing tomorrow.",
    ]
    posts = [{"index": i, "text": p[:limit], "is_hook": i == 0, "is_cta": i == len(base) - 1} for i, p in enumerate(base)]
    return {
        "platform_hint": platform,
        "posts": posts,
        "hashtags": [f"#{brand.sport}", "#training"],
        "summary": angle[:120],
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str, platform: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Direct, useful, non-hypey."
    limit = X_LIMIT if platform == "x" else LI_LIMIT
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + f"\nYou are the Thread agent. Write a {platform} thread of 5-9 posts.\n"
        + f"Each post ≤ {limit} chars. First post is a pattern-break hook. Last post is the CTA.\n"
        + "Output ONLY JSON: {\"posts\": [{\"text\": str}], \"hashtags\": [str], \"summary\": str (≤120 chars)}."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle/topic: {angle}\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=1500)
    try:
        data = res.json_data or json.loads(res.content)
    except Exception:
        data = _fallback(brand, angle, platform)
    posts_in = data.get("posts") or []
    posts_out = []
    for i, p in enumerate(posts_in):
        text = (p.get("text") if isinstance(p, dict) else str(p))[:limit]
        posts_out.append({
            "index": i,
            "text": text,
            "is_hook": i == 0,
            "is_cta": i == len(posts_in) - 1,
        })
    payload = {
        "platform_hint": platform,
        "posts": posts_out,
        "hashtags": data.get("hashtags", [f"#{brand.sport}"]),
        "summary": (data.get("summary") or angle)[:140],
    }
    return payload, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class ThreadPostAgent:
    name = "thread_post"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        platform = entry.platform if entry.platform in {"x", "linkedin"} else "x"

        if settings.OPENROUTER_API_KEY:
            try:
                payload, agent_result = _llm(brand, brain, entry.angle, platform)
            except Exception:
                payload = _fallback(brand, entry.angle, platform)
                agent_result = AgentResult(output={}, model="fallback")
        else:
            payload = _fallback(brand, entry.angle, platform)
            agent_result = AgentResult(output={}, model="fallback")

        item = ContentItem(
            brand_id=brand_id,
            platform=entry.platform,
            content_type=entry.content_type,
            angle=entry.angle,
            product_ids=entry.product_ids,
            payload=payload,
            status="drafted",
            agent_name=self.name,
            created_by="ai",
        )
        db.add(item); db.flush()
        db.add(ContentVariant(content_item_id=item.id, label="A", payload=payload))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()
        return {
            "content_item_id": str(item.id),
            "post_count": len(payload["posts"]),
            "platform_hint": payload["platform_hint"],
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

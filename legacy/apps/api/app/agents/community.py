"""Community Answer Agent (spec § 6.7).

Quora / Reddit / FAQ-style answers. Long-form, expertise-led, single-sport,
links back to the brand site naturally (not spammy). NEVER cross-sport.

Payload:
{
  "question": str,            # what we're answering
  "platform_hint": "quora" | "reddit" | "faq",
  "answer": str,              # 250-600 words, opinion-first then evidence
  "sources_internal": [str],  # urls on the brand site to link
  "tldr": str,                # one-paragraph TL;DR for Reddit-style threads
  "hashtags": [str]           # only used on quora-style topic tags
}
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


def _fallback(brand: Brand, angle: str) -> dict:
    return {
        "question": f"{angle}?",
        "platform_hint": "quora",
        "answer": (
            f"Short answer: most {brand.sport} players overthink this. "
            f"Here's what actually moves the needle, based on what we see at {brand.name}.\n\n"
            "1. Start with the basics — most issues are technique, not gear.\n"
            "2. Match the gear to your level honestly.\n"
            "3. Don't optimise for what the top 1% use; optimise for what works for you tomorrow.\n\n"
            "If you've ruled the basics out, then it's worth thinking about gear specifics — string tension, "
            "grip size, racket weight, that order."
        ),
        "sources_internal": ["/blog", "/shop"],
        "tldr": f"Most {brand.sport} {angle} questions are answered by fixing technique first, gear second.",
        "hashtags": [brand.sport, "training", "gear"],
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Plain-spoken expert, never salesy."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the Community Answer agent. Write a Quora/Reddit-style answer.\n"
        + "Output ONLY JSON: {\"question\": str, \"platform_hint\": \"quora\"|\"reddit\"|\"faq\", "
        + "\"answer\": str (250-600 words, opinion-first then evidence), \"sources_internal\": [str], "
        + "\"tldr\": str (one paragraph), \"hashtags\": [str (≤6, no #)]}."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nTopic / question angle: {angle}\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=1500)
    try:
        data = res.json_data or json.loads(res.content)
    except Exception:
        data = _fallback(brand, angle)
    return data, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class CommunityAgent:
    name = "community"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()

        if settings.OPENROUTER_API_KEY:
            try:
                payload, agent_result = _llm(brand, brain, entry.angle)
            except Exception:
                payload = _fallback(brand, entry.angle); agent_result = AgentResult(output={}, model="fallback")
        else:
            payload = _fallback(brand, entry.angle); agent_result = AgentResult(output={}, model="fallback")

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
            "platform_hint": payload.get("platform_hint"),
            "word_count": len((payload.get("answer") or "").split()),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

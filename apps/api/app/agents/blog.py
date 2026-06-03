"""Blog Agent (spec § 6.7) — long-form SEO post.

Produces ContentItem.payload = {
  title, slug, meta_description, sections: [{h2, body}, ...], cta,
  word_count, target_keywords
}
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult, render_cross_sport_clause
from app.models.brand import Brand, BrandBrain
from app.models.content import CalendarEntry, ContentItem, ContentVariant
from app.models.products import Product
from app.pipeline.llm_gateway import LLMTier, complete


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:80]


def _fallback_blog(brand: Brand, angle: str, product: Optional[Product]) -> dict:
    title = angle[:90]
    sections = [
        {"h2": "Why this matters", "body": f"Most {brand.sport} players overlook this. Here's why it's worth your attention."},
        {"h2": "The fundamentals", "body": "Start with the basics. Get these right and everything else follows."},
        {"h2": "Common mistakes", "body": "Five mistakes that quietly cost you matches."},
        {"h2": "How to apply it this week", "body": "A simple 5-day drill plan you can run on your home court."},
    ]
    return {
        "title": title,
        "slug": _slugify(title),
        "meta_description": f"{title} — practical guide for {brand.sport} players.",
        "sections": sections,
        "cta": f"Shop {brand.name} gear" if product is None else f"Try {product.title} this week.",
        "word_count": sum(len(s["body"].split()) for s in sections),
        "target_keywords": [brand.sport, angle.split()[0] if angle else brand.sport],
    }


class BlogAgent:
    name = "blog"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        product = None
        if entry.product_ids:
            product = db.get(Product, uuid.UUID(entry.product_ids[0]))

        agent_result = AgentResult(output={}, model="fallback")
        payload: dict
        if not settings.OPENROUTER_API_KEY:
            payload = _fallback_blog(brand, entry.angle, product)
        else:
            system = (
                render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
                + "\nYou are the Blog agent. Write an SEO-friendly 700–1000 word article.\n"
                + "Output ONLY JSON with fields: title, slug, meta_description (≤155 chars), "
                + "sections (array of {h2, body}, 4–6 sections, each body ≥120 words), cta, "
                + "word_count (integer), target_keywords (array)."
            )
            voice = (brain.voice if brain else "") or "Clear, useful, non-hypey."
            user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle/topic: {entry.angle}\n"
            if product:
                user += f"Featured product: {product.title} (${product.price})\n"
            try:
                res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=4000)
                payload = res.json_data or json.loads(res.content)
                agent_result = AgentResult(
                    output=payload, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                    cost_usd=res.cost_usd, model=res.model,
                )
            except Exception:
                payload = _fallback_blog(brand, entry.angle, product)

        if "slug" not in payload:
            payload["slug"] = _slugify(payload.get("title", entry.angle))

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
        db.add(item)
        db.flush()
        db.add(ContentVariant(content_item_id=item.id, label="A", payload=payload))

        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()

        return {
            "content_item_id": str(item.id),
            "slug": payload.get("slug"),
            "word_count": payload.get("word_count"),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

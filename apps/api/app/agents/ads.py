"""Ads Agent — Meta + Google paid copy with A/B/C variants.

Payload shape:
{
  "ad_format": "meta" | "google_search",
  "variants": [
    {"label": "A", "headline": str, "primary_text": str, "description": str, "cta": "Shop now" | "Learn more" | ...},
    {"label": "B", ...},
    {"label": "C", ...}
  ],
  "target_audience": str,
  "landing_url": str
}

Each variant is ALSO persisted as a ContentVariant row so the platform-side
A/B engine can pick one randomly when uploaded.
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


META_CTAS = ["Shop now", "Learn more", "Sign up", "Get offer", "Subscribe"]


def _meta_fallback(brand: Brand, angle: str, product: Optional[Product]) -> dict:
    base = product.title if product else f"{brand.name} essentials"
    return {
        "ad_format": "meta",
        "variants": [
            {"label": "A", "headline": f"{base} — built for {brand.sport}", "primary_text": f"Real reviews from real {brand.sport} players. Free shipping today.", "description": "Trusted by 12,000+ players.", "cta": "Shop now"},
            {"label": "B", "headline": f"Stop overpaying for {base}.", "primary_text": f"We tested 28 options. {base} won on 4/5 criteria.", "description": "30-day returns. No-quibble.", "cta": "Learn more"},
            {"label": "C", "headline": f"This is why pros pick {base}.", "primary_text": "Behind the scenes look at our gear test, on court.", "description": "Watch the 60-second breakdown.", "cta": "Get offer"},
        ],
        "target_audience": f"{brand.sport} enthusiasts 22-45, engaged with strings/grips topics",
        "landing_url": "/shop",
    }


def _google_fallback(brand: Brand, angle: str, product: Optional[Product]) -> dict:
    base = product.title if product else f"{brand.name}"
    return {
        "ad_format": "google_search",
        "variants": [
            {"label": "A", "headline": f"{base} | Free Shipping", "primary_text": "", "description": f"Built for {brand.sport}. Reviewed by pros. 30-day returns.", "cta": "Shop now"},
            {"label": "B", "headline": f"{base} - Real Reviews", "primary_text": "", "description": "12k+ players choose us. Compare specs side-by-side.", "cta": "Learn more"},
            {"label": "C", "headline": f"{base} Sale Today", "primary_text": "", "description": "Limited stock. Free shipping over $50.", "cta": "Get offer"},
        ],
        "target_audience": f"{brand.sport} long-tail search intent",
        "landing_url": "/shop",
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str, product: Optional[Product], ad_format: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Direct, no-hype, benefit-led."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + f"\nYou are the Ads agent for {ad_format}. Generate 3 distinct ad variants (A/B/C) for A/B/C testing.\n"
        + ("Meta limits: headline ≤ 40 chars · primary_text ≤ 125 chars · description ≤ 30 chars · CTA from " + ", ".join(META_CTAS) + ".\n" if ad_format == "meta" else "Google Search limits: each headline ≤ 30 chars · description ≤ 90 chars.\n")
        + "Output ONLY JSON: {\"variants\": [{\"label\": str, \"headline\": str, \"primary_text\": str, \"description\": str, \"cta\": str}], \"target_audience\": str, \"landing_url\": str}."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {angle}\n"
    if product:
        user += f"Featured product: {product.title} (${product.price})\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=1500)
    try:
        data = res.json_data or json.loads(res.content)
    except Exception:
        data = _meta_fallback(brand, angle, product) if ad_format == "meta" else _google_fallback(brand, angle, product)
    data["ad_format"] = ad_format
    return data, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class AdsAgent:
    name = "ads"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        product: Optional[Product] = db.get(Product, uuid.UUID(entry.product_ids[0])) if entry.product_ids else None
        ad_format = "google_search" if entry.platform == "google" else "meta"

        if settings.OPENROUTER_API_KEY:
            try:
                payload, agent_result = _llm(brand, brain, entry.angle, product, ad_format)
            except Exception:
                payload = _meta_fallback(brand, entry.angle, product) if ad_format == "meta" else _google_fallback(brand, entry.angle, product)
                agent_result = AgentResult(output={}, model="fallback")
        else:
            payload = _meta_fallback(brand, entry.angle, product) if ad_format == "meta" else _google_fallback(brand, entry.angle, product)
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
        for v in payload.get("variants", []):
            db.add(ContentVariant(content_item_id=item.id, label=v.get("label", "A"), payload=v))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()
        return {
            "content_item_id": str(item.id),
            "variants": len(payload.get("variants", [])),
            "ad_format": ad_format,
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

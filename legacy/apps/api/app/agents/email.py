"""Email Agent (spec § 6.9) — broadcast newsletter."""
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


def _fallback_email(brand: Brand, angle: str, product: Optional[Product]) -> dict:
    return {
        "subject_line": angle[:60],
        "preheader": f"Quick read for {brand.sport} players.",
        "blocks": [
            {"type": "headline", "text": angle[:80]},
            {"type": "paragraph", "text": "Here's what we found this week, and what to try on court next."},
            {"type": "paragraph", "text": "Three ideas, ten minutes total. Then back to your match prep."},
            {"type": "cta", "text": f"Browse {brand.name} gear", "url": "/shop"},
        ],
        "footer": f"{brand.name} · unsubscribe",
    }


class EmailAgent:
    name = "email"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        product: Optional[Product] = None
        if entry.product_ids:
            product = db.get(Product, uuid.UUID(entry.product_ids[0]))

        agent_result = AgentResult(output={}, model="fallback")
        if not settings.OPENROUTER_API_KEY:
            payload = _fallback_email(brand, entry.angle, product)
        else:
            system = (
                render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
                + "\nYou are the Email agent. Write a broadcast email.\n"
                + "Output ONLY JSON: {\"subject_line\": str (≤60), \"preheader\": str (≤90), "
                + "\"blocks\": [{\"type\": \"headline|paragraph|cta\", \"text\": str, \"url\": str (only for cta)}], "
                + "\"footer\": str}.\n"
                + "Aim for 3–5 blocks, end with one cta."
            )
            voice = (brain.voice if brain else "") or "Friendly, useful, non-hypey."
            user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {entry.angle}\n"
            if product:
                user += f"Featured product: {product.title} (${product.price})\n"
            try:
                res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=1500)
                payload = res.json_data or json.loads(res.content)
                agent_result = AgentResult(
                    output=payload, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                    cost_usd=res.cost_usd, model=res.model,
                )
            except Exception:
                payload = _fallback_email(brand, entry.angle, product)

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
        # B variant for A/B subject-line test
        from app.agents._ab import make_b_variant_for_email
        b_payload = make_b_variant_for_email(
            brand_sport=brand.sport,
            brand_voice=(brain.voice if brain else ""),
            angle=entry.angle,
            a_payload=payload,
        )
        db.add(ContentVariant(content_item_id=item.id, label="B", payload=b_payload))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()

        return {
            "content_item_id": str(item.id),
            "subject_line": payload.get("subject_line"),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

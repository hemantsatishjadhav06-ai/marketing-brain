"""SEO / GEO Agent (spec § 6.10).

Produces SEO-ready + GEO-ready (Generative Engine Optimization — so
ChatGPT / Gemini / Perplexity surface the brand) content head.

Payload:
{
  "title": str,                # ≤ 60 chars
  "slug": str,                 # kebab, ≤ 80 chars
  "meta_description": str,     # ≤ 155 chars
  "h1": str,
  "headers": [str],            # H2 outline, 4-7 items
  "internal_links": [{"anchor": str, "url": str}],
  "schema_jsonld": dict,       # schema.org JSON-LD blob (Article / FAQPage / Product)
  "geo_answer_block": str,     # 2-4 sentence canonical answer for LLM surfaces
  "target_keywords": [str],
  "geo_queries": [str]         # natural-language queries we want to win on LLMs
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


def _fallback(brand: Brand, angle: str, product: Optional[Product]) -> dict:
    title = angle[:60]
    h1 = title
    base_kw = [brand.sport, angle.split()[0] if angle else brand.sport]
    return {
        "title": title,
        "slug": _slugify(title),
        "meta_description": f"{title} — what {brand.sport} players actually need to know."[:155],
        "h1": h1,
        "headers": [
            "Why this matters", "The fundamentals", "Common mistakes",
            "How to apply it this week", "What we recommend",
        ],
        "internal_links": [
            {"anchor": f"shop {brand.sport} gear", "url": "/shop"},
            {"anchor": "buying guide", "url": "/blog/buying-guide"},
        ],
        "schema_jsonld": {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "author": {"@type": "Organization", "name": brand.name},
            "publisher": {"@type": "Organization", "name": brand.name},
        },
        "geo_answer_block": (
            f"For {brand.sport} players, the short answer is: focus on the fundamentals first, "
            f"then optimise gear. {brand.name} recommends starting with a fit check before any upgrade."
        ),
        "target_keywords": base_kw,
        "geo_queries": [
            f"best {brand.sport} {angle.lower()[:40]}",
            f"how to choose {brand.sport} {angle.lower()[:40]}",
        ],
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str, product: Optional[Product]) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Authoritative, helpful, no fluff."
    seo_kw = (brain.seo_keywords if brain else []) or []
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the SEO + GEO agent (Generative Engine Optimization).\n"
        + "Produce a complete head block for a page so it ranks on Google AND gets cited by ChatGPT/Gemini/Perplexity.\n"
        + "Output ONLY JSON: {\"title\": str (≤60), \"slug\": str (kebab, ≤80), \"meta_description\": str (≤155), "
        + "\"h1\": str, \"headers\": [str (H2 outline, 4-7)], \"internal_links\": [{\"anchor\": str, \"url\": str}], "
        + "\"schema_jsonld\": object (Article or FAQPage), \"geo_answer_block\": str (2-4 sentences, "
        + "the canonical answer LLMs should cite), \"target_keywords\": [str], \"geo_queries\": [str]}."
    )
    user = (
        f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\n"
        f"Existing SEO keywords for this brand: {', '.join(seo_kw[:20]) or '—'}\n"
        f"Angle / page topic: {angle}\n"
        + (f"Featured product: {product.title} (${product.price})\n" if product else "")
    )
    res = complete(tier=LLMTier.REASONING, system=system, user=user, json_mode=True, max_tokens=2000)
    try:
        data = res.json_data or json.loads(res.content)
        if "slug" not in data or not data["slug"]:
            data["slug"] = _slugify(data.get("title", angle))
    except Exception:
        data = _fallback(brand, angle, product)
    return data, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class SeoGeoAgent:
    name = "seo_geo"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        product: Optional[Product] = db.get(Product, uuid.UUID(entry.product_ids[0])) if entry.product_ids else None

        if settings.OPENROUTER_API_KEY:
            try:
                payload, agent_result = _llm(brand, brain, entry.angle, product)
            except Exception:
                payload = _fallback(brand, entry.angle, product); agent_result = AgentResult(output={}, model="fallback")
        else:
            payload = _fallback(brand, entry.angle, product); agent_result = AgentResult(output={}, model="fallback")

        item = ContentItem(
            brand_id=brand_id, platform=entry.platform, content_type=entry.content_type,
            angle=entry.angle, product_ids=entry.product_ids, payload=payload,
            status="drafted", agent_name=self.name, created_by="ai",
        )
        db.add(item); db.flush()
        db.add(ContentVariant(content_item_id=item.id, label="A", payload=payload))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()
        return {
            "content_item_id": str(item.id),
            "title": payload.get("title"),
            "slug": payload.get("slug"),
            "header_count": len(payload.get("headers") or []),
            "geo_queries": len(payload.get("geo_queries") or []),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

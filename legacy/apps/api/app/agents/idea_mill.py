"""Idea Mill agent (spec § 6.2).

Generates a batch of ContentIdea rows for one brand. Each idea is:
  • paired with 0 or 1 products
  • spread across channels & content_types
  • scored via services.scoring before persistence
  • carries the AGENT NAME so we can attribute it later

Uses the LLM gateway in DRAFTING tier with json_mode for fast batch generation.
Falls back to a deterministic algorithmic generator if no API key is set.
"""
from __future__ import annotations

import json
import random
import re
import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult, render_cross_sport_clause
from app.models.brand import Brand, BrandBrain
from app.models.content import ContentIdea
from app.models.products import Product
from app.pipeline.llm_gateway import LLMTier, complete
from app.services.scoring import score_idea


CHANNEL_TYPES = [
    ("instagram", "static_post"),
    ("instagram", "carousel"),
    ("instagram", "reel"),
    ("youtube", "youtube_short"),
    ("youtube", "youtube_long"),
    ("blog", "blog"),
    ("email", "email"),
    ("x", "post"),
    ("x", "thread"),                 # multi-post thread
    ("linkedin", "post"),
    ("linkedin", "thread"),          # LI long-form follow-ups
    ("tiktok", "reel"),
    ("pinterest", "static_post"),
    ("meta_ads", "ad"),              # paid Meta ads
    ("google_ads", "ad"),            # paid Google Search ads
    ("reddit", "post"),
    ("quora", "answer"),             # community / Q&A long-form
    ("reddit", "answer"),            # subreddit answers
    ("pinterest", "pin"),            # vertical 1000×1500 pin
    ("blog", "seo_geo"),             # SEO + GEO head block for any web page
    ("whatsapp", "broadcast"),       # WA Business template
]

ANGLES_TEMPLATE = [
    "How to {topic} — beginner guide",
    "Why {topic} matters for your game",
    "5 mistakes beginners make with {topic}",
    "{product} vs alternatives — honest take",
    "The truth about {topic}",
    "Behind-the-scenes: how we test {topic}",
    "What pros actually use for {topic}",
    "{topic} explained in 60 seconds",
    "Pre-season checklist: {topic}",
    "Why most {topic} advice is wrong",
]


def _topics_from_brain(brain: BrandBrain | None) -> list[str]:
    base: list[str] = []
    if brain and brain.seo_keywords:
        base.extend([k for k in brain.seo_keywords if isinstance(k, str)])
    if not base:
        base = ["string tension", "grip size", "racket weight", "footwork", "serve technique"]
    return base


def _fallback_ideas(
    brand: Brand, brain: BrandBrain | None, products: list[Product], n: int
) -> list[dict]:
    """Deterministic generator used when OPENROUTER_API_KEY is unset."""
    rng = random.Random(str(brand.id))
    topics = _topics_from_brain(brain)
    out: list[dict] = []
    for i in range(n):
        topic = rng.choice(topics)
        product = rng.choice(products) if products and rng.random() < 0.6 else None
        platform, content_type = rng.choice(CHANNEL_TYPES)
        angle_tmpl = rng.choice(ANGLES_TEMPLATE)
        angle = angle_tmpl.format(topic=topic, product=(product.title if product else topic))
        title = angle[:120]
        out.append(
            {
                "title": title,
                "angle": angle,
                "platform": platform,
                "content_type": content_type,
                "product_sku": product.sku if product else None,
                "keywords": [topic, *([product.title] if product else [])],
            }
        )
    return out


def _llm_ideas(
    brand: Brand, brain: BrandBrain | None, products: list[Product], n: int
) -> tuple[list[dict], AgentResult]:
    sport = brand.sport
    topics = _topics_from_brain(brain)
    product_lines = [f"- {p.sku} | {p.title} | ${p.price} | category={p.category}" for p in products[:30]]
    voice = (brain.voice if brain else "") or "Clear, useful, non-hypey."
    system = (
        render_cross_sport_clause(sport=sport, brand_name=brand.name)
        + "\nYou are the Idea Mill agent for a marketing content brain.\n"
        + "Output ONLY valid JSON of the form: {\"ideas\": [...]}.\n"
        + "Each idea has fields: title, angle, platform, content_type, product_sku (nullable), keywords (array of strings).\n"
        + f"platform ∈ {sorted(set(p for p, _ in CHANNEL_TYPES))}\n"
        + f"content_type ∈ {sorted(set(t for _, t in CHANNEL_TYPES))}\n"
    )
    user = (
        f"Brand: {brand.name} (sport={sport})\n"
        f"Voice: {voice}\n"
        f"Topics of interest: {', '.join(topics)}\n\n"
        f"Available products (use SKU exactly when attaching):\n" + "\n".join(product_lines)
        + f"\n\nGenerate {n} distinct ideas spread across channels. "
        "Mix product-led and informational. Avoid duplicates. Keep titles < 90 chars."
    )
    res = complete(
        tier=LLMTier.DRAFTING,
        system=system,
        user=user,
        json_mode=True,
        temperature=0.85,
        max_tokens=4000,
    )
    ideas: list[dict] = []
    try:
        payload = res.json_data or json.loads(res.content)
        raw_ideas = payload.get("ideas") if isinstance(payload, dict) else None
        if isinstance(raw_ideas, list):
            for raw in raw_ideas[:n]:
                if not isinstance(raw, dict):
                    continue
                ideas.append(
                    {
                        "title": str(raw.get("title", ""))[:200],
                        "angle": str(raw.get("angle", ""))[:250],
                        "platform": str(raw.get("platform", "instagram")),
                        "content_type": str(raw.get("content_type", "static_post")),
                        "product_sku": raw.get("product_sku") or None,
                        "keywords": [str(k) for k in raw.get("keywords", []) if k],
                    }
                )
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    result = AgentResult(
        output={"raw_ideas_count": len(ideas)},
        tokens_in=res.tokens_in,
        tokens_out=res.tokens_out,
        cost_usd=res.cost_usd,
        model=res.model,
    )
    return ideas, result


class IdeaMillAgent:
    name = "idea_mill"

    def run(self, db: Session, brand_id: uuid.UUID, *, count: int = 40) -> dict:
        brand = db.get(Brand, brand_id)
        if not brand:
            raise ValueError(f"brand {brand_id} not found")
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        products = list(db.execute(select(Product).where(Product.brand_id == brand_id)).scalars().all())

        from app.core.config import settings

        agent_result: AgentResult | None = None
        if settings.OPENROUTER_API_KEY:
            try:
                raw_ideas, agent_result = _llm_ideas(brand, brain, products, count)
            except Exception:
                raw_ideas = _fallback_ideas(brand, brain, products, count)
        else:
            raw_ideas = _fallback_ideas(brand, brain, products, count)
        if not raw_ideas:
            raw_ideas = _fallback_ideas(brand, brain, products, count)

        # validate/score/persist
        sku_to_product = {p.sku: p for p in products}
        persisted = 0
        kept_ids: list[uuid.UUID] = []
        for raw in raw_ideas:
            title = (raw["title"] or "").strip()
            angle = (raw["angle"] or "").strip()
            if not title or not angle:
                continue
            sku = raw.get("product_sku")
            prod = sku_to_product.get(sku) if sku else None
            product_list = [prod] if prod else []
            breakdown = score_idea(
                db,
                brand_id=brand_id,
                title=title,
                angle=angle,
                content_type=raw["content_type"],
                keywords=raw.get("keywords") or [],
                products=product_list,
                brain=brain,
            )
            idea = ContentIdea(
                brand_id=brand_id,
                title=title,
                angle=angle,
                platform=raw["platform"],
                content_type=raw["content_type"],
                product_ids=[str(prod.id)] if prod else [],
                score=breakdown.total,
                reason=" | ".join(breakdown.notes)[:1900],
                source="ai",
                status="idea",
            )
            db.add(idea)
            db.flush()
            from app.services.scoring import persist_run

            persist_run(
                db,
                brand_id=brand_id,
                subject_type="idea",
                subject_id=idea.id,
                breakdown=breakdown,
                inputs={"keywords": raw.get("keywords") or [], "product_sku": sku},
            )
            persisted += 1
            kept_ids.append(idea.id)
        db.commit()

        return {
            "brand_id": str(brand_id),
            "ideas_persisted": persisted,
            "agent_cost_usd": agent_result.cost_usd if agent_result else 0.0,
            "model": agent_result.model if agent_result else "fallback",
            "tokens_in": agent_result.tokens_in if agent_result else 0,
            "tokens_out": agent_result.tokens_out if agent_result else 0,
            "first_idea_ids": [str(i) for i in kept_ids[:5]],
        }

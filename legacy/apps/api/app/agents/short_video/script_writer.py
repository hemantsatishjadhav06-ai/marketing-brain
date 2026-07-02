"""Draft a Script JSON from a Product + BrandBrain. Lifted from V1."""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.short_video.prompts import SCRIPT_WRITER_SYSTEM, SCRIPT_WRITER_USER
from app.models.brand import Brand, BrandBrain
from app.models.products import Product
from app.pipeline.llm_gateway import LLMTier, complete


def write_script(db: Session, product_id: uuid.UUID) -> dict:
    product = db.get(Product, product_id)
    if not product:
        raise ValueError(f"product {product_id} not found")
    brand = db.get(Brand, product.brand_id)
    brain = db.execute(
        BrandBrain.__table__.select().where(BrandBrain.brand_id == brand.id)
    ).first()
    voice = brain.voice if brain else ""
    tone = brain.tone if brain else ""
    banned = ", ".join(brain.banned_phrases) if brain else ""

    system = SCRIPT_WRITER_SYSTEM.format(
        brand_name=brand.name,
        sport=brand.sport,
        website=brand.website_url or "—",
        voice=voice or "(brand voice not configured)",
        tone=tone or "(tone not configured)",
        banned_phrases=banned or "(none configured)",
    )
    user = SCRIPT_WRITER_USER.format(
        sku=product.sku,
        title=product.title,
        category=product.category,
        price=float(product.price or 0),
        description=(product.description or "")[:1500],
        attributes=json.dumps(product.attributes or {})[:500],
    )

    result = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=1200)
    return {
        "script": result.json_data or {"raw": result.content},
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "cost_usd": result.cost_usd,
        "model": result.model,
    }

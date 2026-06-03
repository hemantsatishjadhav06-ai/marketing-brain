"""WhatsApp Template Agent (spec § 6.11).

WhatsApp Business message templates (≤1024 chars per body). Header + body +
optional CTA URL/quick-reply buttons. Opt-in audience only.

Payload:
{
  "category": "MARKETING" | "UTILITY" | "AUTHENTICATION",
  "header": {"type": "TEXT", "text": str (≤60)},
  "body": str,                   # ≤1024 chars; uses {{1}}, {{2}} for variables
  "body_examples": [str],        # default values for variables
  "footer": str | null,          # ≤60
  "buttons": [{"type": "URL"|"QUICK_REPLY", "text": str (≤25), "url": str | null}]
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


BODY_LIMIT = 1024
HEADER_LIMIT = 60
FOOTER_LIMIT = 60
BUTTON_LIMIT = 25


def _fallback(brand: Brand, angle: str, product: Optional[Product]) -> dict:
    body = (
        f"Hi {{{{1}}}}, this is {brand.name}.\n\n"
        f"{angle[:200]}\n\n"
        "Reply STOP to opt out."
    )[:BODY_LIMIT]
    return {
        "category": "MARKETING",
        "header": {"type": "TEXT", "text": angle[:HEADER_LIMIT]},
        "body": body,
        "body_examples": ["Hemant"],
        "footer": f"{brand.name} · {brand.sport}",
        "buttons": [
            {"type": "URL", "text": "Shop now"[:BUTTON_LIMIT], "url": "/shop"},
            {"type": "QUICK_REPLY", "text": "Tell me more"[:BUTTON_LIMIT], "url": None},
        ],
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str, product: Optional[Product]) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Friendly, useful, opt-in respectful."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the WhatsApp Template agent. Write a WhatsApp Business message template.\n"
        + f"body ≤ {BODY_LIMIT} chars · header ≤ {HEADER_LIMIT} · footer ≤ {FOOTER_LIMIT} · button text ≤ {BUTTON_LIMIT}.\n"
        + "Use {{1}}, {{2}} for personalisation variables.\n"
        + "Output ONLY JSON: {\"category\": \"MARKETING\"|\"UTILITY\", "
        + "\"header\": {\"type\": \"TEXT\", \"text\": str}, "
        + "\"body\": str, \"body_examples\": [str], \"footer\": str|null, "
        + "\"buttons\": [{\"type\": \"URL\"|\"QUICK_REPLY\", \"text\": str, \"url\": str|null}]}."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle / campaign: {angle}\n"
    if product:
        user += f"Featured product: {product.title} (${product.price})\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=900)
    try:
        data = res.json_data or json.loads(res.content)
        # enforce limits even if the LLM over-shoots
        data["body"] = (data.get("body") or "")[:BODY_LIMIT]
        if isinstance(data.get("header"), dict):
            data["header"]["text"] = (data["header"].get("text") or "")[:HEADER_LIMIT]
        if data.get("footer"):
            data["footer"] = data["footer"][:FOOTER_LIMIT]
        for b in data.get("buttons") or []:
            if isinstance(b, dict) and "text" in b:
                b["text"] = b["text"][:BUTTON_LIMIT]
    except Exception:
        data = _fallback(brand, angle, product)
    return data, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class WhatsAppAgent:
    name = "whatsapp"

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
            "category": payload.get("category"),
            "body_chars": len(payload.get("body") or ""),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

"""X / Twitter Single-Post Agent (spec § 6.8).

Single tweets — trend reactions, product drops, sport facts. Distinct from
the multi-post Thread agent. ≤ 270 chars. 0-2 hashtags. Optional poll prompt.

Payload:
{
  "text": str,             # ≤ 270 chars
  "hashtags": [str],       # 0-2
  "poll": {"options": [str, ...]} | null,
  "reply_strategy": str    # "trend"|"drop"|"fact"|"reply"
}
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult, render_cross_sport_clause
from app.models.brand import Brand, BrandBrain
from app.models.content import CalendarEntry, ContentItem, ContentVariant
from app.pipeline.llm_gateway import LLMTier, complete


X_LIMIT = 270


def _fallback(brand: Brand, angle: str) -> dict:
    text = f"Most {brand.sport} advice you read online is wrong about one thing: {angle.lower()[:120]}."
    return {
        "text": text[:X_LIMIT],
        "hashtags": [f"#{brand.sport}"],
        "poll": None,
        "reply_strategy": "fact",
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Punchy, direct, no hype."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the X / Twitter Single-Post agent. Write ONE tweet.\n"
        + f"≤ {X_LIMIT} chars. 0-2 hashtags. Optional poll (only if it actually adds value).\n"
        + "Output ONLY JSON: {\"text\": str, \"hashtags\": [str (≤2, with #)], "
        + "\"poll\": null | {\"options\": [str, ...]}, \"reply_strategy\": \"trend\"|\"drop\"|\"fact\"|\"reply\"}."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {angle}\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=500)
    try:
        data = res.json_data or json.loads(res.content)
        data["text"] = (data.get("text") or "")[:X_LIMIT]
    except Exception:
        data = _fallback(brand, angle)
    return data, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class XPostAgent:
    name = "x_post"

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
            "chars": len(payload.get("text") or ""),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

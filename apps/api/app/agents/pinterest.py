"""Pinterest Pin Agent (spec § 6.9).

Vertical 1000×1500 pin. Keyword-rich title + description. Board assignment.
Renders the pin image via the same Pillow recipe as static_post but at 2:3.

Payload:
{
  "title": str,             # ≤ 100 chars, keyword-front-loaded
  "description": str,       # ≤ 500 chars, hashtags optional
  "board_hint": str,        # which board this pin belongs to
  "alt_text": str,          # ≤ 500 chars, descriptive for accessibility
  "image_url": str,
  "image_key": str
}
"""
from __future__ import annotations

import io
import json
import textwrap
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult, render_cross_sport_clause
from app.models.assets import Asset
from app.models.brand import Brand, BrandBrain
from app.models.content import CalendarEntry, ContentItem, ContentVariant
from app.models.products import Product
from app.pipeline.llm_gateway import LLMTier, complete
from app.pipeline.storage import get_storage, new_key


W, H = 1000, 1500  # 2:3 Pinterest aspect


def _render_pin(title: str, body: str, accent: str, sport: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (W, H), color="#0e0e0e")
    draw = ImageDraw.Draw(img)
    # accent band at the top
    draw.rectangle([0, 0, W, 8], fill=accent)
    try:
        font_sport = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 78)
        font_body = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 34)
    except Exception:
        font_sport = font_title = font_body = ImageFont.load_default()
    draw.text((48, 40), sport.upper(), fill=accent, font=font_sport)
    # title
    wrap_t = textwrap.TextWrapper(width=18).wrap(title)[:5]
    y = 220
    for line in wrap_t:
        draw.text((48, y), line, fill="white", font=font_title)
        y += 90
    # body
    y += 30
    wrap_b = textwrap.TextWrapper(width=28).wrap(body)[:6]
    for line in wrap_b:
        draw.text((48, y), line, fill="#bbbbbb", font=font_body)
        y += 46
    # bottom accent
    draw.rectangle([0, H - 14, W, H], fill=accent)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _fallback(brand: Brand, angle: str) -> dict:
    title = f"{angle} for {brand.sport} players"[:100]
    return {
        "title": title,
        "description": f"What we look at when we test {brand.sport} gear — and what to skip. Save for later.",
        "board_hint": f"{brand.sport.title()} how-tos",
        "alt_text": f"Pinterest pin about {angle} for {brand.sport} players",
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Helpful, keyword-rich, no hype."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the Pinterest Pin agent. Output ONLY JSON: "
        + "{\"title\": str (≤100 chars, keyword-front-loaded), \"description\": str (≤500 chars), "
        + "\"board_hint\": str, \"alt_text\": str (≤500 chars)}."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {angle}\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=700)
    try:
        data = res.json_data or json.loads(res.content)
    except Exception:
        data = _fallback(brand, angle)
    return data, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


class PinterestAgent:
    name = "pinterest"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()

        if settings.OPENROUTER_API_KEY:
            try:
                copy, agent_result = _llm(brand, brain, entry.angle)
            except Exception:
                copy = _fallback(brand, entry.angle); agent_result = AgentResult(output={}, model="fallback")
        else:
            copy = _fallback(brand, entry.angle); agent_result = AgentResult(output={}, model="fallback")

        accent = brand.accent_color or "#CCFF00"
        img = _render_pin(copy.get("title", entry.angle), copy.get("description", ""), accent, brand.sport)
        storage = get_storage()
        key = new_key(brand_id, "pin", "png")
        url = storage.write_bytes(key, img)

        payload = {**copy, "image_url": url, "image_key": key}
        item = ContentItem(
            brand_id=brand_id, platform=entry.platform, content_type=entry.content_type,
            angle=entry.angle, product_ids=entry.product_ids, payload=payload,
            status="drafted", agent_name=self.name, created_by="ai",
        )
        db.add(item); db.flush()
        db.add(ContentVariant(content_item_id=item.id, label="A", payload=payload))
        db.add(Asset(brand_id=brand_id, content_item_id=item.id, kind="image",
                     storage_key=key, mime="image/png", width=W, height=H, meta={"agent": self.name}))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()
        return {
            "content_item_id": str(item.id),
            "image_url": url,
            "title_chars": len(copy.get("title", "")),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

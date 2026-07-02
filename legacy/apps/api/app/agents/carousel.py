"""Carousel Agent (spec § 6.6) — multi-slide IG/LinkedIn carousel.

Produces N rendered slide images + caption. Default = 6 slides.
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


W, H = 1080, 1350
SLIDE_COUNT_DEFAULT = 6


def _render_slide(idx: int, total: int, heading: str, body: str, accent: str, sport: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (W, H), color="#0e0e0e")
    draw = ImageDraw.Draw(img)
    # page counter pill
    draw.rectangle([W - 160, 40, W - 40, 100], fill=accent)
    try:
        font_count = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 28)
        font_head = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 56)
        font_body = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 36)
        font_sport = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
    except Exception:
        font_count = font_head = font_body = font_sport = ImageFont.load_default()
    draw.text((W - 130, 55), f"{idx}/{total}", fill="#0e0e0e", font=font_count)
    draw.text((48, 48), sport.upper(), fill=accent, font=font_sport)

    # heading
    wrap_h = textwrap.TextWrapper(width=22).wrap(heading)[:3]
    y = 180
    for line in wrap_h:
        draw.text((48, y), line, fill="white", font=font_head)
        y += 70
    y += 40
    # body
    wrap_b = textwrap.TextWrapper(width=30).wrap(body)[:10]
    for line in wrap_b:
        draw.text((48, y), line, fill="#bbbbbb", font=font_body)
        y += 50

    # accent bottom bar
    draw.rectangle([0, H - 16, W, H], fill=accent)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _fallback_slides(angle: str, n: int) -> list[dict]:
    base = [
        {"heading": angle[:60], "body": "Here's what most people get wrong."},
        {"heading": "Mistake #1", "body": "Going too heavy too early. Start light, build form."},
        {"heading": "Mistake #2", "body": "Skipping warm-up. Three minutes saves three weeks."},
        {"heading": "The fix", "body": "Use the 3-2-1 rule: 3 sets, 2-minute rest, 1 focus point."},
        {"heading": "What to do this week", "body": "Run this drill twice. Track results in a simple note."},
        {"heading": "Go further", "body": "Save this post and try one piece tomorrow."},
    ]
    return base[:n]


class CarouselAgent:
    name = "carousel"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID, *, slide_count: int = SLIDE_COUNT_DEFAULT) -> dict:
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
        slides: list[dict]
        caption: str
        hashtags: list[str]
        cta: str

        if not settings.OPENROUTER_API_KEY:
            slides = _fallback_slides(entry.angle, slide_count)
            caption = f"{entry.angle} — swipe →"
            hashtags = [f"#{brand.sport}", "#training", "#gear"]
            cta = "Save this post."
        else:
            system = (
                render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
                + f"\nYou are the Carousel agent. Design a {slide_count}-slide carousel.\n"
                + "Output ONLY JSON: {\"slides\": [{\"heading\": str, \"body\": str}, ...], \"caption\": str, \"hashtags\": [str], \"cta\": str}.\n"
                + "Each slide body ≤ 200 chars. caption ≤ 280 chars."
            )
            voice = (brain.voice if brain else "") or "Clear, useful, non-hypey."
            user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {entry.angle}\n"
            if product:
                user += f"Featured product: {product.title} (${product.price})\n"
            try:
                res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=2000)
                data = res.json_data or json.loads(res.content)
                slides = (data.get("slides") or [])[:slide_count]
                if not slides:
                    slides = _fallback_slides(entry.angle, slide_count)
                caption = data.get("caption") or entry.angle
                hashtags = data.get("hashtags") or [f"#{brand.sport}"]
                cta = data.get("cta") or "Save this post."
                agent_result = AgentResult(
                    output=data, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
                    cost_usd=res.cost_usd, model=res.model,
                )
            except Exception:
                slides = _fallback_slides(entry.angle, slide_count)
                caption, hashtags, cta = entry.angle, [f"#{brand.sport}"], "Save this post."

        # render + upload
        storage = get_storage()
        accent = brand.accent_color or "#CCFF00"
        slide_payload: list[dict] = []
        item = ContentItem(
            brand_id=brand_id,
            platform=entry.platform,
            content_type=entry.content_type,
            angle=entry.angle,
            product_ids=entry.product_ids,
            payload={},
            status="drafted",
            agent_name=self.name,
            created_by="ai",
        )
        db.add(item)
        db.flush()

        for i, s in enumerate(slides, start=1):
            img = _render_slide(i, len(slides), s.get("heading", ""), s.get("body", ""), accent, brand.sport)
            key = new_key(brand_id, "carousel", "png")
            url = storage.write_bytes(key, img)
            slide_payload.append({"index": i, "heading": s.get("heading"), "body": s.get("body"), "image_url": url, "image_key": key})
            db.add(Asset(brand_id=brand_id, content_item_id=item.id, kind="carousel", storage_key=key, mime="image/png", width=W, height=H, meta={"slide": i}))

        item.payload = {
            "slides": slide_payload,
            "caption": caption,
            "hashtags": hashtags,
            "cta": cta,
        }
        db.add(ContentVariant(content_item_id=item.id, label="A", payload=item.payload))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()

        return {
            "content_item_id": str(item.id),
            "slide_count": len(slide_payload),
            "first_slide_url": slide_payload[0]["image_url"] if slide_payload else None,
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

"""Reel + Voice Agent (spec § 6.4 reels track) — short vertical with TTS hook.

9:16 portrait, 15-30s, designed for IG Reels / TikTok / YouTube Shorts. Distinct
from short_video.product_video — this one is trend-driven and brand-themed
(no specific SKU required), and the structure is:

  • HOOK (2s, single line on-screen + voiceover)
  • 3-5 BEATS (each ~4-6s with a single thought + on-screen text)
  • CTA (2-3s on-screen)
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentResult, render_cross_sport_clause
from app.agents.critic import quick_critic
from app.models.assets import Asset
from app.models.brand import Brand, BrandBrain
from app.models.content import CalendarEntry, ContentItem, ContentVariant
from app.models.products import Product
from app.pipeline.llm_gateway import LLMTier, complete
from app.pipeline.media_gateway import get_media_provider
from app.pipeline.render import Scene, render_short_video
from app.pipeline.storage import get_storage, new_key


def _fallback(brand: Brand, angle: str) -> dict:
    return {
        "hook": f"Stop doing {angle.split()[0] if angle else 'this'} wrong",
        "beats": [
            {"text": "Most players load up here.", "on_screen": "MOST DO THIS"},
            {"text": "Pros do the opposite.", "on_screen": "PROS DO THIS"},
            {"text": "Three drills fix it this week.", "on_screen": "3 DRILLS"},
        ],
        "cta": "Save this. Try it tomorrow.",
        "voiceover": f"Stop doing it wrong. Most players load up here. Pros do the opposite. Three drills fix it this week. Save this. Try it tomorrow.",
    }


def _llm(brand: Brand, brain: BrandBrain | None, angle: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Punchy, direct, non-hypey."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the Reel + Voice agent. Write a 15-25s vertical reel script for IG/TikTok/Shorts.\n"
        + "Output ONLY JSON: {\"hook\": str (≤8 words), \"beats\": [{\"text\": str, \"on_screen\": str (CAPS, ≤4 words)}], \"cta\": str, \"voiceover\": str (concat of hook + every beat.text + cta, period-delimited)}.\n"
        + "3-5 beats total. Open with a pattern-break hook in the first 2 seconds."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {angle}\n"
    res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=800)
    try:
        payload = res.json_data or json.loads(res.content)
    except Exception:
        payload = _fallback(brand, angle)
    return payload, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


def _download(url: str, dest: Path) -> Path:
    if not url.startswith(("http://", "https://")):
        return Path(url)
    with httpx.Client(timeout=120) as c:
        r = c.get(url); r.raise_for_status(); dest.write_bytes(r.content)
    return dest


class ReelVoiceAgent:
    name = "reel_voice"

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
                script, agent_result = _llm(brand, brain, entry.angle)
            except Exception:
                script = _fallback(brand, entry.angle)
                agent_result = AgentResult(output={}, model="fallback")
        else:
            script = _fallback(brand, entry.angle)
            agent_result = AgentResult(output={}, model="fallback")

        critic = quick_critic(script.get("voiceover", "") + " " + script.get("hook", ""))
        if not critic.passed:
            raise ValueError(f"critic rejected: {critic.blocking_issues}")

        media = get_media_provider()
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            vo_text = script.get("voiceover", "")
            vo_path: Optional[Path] = None
            if vo_text:
                r = media.tts(text=vo_text)
                if r.url:
                    vo_path = _download(r.url, tdp / "vo.mp3")

            beats = script.get("beats", []) or []
            backdrop_src = (product.image_urls or [None])[0] if product else None
            scenes: list[Scene] = []
            # hook scene
            bg = tdp / "bg_hook.jpg"
            if backdrop_src and backdrop_src.startswith(("http://", "https://")):
                _download(backdrop_src, bg)
            else:
                from PIL import Image as PILImage
                PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(bg)
            scenes.append(Scene(duration_s=2.0, backdrop_path=str(bg), voiceover_path=str(vo_path) if vo_path else None, on_screen_text=script.get("hook", "")[:60].upper(), cta=""))
            # beat scenes
            for i, b in enumerate(beats[:5]):
                bg2 = tdp / f"bg_b{i:02d}.jpg"
                if backdrop_src and backdrop_src.startswith(("http://", "https://")):
                    _download(backdrop_src, bg2)
                else:
                    from PIL import Image as PILImage
                    PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(bg2)
                scenes.append(Scene(duration_s=5.0, backdrop_path=str(bg2), voiceover_path=None, on_screen_text=b.get("on_screen", "")[:40], cta=""))
            # cta scene
            bg3 = tdp / "bg_cta.jpg"
            if backdrop_src and backdrop_src.startswith(("http://", "https://")):
                _download(backdrop_src, bg3)
            else:
                from PIL import Image as PILImage
                PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(bg3)
            scenes.append(Scene(duration_s=2.5, backdrop_path=str(bg3), voiceover_path=None, on_screen_text="", cta=script.get("cta", "Save this.")))

            out = tdp / "out.mp4"
            render_short_video(scenes, str(out))
            storage = get_storage()
            key = new_key(brand_id, "videos", "mp4")
            url = storage.write_file(key, str(out))

        payload = {**script, "video_url": url, "video_key": key}
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
        db.add(ContentVariant(content_item_id=item.id, label="A", payload=payload))
        db.add(Asset(brand_id=brand_id, content_item_id=item.id, kind="video", storage_key=key, mime="video/mp4", meta={"agent": self.name}))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()
        return {
            "content_item_id": str(item.id),
            "video_url": url,
            "beats": len(script.get("beats", [])),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

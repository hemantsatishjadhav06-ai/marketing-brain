"""Long Video Agent (spec § 6.4) — chaptered long-form video.

Structurally distinct from the ShortVideoAgent:
  • intro (5-10s)
  • 3-6 chapters with timestamps + h2 + voiceover line + on-screen text
  • outro / CTA (5-10s)
Total target: 60-180s. Rendered with the same Pillow + ffmpeg pipeline from V1.

Payload schema:
{
  "title": str,
  "voiceover": str,              # full voiceover, periods aligned with beats
  "chapters": [
    {"start_s": float, "title": str, "body": str, "on_screen_text": str, "duration_s": float}
  ],
  "cta": str,
  "video_url": str,              # storage URL of the rendered MP4
  "chapters_youtube": str,       # newline-separated "MM:SS Title" — paste into YT description
}
"""
from __future__ import annotations

import io
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
    chapters = [
        {"title": "Why this matters", "body": f"What every {brand.sport} player gets wrong about {angle}.", "on_screen_text": "WHY THIS MATTERS", "duration_s": 18.0},
        {"title": "The fundamentals", "body": "Start here. Three principles that fix 80% of mistakes.", "on_screen_text": "FUNDAMENTALS", "duration_s": 22.0},
        {"title": "Common mistakes", "body": "Five mistakes beginners make that quietly cost matches.", "on_screen_text": "MISTAKES", "duration_s": 20.0},
        {"title": "Five-day drill plan", "body": "A simple progression you can run on a home court.", "on_screen_text": "DRILL PLAN", "duration_s": 22.0},
    ]
    start = 5.0
    for ch in chapters:
        ch["start_s"] = round(start, 1)
        start += ch["duration_s"]
    voiceover = " ".join(ch["body"] for ch in chapters)
    return {
        "title": angle[:90],
        "voiceover": voiceover,
        "chapters": chapters,
        "cta": "Subscribe for more.",
    }


def _llm_long_video(brand: Brand, brain: BrandBrain | None, angle: str) -> tuple[dict, AgentResult]:
    voice = (brain.voice if brain else "") or "Clear, useful, non-hypey."
    system = (
        render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
        + "\nYou are the Long Video agent. Write a script for a 90-180 second YouTube long video.\n"
        + "Output ONLY JSON:\n"
        + "{\"title\": str, \"voiceover\": str, \"chapters\": [{\"title\": str, \"body\": str, \"on_screen_text\": str, \"duration_s\": float}], \"cta\": str}.\n"
        + "Aim for 4-6 chapters; each body 25-40 words; on_screen_text ≤ 5 words SCREAMING CAPS.\n"
        + "voiceover = the entire script (intro + every chapter body + cta), period-delimited."
    )
    user = f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nAngle: {angle}\n"
    res = complete(tier=LLMTier.REASONING, system=system, user=user, json_mode=True, max_tokens=3000)
    try:
        payload = res.json_data or json.loads(res.content)
    except Exception:
        payload = _fallback(brand, angle)
    # compute chapter start_s
    start = 5.0
    for ch in payload.get("chapters", []):
        ch["start_s"] = round(start, 1)
        start += float(ch.get("duration_s", 20))
    return payload, AgentResult(
        output={}, tokens_in=res.tokens_in, tokens_out=res.tokens_out,
        cost_usd=res.cost_usd, model=res.model,
    )


def _youtube_chapters(chapters: list[dict]) -> str:
    lines: list[str] = []
    lines.append("0:00 Intro")
    for ch in chapters:
        secs = int(ch.get("start_s", 0))
        mm, ss = secs // 60, secs % 60
        lines.append(f"{mm}:{ss:02d} {ch.get('title','')}")
    return "\n".join(lines)


def _download(url: str, dest: Path) -> Path:
    if not url.startswith(("http://", "https://")):
        return Path(url)
    with httpx.Client(timeout=120) as c:
        r = c.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


class LongVideoAgent:
    name = "long_video"

    def run(self, db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID) -> dict:
        from app.core.config import settings

        entry = db.get(CalendarEntry, entry_id)
        if not entry or entry.brand_id != brand_id:
            raise ValueError("calendar entry not found")
        brand = db.get(Brand, brand_id)
        brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
        product = db.get(Product, uuid.UUID(entry.product_ids[0])) if entry.product_ids else None

        if settings.OPENROUTER_API_KEY:
            try:
                script, agent_result = _llm_long_video(brand, brain, entry.angle)
            except Exception:
                script = _fallback(brand, entry.angle)
                agent_result = AgentResult(output={}, model="fallback")
        else:
            script = _fallback(brand, entry.angle)
            agent_result = AgentResult(output={}, model="fallback")

        # cross-sport hard gate before doing any media spend
        critic = quick_critic(script.get("voiceover", "") + " " + " ".join(ch.get("on_screen_text", "") for ch in script.get("chapters", [])))
        if not critic.passed:
            raise ValueError(f"critic rejected: {critic.blocking_issues}")

        # render
        media = get_media_provider()
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            # one voiceover for the whole thing — anchored to scene 0
            voiceover_path: Optional[Path] = None
            vo_text = script.get("voiceover", "")
            if vo_text:
                r = media.tts(text=vo_text)
                if r.url:
                    voiceover_path = _download(r.url, tdp / "vo.mp3")

            # backdrop pool: product image (if any) repeated; fall back to dark plate
            backdrop_src = (product.image_urls or [None])[0] if product else None
            scenes: list[Scene] = []
            for i, ch in enumerate(script.get("chapters", []) or []):
                bg = tdp / f"bg_{i:02d}.jpg"
                if backdrop_src and backdrop_src.startswith(("http://", "https://")):
                    _download(backdrop_src, bg)
                else:
                    from PIL import Image as PILImage
                    PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(bg)
                scenes.append(
                    Scene(
                        duration_s=float(ch.get("duration_s", 20)),
                        backdrop_path=str(bg),
                        voiceover_path=str(voiceover_path) if (voiceover_path and i == 0) else None,
                        on_screen_text=str(ch.get("on_screen_text", "")),
                        cta=script.get("cta", "") if i == len(script["chapters"]) - 1 else "",
                    )
                )
            if not scenes:
                # nothing to render — make a single placeholder scene so we still produce a file
                bg = tdp / "bg.jpg"
                from PIL import Image as PILImage
                PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(bg)
                scenes = [Scene(duration_s=10.0, backdrop_path=str(bg), voiceover_path=str(voiceover_path) if voiceover_path else None, on_screen_text="MARKETING BRAIN", cta="")]

            out = tdp / "out.mp4"
            render_short_video(scenes, str(out))

            storage = get_storage()
            key = new_key(brand_id, "videos", "mp4")
            url = storage.write_file(key, str(out))

        payload = {
            **script,
            "video_url": url,
            "video_key": key,
            "chapters_youtube": _youtube_chapters(script.get("chapters", [])),
        }
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
        db.add(Asset(brand_id=brand_id, content_item_id=item.id, kind="video", storage_key=key, mime="video/mp4", meta={"agent": self.name}))
        entry.content_item_id = item.id
        entry.status = "drafted"
        db.commit()

        return {
            "content_item_id": str(item.id),
            "video_url": url,
            "chapter_count": len(script.get("chapters", [])),
            "cost_usd": agent_result.cost_usd,
            "model": agent_result.model,
        }

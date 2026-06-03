"""ShortVideoAgent — runs the `product_video` sub-type end-to-end.

Pipeline (lifted + simplified from V1):
  1. write_script (LLM draft)         → cost_log
  2. critic gate (cross-sport regex)  → reject early if bad
  3. for each scene: generate backdrop (fal nano-banana edit) [optional]
  4. tts the voiceover (fal elevenlabs)                       [optional]
  5. render mp4 via ffmpeg+Pillow
  6. upload to storage + return result dict for Job.result

In Phase 0 the LLM and fal calls have stub fallbacks so the pipeline runs
end-to-end without API keys (returns a placeholder MP4 path).
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from app.agents.critic import quick_critic
from app.agents.short_video.script_writer import write_script
from app.core.cost_guard import record_cost
from app.models.jobs import Job
from app.models.products import Product
from app.pipeline.media_gateway import get_media_provider
from app.pipeline.render import Scene, render_short_video
from app.pipeline.storage import get_storage, new_key
from app.workers.events import emit


def _download(url: str, dest: Path) -> Path:
    if not url.startswith(("http://", "https://")):
        return Path(url)
    with httpx.Client(timeout=120) as c:
        r = c.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


def run_product_video(db: Session, job: Job) -> dict:
    """`payload`: { product_id: uuid }. Returns { video_url, script, scenes_meta, critic }."""
    product_id = uuid.UUID(job.payload["product_id"])
    product = db.get(Product, product_id)
    if not product:
        raise ValueError(f"product {product_id} not found")
    if product.brand_id != job.brand_id:
        raise ValueError("product/brand mismatch — cross-brand violation")

    emit(job.id, status="scripting", message="Drafting script…")
    script_pack = write_script(db, product_id)
    record_cost(
        db,
        job.org_id,
        provider="openrouter",
        model=script_pack["model"],
        usd=script_pack["cost_usd"],
        brand_id=job.brand_id,
        job_id=job.id,
    )
    job.cost_usd = float(job.cost_usd or 0) + script_pack["cost_usd"]
    job.tokens_in += script_pack["tokens_in"]
    job.tokens_out += script_pack["tokens_out"]
    job.model = script_pack["model"]
    db.commit()

    script = script_pack["script"]
    transcript_for_critic = " ".join(
        [script.get("voiceover", "")] + [s.get("on_screen_text", "") for s in script.get("scenes", [])]
    )
    emit(job.id, status="critiquing", message="Cross-sport gate + rubric…")
    critic = quick_critic(transcript_for_critic)
    if not critic.passed:
        raise ValueError(f"critic rejected: {critic.blocking_issues}")

    # Phase 0: render with a placeholder backdrop if no product image is present,
    # so the full pipeline can complete without media-API keys.
    emit(job.id, status="generating_media", message="Backdrops + voiceover…")
    media = get_media_provider()

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        # voiceover — single call
        voiceover_path: Path | None = None
        vo = script.get("voiceover", "")
        if vo:
            r = media.tts(text=vo)
            if r.url:
                record_cost(db, job.org_id, provider="fal", model=r.model, usd=r.cost_usd, brand_id=job.brand_id, job_id=job.id)
                job.cost_usd = float(job.cost_usd or 0) + r.cost_usd
                voiceover_path = _download(r.url, td_path / "vo.mp3")

        # per-scene backdrop
        scenes_out: list[Scene] = []
        src_image = (product.image_urls or [None])[0]
        for i, s in enumerate(script.get("scenes", [])):
            dur = float(s.get("duration_s", 5))
            backdrop_path = td_path / f"bg_{i:02d}.jpg"
            if src_image:
                if src_image.startswith(("http://", "https://")):
                    _download(src_image, backdrop_path)
                else:
                    # local placeholder if no real image available
                    from PIL import Image as PILImage
                    PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(backdrop_path)
            else:
                from PIL import Image as PILImage
                PILImage.new("RGB", (1080, 1920), (10, 10, 11)).save(backdrop_path)
            scenes_out.append(
                Scene(
                    duration_s=dur,
                    backdrop_path=str(backdrop_path),
                    voiceover_path=str(voiceover_path) if (voiceover_path and i == 0) else None,
                    on_screen_text=s.get("on_screen_text", ""),
                    cta=script.get("cta", "") if i == len(script.get("scenes", [])) - 1 else "",
                )
            )

        emit(job.id, status="rendering", message="ffmpeg compose…")
        out_path = td_path / "out.mp4"
        render_short_video(scenes_out, str(out_path))

        storage = get_storage()
        key = new_key(job.brand_id, "videos", "mp4")
        url = storage.write_file(key, str(out_path))

    return {
        "video_url": url,
        "script": script,
        "critic": {"passed": critic.passed, "scores": critic.scores, "total": critic.weighted_total},
        "scenes": len(script.get("scenes", [])),
    }

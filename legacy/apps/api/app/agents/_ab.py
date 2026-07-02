"""Shared A/B variant helpers.

Most specialist agents produce one drafted ContentItem with a single ContentVariant.
For A/B testing we want a second 'B' variant generated from the same context.

Strategy:
  • If OPENROUTER_API_KEY is set → ask the LLM for a second copy with a
    deliberately different hook + CTA but the same product / angle.
  • Otherwise → derive a deterministic B variant by swapping headline tone
    (statement → question) and CTA (action → curiosity).
"""
from __future__ import annotations

import json
from typing import Optional

from app.pipeline.llm_gateway import LLMTier, complete


def _swap_cta(cta: str) -> str:
    if not cta:
        return "Curious? Save this for later."
    low = cta.lower()
    if "shop" in low or "buy" in low:
        return "Worth a 60-second read."
    if "save" in low or "read" in low or "later" in low:
        return "Tap to shop today."
    return f"More like this — {cta}"


def make_b_variant_for_caption(
    *, brand_sport: str, brand_voice: str, angle: str, a_payload: dict,
) -> dict:
    """Returns a B-variant payload for caption-style content (static_post, carousel, email)."""
    from app.core.config import settings

    a_headline = (a_payload.get("headline") or a_payload.get("title") or a_payload.get("subject_line") or "")[:200]
    a_caption = (a_payload.get("caption") or "")[:400]
    a_cta = (a_payload.get("cta") or "")

    if settings.OPENROUTER_API_KEY:
        system = (
            f"You are writing a SECOND variant (B) for an A/B test for the {brand_sport} brand. "
            f"Voice: {brand_voice or 'clear and direct'}. "
            "It must differ from variant A in: opening hook (use a question or contrast), "
            "specific phrasing (no repeated 5+ word strings), and CTA tone (curiosity vs action). "
            "Same product, same angle, same length budget. "
            "Output ONLY JSON: {\"headline\": str, \"caption\": str, \"cta\": str}."
        )
        user = (
            f"Angle: {angle}\n"
            f"Variant A — headline: {a_headline}\n"
            f"Variant A — caption: {a_caption}\n"
            f"Variant A — cta: {a_cta}\n"
        )
        try:
            res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=500)
            data = res.json_data or json.loads(res.content)
            if isinstance(data, dict):
                merged = dict(a_payload)
                merged["headline"] = data.get("headline", a_headline)
                merged["caption"] = data.get("caption", a_caption)
                merged["cta"] = data.get("cta", _swap_cta(a_cta))
                return merged
        except Exception:
            pass

    # deterministic fallback
    merged = dict(a_payload)
    merged["headline"] = a_headline.rstrip(".!?") + "?"
    merged["caption"] = "Here's the question to ask first: " + (a_caption[:240])
    merged["cta"] = _swap_cta(a_cta)
    return merged


def make_b_variant_for_email(*, brand_sport: str, brand_voice: str, angle: str, a_payload: dict) -> dict:
    """Email-shaped B: different subject_line + preheader + CTA tone."""
    from app.core.config import settings

    a_subject = a_payload.get("subject_line") or ""
    a_pre = a_payload.get("preheader") or ""

    if settings.OPENROUTER_API_KEY:
        system = (
            f"You are writing a SECOND email variant (B) for an A/B subject-line test. "
            f"Brand sport: {brand_sport}. Voice: {brand_voice or 'clear, useful, non-hypey'}. "
            "Variant B must use a different angle (e.g. question vs statement, benefit vs curiosity), "
            "stay ≤ 60 chars on subject_line, ≤ 90 on preheader. "
            "Output ONLY JSON: {\"subject_line\": str, \"preheader\": str, \"cta_text\": str}."
        )
        user = (
            f"Angle: {angle}\nVariant A subject: {a_subject}\nVariant A preheader: {a_pre}\n"
        )
        try:
            res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=400)
            data = res.json_data or json.loads(res.content)
            if isinstance(data, dict):
                merged = dict(a_payload)
                merged["subject_line"] = data.get("subject_line", a_subject)[:60]
                merged["preheader"] = data.get("preheader", a_pre)[:90]
                # find + replace the CTA block if present
                blocks = list(merged.get("blocks") or [])
                for b in blocks:
                    if isinstance(b, dict) and b.get("type") == "cta":
                        b["text"] = data.get("cta_text", b.get("text"))
                        break
                merged["blocks"] = blocks
                return merged
        except Exception:
            pass

    # deterministic
    merged = dict(a_payload)
    merged["subject_line"] = (a_subject.rstrip(".!?") + "?")[:60]
    merged["preheader"] = ("Quick read — " + (a_pre or angle))[:90]
    return merged


def make_b_variant_for_blog(*, brand_sport: str, brand_voice: str, angle: str, a_payload: dict) -> dict:
    """Blog B: different title + meta_description (same body — we're A/B testing
    the SEO/click bait, not the body)."""
    from app.core.config import settings

    a_title = a_payload.get("title") or ""
    a_meta = a_payload.get("meta_description") or ""

    if settings.OPENROUTER_API_KEY:
        system = (
            f"You are writing a SECOND blog title (B) for a CTR test. "
            f"Brand sport: {brand_sport}. "
            "Variant B must use a clearly different framing (e.g. numbered list vs how-to). "
            "Output ONLY JSON: {\"title\": str (≤90 chars), \"meta_description\": str (≤155 chars)}."
        )
        user = f"Angle: {angle}\nVariant A title: {a_title}\nVariant A meta: {a_meta}\n"
        try:
            res = complete(tier=LLMTier.DRAFTING, system=system, user=user, json_mode=True, max_tokens=350)
            data = res.json_data or json.loads(res.content)
            if isinstance(data, dict):
                merged = dict(a_payload)
                merged["title"] = data.get("title", a_title)[:90]
                merged["meta_description"] = data.get("meta_description", a_meta)[:155]
                return merged
        except Exception:
            pass

    # deterministic
    merged = dict(a_payload)
    base = a_title or angle
    merged["title"] = (f"5 things to know about {base.lower()}")[:90]
    merged["meta_description"] = (a_meta or base)[:155]
    return merged

"""Critic v2 (spec § 6.12) — LLM-backed rubric over a ContentItem.

This is the agent we call right after any specialist agent finishes a draft.
It enforces the cross-sport hard gate at the regex layer FIRST (cheap, deterministic)
and only then calls the LLM for nuanced scoring. Result is persisted as a
CriticReview row tied to the ContentItem.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import render_cross_sport_clause
from app.agents.critic import CRITERIA, PASS_THRESHOLD, hard_cross_sport_check
from app.models.brand import Brand, BrandBrain
from app.models.content import ContentItem, CriticReview
from app.pipeline.llm_gateway import LLMTier, complete


def _flatten_payload(payload: dict) -> str:
    """Reduce a content payload to one big string for the critic to read."""
    parts: list[str] = []

    def walk(node):
        if isinstance(node, str):
            parts.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    return " ".join(parts)[:4000]


def _fallback_scores(text: str, brain: BrandBrain | None) -> dict:
    scores = {k: 75 for k, _ in CRITERIA}
    # quick heuristic boosts/penalties
    if any(w in text.lower() for w in ["buy now", "shop", "→", "limited"]):
        scores["cta_strength"] = 85
    if brain and brain.seo_keywords:
        kw = {k.lower() for k in brain.seo_keywords}
        if any(k in text.lower() for k in kw):
            scores["brand_fit"] = 88
    return scores


def critic_review(
    db: Session,
    *,
    content_item_id: uuid.UUID,
    persist: bool = True,
) -> dict:
    from app.core.config import settings

    item = db.get(ContentItem, content_item_id)
    if item is None:
        raise ValueError("content_item not found")
    brand = db.get(Brand, item.brand_id)
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == item.brand_id)).scalar_one_or_none()
    text = _flatten_payload(item.payload or {})

    # hard gate
    cross_issues = hard_cross_sport_check(text)
    if cross_issues:
        scores = {k: 0 for k, _ in CRITERIA}
        review = {
            "scores": scores,
            "weighted_total": 0.0,
            "passed": False,
            "blocking_issues": cross_issues,
            "fixes": ["remove cross-sport references"],
            "reviewer": "ai",
        }
    else:
        if not settings.OPENROUTER_API_KEY:
            scores = _fallback_scores(text, brain)
            fixes: list[str] = []
        else:
            system = (
                render_cross_sport_clause(sport=brand.sport, brand_name=brand.name)
                + "\nYou are the Creative Critic. Score the content on each criterion 0–100.\n"
                + "Criteria with weights:\n"
                + "\n".join([f"  • {k} (w={w})" for k, w in CRITERIA])
                + "\nOutput ONLY JSON: {\"scores\": {criterion: int, ...}, \"blocking_issues\": [str], \"fixes\": [str], \"notes\": str}.\n"
                + "blocking_issues are show-stoppers (banned claim, off-brand voice, factual error).\n"
                + "fixes are short, actionable rewrites (1 line each)."
            )
            voice = (brain.voice if brain else "") or ""
            banned = ", ".join(brain.banned_phrases if (brain and brain.banned_phrases) else [])
            user = (
                f"Brand: {brand.name} (sport={brand.sport})\nVoice: {voice}\nBanned phrases: {banned}\n\n"
                f"Content payload:\n{text}\n"
            )
            try:
                res = complete(tier=LLMTier.REASONING, system=system, user=user, json_mode=True, max_tokens=1500)
                data = res.json_data or json.loads(res.content)
                raw_scores = data.get("scores") or {}
                scores = {k: int(raw_scores.get(k, 70)) for k, _ in CRITERIA}
                fixes = list(data.get("fixes") or [])
                cross_issues = list(data.get("blocking_issues") or [])
            except Exception:
                scores = _fallback_scores(text, brain)
                fixes = []
        weighted = sum(scores[k] * w for k, w in CRITERIA) / sum(w for _, w in CRITERIA)
        review = {
            "scores": scores,
            "weighted_total": round(weighted, 2),
            "passed": weighted >= PASS_THRESHOLD and not cross_issues,
            "blocking_issues": cross_issues,
            "fixes": fixes,
            "reviewer": "ai",
        }

    if persist:
        cr = CriticReview(
            content_item_id=content_item_id,
            scores=review["scores"],
            weighted_total=review["weighted_total"],
            passed=review["passed"],
            blocking_issues=review["blocking_issues"],
            fixes=review["fixes"],
            reviewer=review["reviewer"],
        )
        db.add(cr)
        # auto-transition drafted → under_review on first review
        if item.status == "drafted":
            item.status = "under_review"
        db.commit()
        review["review_id"] = str(cr.id)

    return review

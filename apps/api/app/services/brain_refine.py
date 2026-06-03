"""Brand-brain refinement loop (spec § 21).

Look at top-performing content in the last N days, extract:
  • the most-used non-stopword keywords  → propose for seo_keywords
  • CTAs that appear in winners          → log as voice exemplars
  • platforms over-indexed in winners    → suggest content-mix shifts
  • banned-phrase regressions            → flag if any winners contain banned

Returns a "Proposals" object the UI can show in the Brand Brain page with
one-click accept buttons.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.brand import BrandBrain
from app.models.content import ContentItem
from app.models.publishing import ContentPerformance


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "for", "to", "in", "on", "at",
    "with", "from", "by", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "as", "it", "its", "into", "your", "you",
    "we", "our", "they", "them", "their", "i", "me", "my", "have", "has", "had",
    "do", "does", "did", "will", "would", "can", "could", "should", "if",
    "than", "then", "so", "not", "no", "more", "most", "other", "another",
    "about", "over", "under", "out", "up", "down", "what", "how", "why", "when",
    "all", "some", "any", "best", "vs", "via", "use", "using", "get", "got",
    "one", "two", "three", "five", "ten", "new", "old", "now", "first", "last",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z]{3,}", (text or "").lower()) if t not in STOPWORDS]


def _flatten_payload(payload: dict) -> str:
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
    return " ".join(parts)


def propose_refinements(
    db: Session,
    *,
    brand_id: uuid.UUID,
    days: int = 30,
    min_engagement: int = 1,
    top_keywords: int = 12,
) -> dict:
    """Returns proposals + the data the proposals were derived from."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = list(
        db.execute(
            select(ContentPerformance, ContentItem)
            .join(ContentItem, ContentItem.id == ContentPerformance.content_item_id)
            .where(ContentItem.brand_id == brand_id)
            .where(ContentPerformance.created_at >= since)
            .order_by(desc(ContentPerformance.engagements))
            .limit(50)
        ).all()
    )

    if not rows:
        return {
            "days": days,
            "winners_analyzed": 0,
            "proposals": {"add_seo_keywords": [], "voice_exemplars": [], "channel_mix_shift": {}, "banned_regressions": []},
        }

    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    existing_seo = {k.lower() for k in (brain.seo_keywords or []) if isinstance(k, str)} if brain else set()
    banned = {b.lower() for b in (brain.banned_phrases or []) if isinstance(b, str)} if brain else set()

    keyword_counter: Counter[str] = Counter()
    channel_counter: Counter[str] = Counter()
    voice_lines: list[str] = []
    banned_regressions: list[dict] = []
    winners = 0

    for perf, item in rows:
        if (perf.engagements or 0) < min_engagement:
            continue
        winners += 1
        text = _flatten_payload(item.payload or {})
        for tok in _tokens(text):
            if tok in existing_seo:
                continue
            keyword_counter[tok] += 1
        channel_counter[item.platform] += 1
        # collect 1 voice exemplar per winning item: prefer caption / cta
        for k in ("cta", "caption", "headline"):
            v = (item.payload or {}).get(k)
            if isinstance(v, str) and v and len(v) < 200:
                voice_lines.append(v.strip())
                break
        # banned regression check
        lower = text.lower()
        hits = [b for b in banned if b in lower]
        if hits:
            banned_regressions.append({"content_item_id": str(item.id), "banned": hits})

    proposed = [k for k, _ in keyword_counter.most_common(top_keywords)]
    voice_dedup = list(dict.fromkeys(voice_lines))[:8]
    channel_mix = {
        p: round((c / max(1, winners)) * 100.0, 1) for p, c in channel_counter.most_common()
    }

    return {
        "days": days,
        "winners_analyzed": winners,
        "proposals": {
            "add_seo_keywords": proposed,
            "voice_exemplars": voice_dedup,
            "channel_mix_shift": channel_mix,
            "banned_regressions": banned_regressions,
        },
    }


def accept_seo_proposals(db: Session, brand_id: uuid.UUID, keywords: list[str]) -> dict:
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if brain is None:
        brain = BrandBrain(brand_id=brand_id)
        db.add(brain)
    existing = list(brain.seo_keywords or [])
    existing_set = {k.lower() for k in existing if isinstance(k, str)}
    added: list[str] = []
    for k in keywords:
        if k.lower() not in existing_set and k.strip():
            existing.append(k.strip())
            added.append(k.strip())
    brain.seo_keywords = existing
    db.commit()
    return {"added": added, "total": len(existing)}

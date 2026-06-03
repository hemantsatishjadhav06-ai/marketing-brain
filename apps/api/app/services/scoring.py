"""Scoring engine (spec § 9).

Produces a normalised 0–100 score per content idea from six signals:

    trend_lift          — recency-weighted Trend rows matching the idea's keywords
    evergreen_value     — does the angle stay relevant > 30 days?
    business_value      — is a product attached, and what's its margin tier?
    inventory_relevance — pushed by is_dead_stock / is_bestseller / is_new flags
    brand_fit           — keyword overlap with brand_brain.seo_keywords + voice cues
    risk_penalty        — banned_phrases + taboo claims subtract here

The exact weights are defined here so the UI can render the breakdown.

This module is deliberately framework-free (pure functions over the SQLAlchemy
session). Agents call into it; the scoring router exposes it.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import BrandBrain
from app.models.intelligence import ScoringRun, Trend
from app.models.products import Product


# ─── weights ──────────────────────────────────────────────────────────────────
WEIGHTS = {
    "trend_lift": 25,
    "evergreen_value": 15,
    "business_value": 20,
    "inventory_relevance": 15,
    "brand_fit": 15,
    "risk_penalty": -10,  # subtractive
}
ASSERTED_TOTAL_WEIGHT = sum(abs(w) for w in WEIGHTS.values())  # = 100


@dataclass
class ScoreBreakdown:
    trend_lift: float = 0.0
    evergreen_value: float = 0.0
    business_value: float = 0.0
    inventory_relevance: float = 0.0
    brand_fit: float = 0.0
    risk_penalty: float = 0.0
    total: float = 0.0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "trend_lift": round(self.trend_lift, 2),
            "evergreen_value": round(self.evergreen_value, 2),
            "business_value": round(self.business_value, 2),
            "inventory_relevance": round(self.inventory_relevance, 2),
            "brand_fit": round(self.brand_fit, 2),
            "risk_penalty": round(self.risk_penalty, 2),
            "total": round(self.total, 2),
            "notes": self.notes,
        }


# ─── individual signals ───────────────────────────────────────────────────────
def _tokens(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text or "")}


def score_trend_lift(db: Session, brand_id: uuid.UUID, keywords: Iterable[str]) -> tuple[float, list[str]]:
    """0–100. Newer trends with higher signal_strength weigh more.

    Decay: linear over 30 days. signal_strength is assumed in [0, 100].
    """
    kw = {k.lower() for k in keywords if k}
    if not kw:
        return 0.0, ["no keywords"]
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Trend).where(Trend.brand_id == brand_id).order_by(Trend.captured_at.desc()).limit(500)
    ).scalars().all()
    if not rows:
        return 30.0, ["no trend rows — using neutral baseline 30"]
    hits: list[float] = []
    matched: list[str] = []
    for t in rows:
        text = f"{t.topic} {t.keyword}".lower()
        if any(k in text for k in kw):
            age_days = (now - t.captured_at).total_seconds() / 86400.0
            recency = max(0.0, 1.0 - age_days / 30.0)
            slope_boost = 1.0 + max(0.0, min(float(t.slope), 1.0))
            hits.append(float(t.signal_strength) * recency * slope_boost)
            matched.append(t.topic)
    if not hits:
        return 15.0, ["keywords didn't match any captured trend"]
    raw = sum(hits) / len(hits)
    return min(100.0, raw), [f"matched {len(hits)} trends: {', '.join(matched[:3])}"]


def score_evergreen_value(angle: str, content_type: str) -> tuple[float, list[str]]:
    """How long the idea stays relevant. Educational > seasonal > news."""
    a = (angle or "").lower()
    if any(k in a for k in ["how to", "guide", "explain", "beginner", "tutorial", "fundamentals"]):
        return 90.0, ["evergreen tutorial framing"]
    if any(k in a for k in ["news", "breaking", "announcement", "release", "live"]):
        return 25.0, ["news framing — short shelf life"]
    if content_type in {"blog", "youtube_short", "youtube_long"}:
        return 70.0, ["long-form / SEO surface = naturally evergreen"]
    return 55.0, ["mid-shelf-life social content"]


def score_business_value(products: list[Product]) -> tuple[float, list[str]]:
    """Margin-weighted. No product attached = 50 (informational still has value)."""
    if not products:
        return 50.0, ["no product attached — informational"]
    margins = [float(p.margin or 0) for p in products]
    avg_margin = sum(margins) / max(1, len(margins))
    raw = min(100.0, (avg_margin / 200.0) * 100.0)
    return raw, [f"avg margin ${avg_margin:.0f} across {len(products)} product(s)"]


def score_inventory_relevance(products: list[Product]) -> tuple[float, list[str]]:
    """is_dead_stock pushes UP (we want to move it). is_new is medium-high."""
    if not products:
        return 40.0, ["no product → neutral inventory signal"]
    score = 0.0
    notes: list[str] = []
    for p in products:
        if p.is_dead_stock:
            score = max(score, 95.0)
            notes.append(f"{p.sku}: DEAD STOCK — high push priority")
        elif p.is_discounted:
            score = max(score, 80.0)
            notes.append(f"{p.sku}: discounted — convert urgency")
        elif p.is_bestseller:
            score = max(score, 75.0)
            notes.append(f"{p.sku}: bestseller — sustaining momentum")
        elif p.is_new:
            score = max(score, 70.0)
            notes.append(f"{p.sku}: new launch")
        else:
            score = max(score, 50.0)
    return score, notes


def score_brand_fit(angle: str, title: str, brain: BrandBrain | None) -> tuple[float, list[str]]:
    """Keyword overlap with brand_brain.seo_keywords. 50 is neutral baseline."""
    if not brain or not brain.seo_keywords:
        return 50.0, ["no brand_brain.seo_keywords configured — neutral"]
    seo = {k.lower() for k in brain.seo_keywords if isinstance(k, str)}
    text_tokens = _tokens(f"{title} {angle}")
    overlap = seo & text_tokens
    if not overlap:
        return 35.0, [f"no overlap with {len(seo)} brand keywords"]
    raw = min(100.0, 50.0 + 10.0 * len(overlap))
    return raw, [f"hits brand keywords: {', '.join(sorted(overlap))[:120]}"]


def score_risk_penalty(angle: str, title: str, brain: BrandBrain | None) -> tuple[float, list[str]]:
    """Returns a POSITIVE number in [0, 100] representing penalty magnitude.

    Combined later via weight = -10 so 100 here = -10 to total.
    """
    if not brain or not brain.banned_phrases:
        return 0.0, []
    banned = {b.lower() for b in brain.banned_phrases if isinstance(b, str)}
    text = f"{title} {angle}".lower()
    hits = [b for b in banned if b in text]
    if not hits:
        return 0.0, []
    return min(100.0, 30.0 * len(hits)), [f"banned phrases: {', '.join(hits)}"]


# ─── orchestrator ─────────────────────────────────────────────────────────────
def score_idea(
    db: Session,
    *,
    brand_id: uuid.UUID,
    title: str,
    angle: str,
    content_type: str,
    keywords: list[str],
    products: list[Product],
    brain: BrandBrain | None,
) -> ScoreBreakdown:
    """Returns a 0–100 total + per-signal breakdown + notes."""
    out = ScoreBreakdown()

    tl, n1 = score_trend_lift(db, brand_id, keywords)
    ev, n2 = score_evergreen_value(angle, content_type)
    bv, n3 = score_business_value(products)
    ir, n4 = score_inventory_relevance(products)
    bf, n5 = score_brand_fit(angle, title, brain)
    rp, n6 = score_risk_penalty(angle, title, brain)

    out.trend_lift, out.evergreen_value = tl, ev
    out.business_value, out.inventory_relevance = bv, ir
    out.brand_fit, out.risk_penalty = bf, rp

    pos = tl * WEIGHTS["trend_lift"] + ev * WEIGHTS["evergreen_value"] + bv * WEIGHTS["business_value"] \
        + ir * WEIGHTS["inventory_relevance"] + bf * WEIGHTS["brand_fit"]
    neg = rp * abs(WEIGHTS["risk_penalty"])
    total = (pos - neg) / ASSERTED_TOTAL_WEIGHT
    out.total = max(0.0, min(100.0, total))
    out.notes = [*n1, *n2, *n3, *n4, *n5, *n6]
    return out


def persist_run(
    db: Session,
    *,
    brand_id: uuid.UUID,
    subject_type: str,
    subject_id: uuid.UUID,
    breakdown: ScoreBreakdown,
    inputs: dict,
) -> ScoringRun:
    run = ScoringRun(
        brand_id=brand_id,
        subject_type=subject_type,
        subject_id=subject_id,
        score_type="content",
        total=breakdown.total,
        breakdown=breakdown.as_dict(),
        inputs=inputs,
    )
    db.add(run)
    return run

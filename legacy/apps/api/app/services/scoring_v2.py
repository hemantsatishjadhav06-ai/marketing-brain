"""Scoring engines per spec § 10 — four engines, explicit weights.

This sits alongside the simpler `services/scoring.py` from v0.1. The old engine
is still used as a fast composite when you just need one number for an idea.
This module exposes the four canonical engines the spec describes, so the
calendar / orchestrator can reason in the same units as the spec doc.

Engines:
  10.1 product_demand_score   — per Product
  10.2 trend_score            — per topic/keyword in a brand
  10.3 audience_likelihood    — per (platform, content_type) for a brand
  10.4 content_priority       — final priority for a ContentIdea / CalendarEntry
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.brand import BrandBrain
from app.models.content import ContentIdea
from app.models.intelligence import Trend
from app.models.products import Product
from app.models.publishing import ContentPerformance


# ─── 10.1 Product Demand Score weights ────────────────────────────────────────
DEMAND_WEIGHTS = {
    "sales_velocity_norm":         0.30,
    "search_demand_norm":          0.20,
    "inventory_urgency":           0.15,
    "margin_norm":                 0.15,
    "seasonality_fit":             0.10,
    "newness_or_bestseller_flag":  0.10,
}
assert abs(sum(DEMAND_WEIGHTS.values()) - 1.0) < 1e-9

# ─── 10.2 Trend Score weights ─────────────────────────────────────────────────
TREND_WEIGHTS = {
    "search_trend_slope":      0.35,
    "social_trend_strength":   0.25,
    "event_proximity":         0.20,
    "competitor_activity":     0.20,
}
assert abs(sum(TREND_WEIGHTS.values()) - 1.0) < 1e-9

# ─── 10.3 Audience Likelihood Score weights ───────────────────────────────────
AUDIENCE_WEIGHTS = {
    "platform_affinity":              0.40,
    "topic_interest_match":           0.30,
    "historical_engagement_similar":  0.30,
}
assert abs(sum(AUDIENCE_WEIGHTS.values()) - 1.0) < 1e-9

# ─── 10.4 Content Priority weights ────────────────────────────────────────────
CONTENT_PRIORITY_WEIGHTS = {
    "product_demand":      0.30,
    "trend":               0.25,
    "audience_likelihood": 0.20,
    "business_goal_fit":   0.15,
    "reusability":         0.10,
}
assert abs(sum(CONTENT_PRIORITY_WEIGHTS.values()) - 1.0) < 1e-9


@dataclass
class Score:
    total: float
    breakdown: dict
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"total": round(self.total, 2), "breakdown": self.breakdown, "notes": self.notes}


# ─── 10.1 Product Demand Score ────────────────────────────────────────────────
def product_demand_score(db: Session, product: Product) -> Score:
    # sales_velocity_norm — no events table yet; fall back to bestseller flag * 80
    sales = 80.0 if product.is_bestseller else (40.0 if product.is_new else 30.0)
    # search_demand_norm — proxy via brand trends for any kw in product.title
    search = _search_demand_norm(db, product.brand_id, product.title)
    # inventory_urgency
    inv = 95.0 if product.is_dead_stock else (75.0 if product.is_discounted else 35.0)
    # margin_norm — clamp $0..$200 to 0..100
    margin = min(100.0, (float(product.margin or 0) / 200.0) * 100.0)
    # seasonality_fit — TODO real seasonal cal; neutral for now
    season = 50.0
    # newness_or_bestseller_flag — 90 if either flag is true else 30
    flag = 90.0 if (product.is_new or product.is_bestseller) else 30.0

    breakdown = {
        "sales_velocity_norm": round(sales, 2),
        "search_demand_norm": round(search, 2),
        "inventory_urgency": round(inv, 2),
        "margin_norm": round(margin, 2),
        "seasonality_fit": round(season, 2),
        "newness_or_bestseller_flag": round(flag, 2),
    }
    total = sum(breakdown[k] * w for k, w in DEMAND_WEIGHTS.items())
    return Score(total=total, breakdown=breakdown, notes=[
        f"product {product.sku}: dead_stock={product.is_dead_stock} bestseller={product.is_bestseller} new={product.is_new}",
    ])


def _search_demand_norm(db: Session, brand_id: uuid.UUID, text: str) -> float:
    if not text:
        return 20.0
    tokens = {w.lower() for w in text.split() if len(w) > 2}
    if not tokens:
        return 20.0
    rows = db.execute(
        select(Trend).where(Trend.brand_id == brand_id).order_by(desc(Trend.captured_at)).limit(200)
    ).scalars().all()
    matched = [float(t.signal_strength) for t in rows if any(k in (t.topic + " " + t.keyword).lower() for k in tokens)]
    if not matched:
        return 25.0
    return min(100.0, sum(matched) / len(matched))


# ─── 10.2 Trend Score ─────────────────────────────────────────────────────────
def trend_score(db: Session, brand_id: uuid.UUID, keywords: Iterable[str]) -> Score:
    kw = {k.lower() for k in keywords if k}
    rows = db.execute(
        select(Trend).where(Trend.brand_id == brand_id).order_by(desc(Trend.captured_at)).limit(300)
    ).scalars().all()

    matched = [t for t in rows if any(k in (t.topic + " " + t.keyword).lower() for k in kw)]
    if not matched:
        return Score(total=20.0, breakdown={
            "search_trend_slope": 20.0, "social_trend_strength": 20.0,
            "event_proximity": 20.0, "competitor_activity": 20.0,
        }, notes=["no matched trends → neutral baseline"])

    search_slope = sum(min(100.0, max(0.0, float(t.slope) * 100.0)) for t in matched) / len(matched)
    social_strength = sum(float(t.signal_strength) for t in matched if t.source in ("reddit", "twitter", "youtube")) / max(1, len([t for t in matched if t.source in ("reddit", "twitter", "youtube")]))
    competitor = sum(float(t.signal_strength) for t in matched if t.source == "competitor") / max(1, len([t for t in matched if t.source == "competitor"]))
    event_proximity = 50.0   # TODO real sports-calendar; neutral until § 11 events table lands

    breakdown = {
        "search_trend_slope":    round(search_slope, 2),
        "social_trend_strength": round(social_strength, 2),
        "event_proximity":       round(event_proximity, 2),
        "competitor_activity":   round(competitor, 2),
    }
    total = sum(breakdown[k] * w for k, w in TREND_WEIGHTS.items())
    return Score(total=total, breakdown=breakdown, notes=[f"matched {len(matched)} trend rows"])


# ─── 10.3 Audience Likelihood Score ───────────────────────────────────────────
def audience_likelihood(
    db: Session, brand_id: uuid.UUID, *, platform: str, content_type: str, angle: str
) -> Score:
    # platform_affinity — TODO read from Audience.affinity_scores; neutral until UI is wired
    aff = 70.0
    # topic_interest_match — does the angle contain any seo_keyword?
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    seo = {k.lower() for k in ((brain.seo_keywords if brain else []) or []) if isinstance(k, str)}
    topic = 80.0 if any(k in angle.lower() for k in seo) else 45.0
    # historical_engagement_similar — average engagement on past items of same platform+content_type
    since = datetime.now(timezone.utc) - timedelta(days=60)
    rows = db.execute(
        select(ContentPerformance).where(ContentPerformance.created_at >= since)
    ).scalars().all()
    hist = sum(float(p.score or 0) for p in rows) / len(rows) if rows else 50.0
    hist = min(100.0, hist)

    breakdown = {
        "platform_affinity": round(aff, 2),
        "topic_interest_match": round(topic, 2),
        "historical_engagement_similar": round(hist, 2),
    }
    total = sum(breakdown[k] * w for k, w in AUDIENCE_WEIGHTS.items())
    return Score(total=total, breakdown=breakdown, notes=[f"platform={platform} type={content_type}"])


# ─── 10.4 Content Priority — combines all three ───────────────────────────────
def content_priority(
    db: Session,
    *,
    brand_id: uuid.UUID,
    title: str,
    angle: str,
    platform: str,
    content_type: str,
    keywords: list[str],
    products: list[Product],
    business_goal_fit: float = 60.0,
    reusability: float = 60.0,
) -> Score:
    # use highest demand from attached products (0 if none)
    pd = max((product_demand_score(db, p).total for p in products), default=50.0)
    tr = trend_score(db, brand_id, keywords or [angle]).total
    au = audience_likelihood(db, brand_id, platform=platform, content_type=content_type, angle=angle).total

    breakdown = {
        "product_demand":      round(pd, 2),
        "trend":               round(tr, 2),
        "audience_likelihood": round(au, 2),
        "business_goal_fit":   round(business_goal_fit, 2),
        "reusability":         round(reusability, 2),
    }
    total = sum(breakdown[k] * w for k, w in CONTENT_PRIORITY_WEIGHTS.items())
    return Score(total=total, breakdown=breakdown, notes=[
        f"4-engine score: demand={pd:.0f} · trend={tr:.0f} · audience={au:.0f}",
    ])

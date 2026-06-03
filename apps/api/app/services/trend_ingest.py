"""Trend ingestion (Phase 3) — pulls signals into the Trend table.

Two real sources:
  • Reddit JSON (no auth needed for /r/<sub>/hot.json) → reddit_hot
  • Google Trends daily-trending RSS                  → google_trends_daily

Both are intentionally dumb: they hit a public endpoint, parse, and persist.
The scoring engine reads from `Trend.signal_strength` + `Trend.slope` so the
output shape is unified.

Configure per brand via brand_brain:
  • brand_brain.geo_prompts    = ["US", "IN", "GB"]       (Google Trends geos)
  • brand_brain.competitors    = ["r/tennis", "r/10s"]    (subreddits, with or without r/)
"""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import Brand, BrandBrain
from app.models.intelligence import Trend


REDDIT_UA = "marketing-brain/0.3 (trend-ingest)"


# ─── Reddit ───────────────────────────────────────────────────────────────────
def _normalise_sub(s: str) -> str:
    s = s.strip()
    if s.startswith("https://www.reddit.com/r/"):
        s = s.removeprefix("https://www.reddit.com/r/").split("/")[0]
    return s.removeprefix("r/").removeprefix("/r/")


def ingest_reddit_hot(db: Session, brand_id: uuid.UUID, subs: Iterable[str], limit: int = 25) -> dict:
    now = datetime.now(timezone.utc)
    persisted = 0
    for sub in subs:
        s = _normalise_sub(sub)
        if not s:
            continue
        url = f"https://www.reddit.com/r/{s}/hot.json?limit={limit}"
        try:
            with httpx.Client(timeout=20, headers={"User-Agent": REDDIT_UA}) as c:
                r = c.get(url)
                if r.status_code != 200:
                    continue
                data = r.json()
        except (httpx.HTTPError, ValueError):
            continue
        max_score = 1
        for child in data.get("data", {}).get("children", []):
            max_score = max(max_score, int(child.get("data", {}).get("score") or 0))
        for child in data.get("data", {}).get("children", [])[:limit]:
            d = child.get("data", {}) or {}
            score = int(d.get("score") or 0)
            signal = min(100.0, (score / max_score) * 100.0)
            num_comments = int(d.get("num_comments") or 0)
            slope = min(1.0, num_comments / 200.0)
            db.add(
                Trend(
                    brand_id=brand_id,
                    source="reddit",
                    topic=(d.get("title") or "")[:255],
                    keyword=(d.get("link_flair_text") or s)[:255],
                    signal_strength=signal,
                    slope=slope,
                    payload={
                        "sub": s,
                        "url": d.get("url"),
                        "score": score,
                        "comments": num_comments,
                        "permalink": d.get("permalink"),
                    },
                    captured_at=now,
                )
            )
            persisted += 1
    db.commit()
    return {"source": "reddit", "trends_persisted": persisted}


# ─── Google Trends daily RSS ──────────────────────────────────────────────────
def _google_trends_url(geo: str) -> str:
    return f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"


def ingest_google_trends(db: Session, brand_id: uuid.UUID, geos: Iterable[str]) -> dict:
    now = datetime.now(timezone.utc)
    persisted = 0
    for geo in geos:
        geo = geo.strip().upper()
        if not geo:
            continue
        try:
            with httpx.Client(timeout=20, headers={"User-Agent": REDDIT_UA}) as c:
                r = c.get(_google_trends_url(geo))
                if r.status_code != 200:
                    continue
                root = ET.fromstring(r.text)
        except (httpx.HTTPError, ET.ParseError):
            continue
        ns = {"ht": "https://trends.google.com/trending/rss"}
        items = root.findall(".//item")
        for it in items:
            title = (it.findtext("title") or "").strip()
            traffic_el = it.find("ht:approx_traffic", ns)
            traffic_str = (traffic_el.text if traffic_el is not None else "0").lower()
            m = re.match(r"([\d,]+)\+?", traffic_str)
            traffic = int(m.group(1).replace(",", "")) if m else 0
            # cap to 100; 1M+ = 100
            signal = min(100.0, (traffic / 1_000_000.0) * 100.0)
            db.add(
                Trend(
                    brand_id=brand_id,
                    source="google_trends",
                    topic=title[:255],
                    keyword=geo,
                    signal_strength=signal,
                    slope=0.5,  # we don't have a slope from this feed
                    payload={"geo": geo, "approx_traffic": traffic_str},
                    captured_at=now,
                )
            )
            persisted += 1
    db.commit()
    return {"source": "google_trends", "trends_persisted": persisted}


# ─── Brain-driven aggregator ──────────────────────────────────────────────────
def ingest_all_for_brand(db: Session, brand_id: uuid.UUID) -> dict:
    brand = db.get(Brand, brand_id)
    if not brand:
        raise ValueError("brand not found")
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    subs = (brain.competitors if brain else None) or []
    # default geos: just the brand's region inference (US/IN good defaults)
    geos = (brain.geo_prompts if brain else None) or ["US"]
    out = {"brand_id": str(brand_id), "results": []}
    if subs:
        out["results"].append(ingest_reddit_hot(db, brand_id, subs))
    out["results"].append(ingest_google_trends(db, brand_id, geos))
    return out

"""Analytics — performance ingestion (CSV / manual) + dashboards.

Phase 2: manual + CSV ingestion. Phase 3 swaps in per-platform pulls
(Meta Graph, GA4, X analytics, YouTube Analytics, Klaviyo, etc.) behind
the same endpoint shape so the UI doesn't change.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.publishing import AnalyticsEvent, ContentPerformance
from app.models.tenancy import User

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


class PerfIn(BaseModel):
    content_item_id: uuid.UUID
    impressions: int = 0
    engagements: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0
    period: str = "rolling_7d"


def _engagement_rate(p: dict | ContentPerformance) -> float:
    if isinstance(p, dict):
        imp = p.get("impressions", 0); eng = p.get("engagements", 0)
    else:
        imp, eng = p.impressions, p.engagements
    return round((eng / imp) * 100, 2) if imp else 0.0


@router.post("/{brand_id}/analytics/perf")
def ingest_perf(
    brand_id: uuid.UUID,
    body: PerfIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    item = db.get(ContentItem, body.content_item_id)
    if not item or item.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "content_item not found in brand")
    perf = ContentPerformance(
        content_item_id=body.content_item_id,
        impressions=body.impressions,
        engagements=body.engagements,
        clicks=body.clicks,
        conversions=body.conversions,
        revenue=body.revenue,
        score=_engagement_rate(body.model_dump()),
        period=body.period,
    )
    db.add(perf)
    db.commit()
    return {"id": str(perf.id), "score": float(perf.score)}


@router.post("/{brand_id}/analytics/perf/csv", status_code=status.HTTP_201_CREATED)
async def ingest_perf_csv(
    brand_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """CSV columns: content_item_id, impressions, engagements, clicks, conversions, revenue."""
    _brand_or_404(db, brand_id, user)
    raw = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    count = 0
    for row in reader:
        try:
            cid = uuid.UUID(row["content_item_id"])
        except Exception:
            continue
        item = db.get(ContentItem, cid)
        if not item or item.brand_id != brand_id:
            continue
        p = ContentPerformance(
            content_item_id=cid,
            impressions=int(row.get("impressions") or 0),
            engagements=int(row.get("engagements") or 0),
            clicks=int(row.get("clicks") or 0),
            conversions=int(row.get("conversions") or 0),
            revenue=float(row.get("revenue") or 0),
            period=row.get("period") or "rolling_7d",
        )
        p.score = _engagement_rate(p)
        db.add(p)
        count += 1
    db.commit()
    return {"rows_ingested": count}


@router.get("/{brand_id}/analytics/summary")
def summary(
    brand_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = list(
        db.execute(
            select(ContentPerformance, ContentItem)
            .join(ContentItem, ContentItem.id == ContentPerformance.content_item_id)
            .where(ContentItem.brand_id == brand_id)
            .where(ContentPerformance.created_at >= since)
        ).all()
    )
    totals = {"impressions": 0, "engagements": 0, "clicks": 0, "conversions": 0, "revenue": 0.0, "items": 0}
    by_platform: dict[str, dict] = {}
    top: list[dict] = []
    for perf, item in rows:
        totals["impressions"] += int(perf.impressions or 0)
        totals["engagements"] += int(perf.engagements or 0)
        totals["clicks"] += int(perf.clicks or 0)
        totals["conversions"] += int(perf.conversions or 0)
        totals["revenue"] += float(perf.revenue or 0)
        totals["items"] += 1
        b = by_platform.setdefault(item.platform, {"impressions": 0, "engagements": 0, "revenue": 0.0, "items": 0})
        b["impressions"] += int(perf.impressions or 0)
        b["engagements"] += int(perf.engagements or 0)
        b["revenue"] += float(perf.revenue or 0)
        b["items"] += 1
        top.append(
            {
                "content_item_id": str(item.id),
                "platform": item.platform,
                "content_type": item.content_type,
                "angle": item.angle,
                "impressions": int(perf.impressions or 0),
                "engagements": int(perf.engagements or 0),
                "revenue": float(perf.revenue or 0),
                "engagement_rate": float(perf.score or 0),
            }
        )
    top.sort(key=lambda r: r["engagements"], reverse=True)
    return {
        "totals": totals,
        "by_platform": by_platform,
        "top_content": top[:10],
        "days": days,
    }

"""Trends — manual ingest + list (per-brand)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.intelligence import Trend
from app.models.tenancy import User

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


class TrendIn(BaseModel):
    source: str = Field(..., max_length=64)  # google_trends|serp|youtube|competitor|manual
    topic: str = Field(..., max_length=255)
    keyword: str = Field("", max_length=255)
    signal_strength: float = Field(0.0, ge=0, le=100)
    slope: float = Field(0.0, ge=-1, le=1)
    payload: dict = Field(default_factory=dict)


class TrendsBatchIn(BaseModel):
    trends: list[TrendIn]


@router.get("/{brand_id}/trends")
def list_trends(
    brand_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    source: Optional[str] = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    q = select(Trend).where(Trend.brand_id == brand_id)
    if source:
        q = q.where(Trend.source == source)
    rows = db.execute(q.order_by(desc(Trend.captured_at)).limit(limit)).scalars().all()
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "topic": r.topic,
            "keyword": r.keyword,
            "signal_strength": float(r.signal_strength),
            "slope": float(r.slope),
            "captured_at": r.captured_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/{brand_id}/trends", status_code=status.HTTP_201_CREATED)
def ingest_trend(
    brand_id: uuid.UUID,
    body: TrendIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    t = Trend(
        brand_id=brand_id,
        source=body.source,
        topic=body.topic,
        keyword=body.keyword,
        signal_strength=body.signal_strength,
        slope=body.slope,
        payload=body.payload,
        captured_at=datetime.now(timezone.utc),
    )
    db.add(t)
    db.commit()
    return {"id": str(t.id)}


@router.post("/{brand_id}/trends/batch", status_code=status.HTTP_201_CREATED)
def ingest_trends_batch(
    brand_id: uuid.UUID,
    body: TrendsBatchIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    ids: list[str] = []
    now = datetime.now(timezone.utc)
    for tr in body.trends:
        t = Trend(
            brand_id=brand_id,
            source=tr.source,
            topic=tr.topic,
            keyword=tr.keyword,
            signal_strength=tr.signal_strength,
            slope=tr.slope,
            payload=tr.payload,
            captured_at=now,
        )
        db.add(t)
        db.flush()
        ids.append(str(t.id))
    db.commit()
    return {"created": len(ids), "ids": ids[:10]}

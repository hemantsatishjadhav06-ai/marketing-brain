"""Trend ingestion endpoints — kick off pulls manually or via scheduled job.

POST /brands/{brand_id}/trends/ingest         → all configured sources
POST /brands/{brand_id}/trends/ingest/reddit  → subreddits in body
POST /brands/{brand_id}/trends/ingest/google  → geos in body
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.tenancy import User
from app.services.trend_ingest import (
    ingest_all_for_brand,
    ingest_google_trends,
    ingest_reddit_hot,
)

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.post("/{brand_id}/trends/ingest")
def ingest_all(
    brand_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return ingest_all_for_brand(db, brand_id)


class RedditIngestIn(BaseModel):
    subreddits: list[str]
    limit: int = 25


@router.post("/{brand_id}/trends/ingest/reddit")
def ingest_reddit(
    brand_id: uuid.UUID,
    body: RedditIngestIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return ingest_reddit_hot(db, brand_id, body.subreddits, limit=body.limit)


class GoogleIngestIn(BaseModel):
    geos: list[str]


@router.post("/{brand_id}/trends/ingest/google")
def ingest_google(
    brand_id: uuid.UUID,
    body: GoogleIngestIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return ingest_google_trends(db, brand_id, body.geos)

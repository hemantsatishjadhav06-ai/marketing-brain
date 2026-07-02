"""Live analytics pull endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.tenancy import User
from app.services.analytics_pull import pull_ga4, pull_meta_insights

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


class GA4In(BaseModel):
    property_id: str
    access_token: str
    days: int = 7


@router.post("/{brand_id}/analytics/pull/ga4")
def pull_ga4_endpoint(
    brand_id: uuid.UUID,
    body: GA4In,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return pull_ga4(db, brand_id=brand_id, property_id=body.property_id, access_token=body.access_token, days=body.days)


class MetaIn(BaseModel):
    access_token: str


@router.post("/{brand_id}/analytics/pull/meta")
def pull_meta_endpoint(
    brand_id: uuid.UUID,
    body: MetaIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return pull_meta_insights(db, brand_id=brand_id, access_token=body.access_token)

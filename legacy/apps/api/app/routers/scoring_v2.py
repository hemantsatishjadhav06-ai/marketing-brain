"""Scoring v2 endpoints — exposes the 4 canonical engines from spec § 10."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_user
from app.models.brand import Brand, BrandBrain
from app.models.products import Product
from app.models.tenancy import User
from app.services.scoring_v2 import (
    audience_likelihood,
    content_priority,
    product_demand_score,
    trend_score,
)

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/{brand_id}/score/product/{product_id}")
def score_product(
    brand_id: uuid.UUID,
    product_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    prod = db.get(Product, product_id)
    if not prod or prod.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not in brand")
    return product_demand_score(db, prod).as_dict()


@router.get("/{brand_id}/score/trend")
def score_trend(
    brand_id: uuid.UUID,
    keywords: str = Query(..., description="comma-separated keywords"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    kw = [k.strip() for k in keywords.split(",") if k.strip()]
    return trend_score(db, brand_id, kw).as_dict()


@router.get("/{brand_id}/score/audience")
def score_audience(
    brand_id: uuid.UUID,
    platform: str = Query(...),
    content_type: str = Query(...),
    angle: str = Query(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return audience_likelihood(db, brand_id, platform=platform, content_type=content_type, angle=angle).as_dict()


@router.get("/{brand_id}/score/content_priority")
def score_content_priority(
    brand_id: uuid.UUID,
    title: str = Query(...),
    angle: str = Query(...),
    platform: str = Query(...),
    content_type: str = Query(...),
    keywords: str = Query(""),
    product_id: Optional[uuid.UUID] = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    products: list[Product] = []
    if product_id:
        p = db.get(Product, product_id)
        if p and p.brand_id == brand_id:
            products = [p]
    kw = [k.strip() for k in keywords.split(",") if k.strip()]
    return content_priority(
        db, brand_id=brand_id, title=title, angle=angle,
        platform=platform, content_type=content_type, keywords=kw, products=products,
    ).as_dict()

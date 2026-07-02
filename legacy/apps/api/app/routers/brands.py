"""Brands (sport verticals). Always brand_id-scoped."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.guards.no_cross_brand import CrossBrandViolation
from app.models.brand import Brand, BrandBrain, Sport
from app.models.tenancy import User
from app.schemas.brands import BrandCreateIn, BrandOut, BrandUpdateIn

router = APIRouter()

ACCENT_DEFAULTS = {
    "tennis": "#CCFF00",
    "padel": "#22D3EE",
    "pickleball": "#F59E0B",
    "badminton": "#A78BFA",
    "squash": "#EF4444",
}


def _own_brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return brand


@router.get("", response_model=List[BrandOut])
def list_brands(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Brand).where(Brand.org_id == user.org_id).order_by(Brand.sport)).scalars().all()
    return rows


@router.post("", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
def create_brand(
    payload: BrandCreateIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if payload.sport not in {s.value for s in Sport}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown sport")
    existing = db.execute(
        select(Brand).where(Brand.org_id == user.org_id, Brand.sport == payload.sport)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Brand for sport={payload.sport} already exists")
    brand = Brand(
        org_id=user.org_id,
        sport=payload.sport,
        name=payload.name,
        website_url=payload.website_url,
        timezone=payload.timezone,
        accent_color=payload.accent_color or ACCENT_DEFAULTS.get(payload.sport, "#CCFF00"),
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    # auto-create empty brand brain
    db.add(BrandBrain(brand_id=brand.id))
    db.commit()
    return brand


@router.get("/{brand_id}", response_model=BrandOut)
def get_brand(brand_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return _own_brand_or_404(db, brand_id, user)


@router.patch("/{brand_id}", response_model=BrandOut)
def update_brand(
    brand_id: uuid.UUID,
    payload: BrandUpdateIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    brand = _own_brand_or_404(db, brand_id, user)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(brand, k, v)
    db.commit()
    db.refresh(brand)
    return brand

"""Brand Brain — voice, tone, banned phrases, platform rules, SEO/GEO."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand, BrandBrain
from app.models.tenancy import User
from app.schemas.brands import BrandBrainOut, BrandBrainUpdateIn

router = APIRouter()


def _own_brand(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/{brand_id}/brain", response_model=BrandBrainOut)
def get_brain(brand_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    _own_brand(db, brand_id, user)
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if not brain:
        brain = BrandBrain(brand_id=brand_id)
        db.add(brain)
        db.commit()
        db.refresh(brain)
    return brain


@router.put("/{brand_id}/brain", response_model=BrandBrainOut)
def update_brain(
    brand_id: uuid.UUID,
    payload: BrandBrainUpdateIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _own_brand(db, brand_id, user)
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if not brain:
        brain = BrandBrain(brand_id=brand_id)
        db.add(brain)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(brain, k, v)
    db.commit()
    db.refresh(brain)
    return brain

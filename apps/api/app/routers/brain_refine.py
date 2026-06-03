"""Brand-brain refinement endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.tenancy import User
from app.services.brain_refine import accept_seo_proposals, propose_refinements

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/{brand_id}/brain/refinements")
def get_refinements(
    brand_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return propose_refinements(db, brand_id=brand_id, days=days)


class AcceptSeoIn(BaseModel):
    keywords: list[str]


@router.post("/{brand_id}/brain/refinements/accept-seo")
def accept_seo(
    brand_id: uuid.UUID,
    body: AcceptSeoIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return accept_seo_proposals(db, brand_id, body.keywords)

"""Repurpose router — POST /repurpose/{content_id}."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.repurpose import RepurposeAgent
from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.tenancy import User

router = APIRouter()


@router.post("/{content_id}")
def repurpose(
    content_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    item = db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    brand = db.get(Brand, item.brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    try:
        return RepurposeAgent().fan_out(db, content_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

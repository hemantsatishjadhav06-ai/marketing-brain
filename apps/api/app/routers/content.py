"""Content — list + state transitions. Bodies land in Phase 1."""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.content import ContentItem, ContentStatus
from app.models.tenancy import User

router = APIRouter()

VALID_TRANSITIONS = {
    "idea": {"drafted", "failed"},
    "drafted": {"under_review", "failed"},
    "under_review": {"approved", "failed", "drafted"},
    "approved": {"scheduled", "failed"},
    "scheduled": {"published", "failed"},
    "published": set(),
    "failed": {"drafted"},
}


@router.get("")
def list_content(
    brand_id: uuid.UUID,
    status_filter: Optional[str] = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    q = select(ContentItem).where(ContentItem.brand_id == brand_id)
    if status_filter:
        q = q.where(ContentItem.status == status_filter)
    q = q.order_by(ContentItem.created_at.desc())
    return [
        {
            "id": str(c.id),
            "platform": c.platform,
            "content_type": c.content_type,
            "status": c.status,
            "angle": c.angle,
            "created_at": c.created_at.isoformat(),
        }
        for c in db.execute(q).scalars().all()
    ]


@router.post("/{content_id}/transition")
def transition(
    content_id: uuid.UUID,
    to: str,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    item = db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    brand = db.get(Brand, item.brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    allowed = VALID_TRANSITIONS.get(item.status, set())
    if to not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot transition {item.status} → {to}")
    # role gate for approval-class transitions
    if to in {"approved", "published"} and user.role not in {"growth_head", "admin", "owner"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires growth_head+")
    item.status = to
    db.commit()
    return {"id": str(item.id), "status": item.status}

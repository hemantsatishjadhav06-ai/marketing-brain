"""Content — list, draft, transition, detail (Phase 1)."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.registry import draft_entry
from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.content import CalendarEntry, ContentItem, ContentVariant, CriticReview
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


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("")
def list_content(
    brand_id: uuid.UUID,
    status_filter: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    q = select(ContentItem).where(ContentItem.brand_id == brand_id)
    if status_filter:
        q = q.where(ContentItem.status == status_filter)
    if platform:
        q = q.where(ContentItem.platform == platform)
    q = q.order_by(desc(ContentItem.created_at)).limit(limit)
    return [
        {
            "id": str(c.id),
            "platform": c.platform,
            "content_type": c.content_type,
            "status": c.status,
            "angle": c.angle,
            "agent_name": c.agent_name,
            "created_at": c.created_at.isoformat(),
        }
        for c in db.execute(q).scalars().all()
    ]


@router.get("/{content_id}")
def get_content(
    content_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    item = db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    brand = db.get(Brand, item.brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    variants = db.execute(
        select(ContentVariant).where(ContentVariant.content_item_id == content_id)
    ).scalars().all()
    reviews = db.execute(
        select(CriticReview).where(CriticReview.content_item_id == content_id).order_by(desc(CriticReview.created_at))
    ).scalars().all()
    return {
        "id": str(item.id),
        "brand_id": str(item.brand_id),
        "platform": item.platform,
        "content_type": item.content_type,
        "status": item.status,
        "angle": item.angle,
        "agent_name": item.agent_name,
        "payload": item.payload,
        "variants": [
            {"id": str(v.id), "label": v.label, "payload": v.payload} for v in variants
        ],
        "reviews": [
            {
                "id": str(r.id),
                "scores": r.scores,
                "weighted_total": float(r.weighted_total),
                "passed": r.passed,
                "blocking_issues": r.blocking_issues,
                "fixes": r.fixes,
                "reviewer": r.reviewer,
                "created_at": r.created_at.isoformat(),
            }
            for r in reviews
        ],
        "created_at": item.created_at.isoformat(),
    }


class DraftBody(BaseModel):
    brand_id: uuid.UUID
    entry_id: uuid.UUID


@router.post("/draft")
def draft(
    body: DraftBody,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, body.brand_id, user)
    entry = db.get(CalendarEntry, body.entry_id)
    if not entry or entry.brand_id != body.brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Calendar entry not found")
    try:
        result = draft_entry(db, body.brand_id, body.entry_id, entry.agent_name)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return result


@router.post("/{content_id}/transition")
def transition(
    content_id: uuid.UUID,
    to: str = Query(...),
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
    if to in {"approved", "published"} and user.role not in {"growth_head", "admin", "owner"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires growth_head+")
    item.status = to
    db.commit()
    return {"id": str(item.id), "status": item.status}

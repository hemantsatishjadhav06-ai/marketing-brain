"""Reviews — list pending, run critic, approve/reject (Phase 1)."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.critic_llm import critic_review
from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.content import ContentItem, CriticReview
from app.models.tenancy import User

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/{brand_id}/reviews/pending")
def list_pending(
    brand_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    rows = db.execute(
        select(ContentItem)
        .where(ContentItem.brand_id == brand_id)
        .where(ContentItem.status.in_(("drafted", "under_review")))
        .order_by(desc(ContentItem.created_at))
        .limit(limit)
    ).scalars().all()
    out = []
    for c in rows:
        last_review = db.execute(
            select(CriticReview)
            .where(CriticReview.content_item_id == c.id)
            .order_by(desc(CriticReview.created_at))
            .limit(1)
        ).scalar_one_or_none()
        out.append(
            {
                "id": str(c.id),
                "platform": c.platform,
                "content_type": c.content_type,
                "angle": c.angle,
                "status": c.status,
                "agent_name": c.agent_name,
                "created_at": c.created_at.isoformat(),
                "last_review": (
                    {
                        "weighted_total": float(last_review.weighted_total),
                        "passed": last_review.passed,
                        "scores": last_review.scores,
                        "blocking_issues": last_review.blocking_issues,
                    }
                    if last_review
                    else None
                ),
            }
        )
    return out


@router.post("/{brand_id}/reviews/{content_id}/run")
def run_critic(
    brand_id: uuid.UUID,
    content_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    item = db.get(ContentItem, content_id)
    if not item or item.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    return critic_review(db, content_item_id=content_id, persist=True)


@router.post("/{brand_id}/reviews/{content_id}/approve")
def approve(
    brand_id: uuid.UUID,
    content_id: uuid.UUID,
    user: User = Depends(require_role("growth_head")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    item = db.get(ContentItem, content_id)
    if not item or item.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    item.status = "approved"
    db.add(
        CriticReview(
            content_item_id=content_id,
            scores={},
            weighted_total=100.0,
            passed=True,
            blocking_issues=[],
            fixes=[],
            reviewer="human",
        )
    )
    db.commit()
    return {"id": str(item.id), "status": item.status}


@router.post("/{brand_id}/reviews/{content_id}/reject")
def reject(
    brand_id: uuid.UUID,
    content_id: uuid.UUID,
    reason: str = Query("", max_length=2000),
    user: User = Depends(require_role("growth_head")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    item = db.get(ContentItem, content_id)
    if not item or item.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    item.status = "failed"
    item.failure_reason = reason
    db.add(
        CriticReview(
            content_item_id=content_id,
            scores={},
            weighted_total=0.0,
            passed=False,
            blocking_issues=[reason or "rejected by reviewer"],
            fixes=[],
            reviewer="human",
        )
    )
    db.commit()
    return {"id": str(item.id), "status": item.status}

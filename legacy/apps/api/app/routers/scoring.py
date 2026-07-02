"""Scoring + Idea Mill endpoints (Phase 1 real implementation).

POST /brands/{brand_id}/ideas/generate          → run Idea Mill (40 by default)
GET  /brands/{brand_id}/ideas                   → list ideas, sortable, filterable
POST /brands/{brand_id}/score/run               → re-score all existing ideas
GET  /brands/{brand_id}/scoring/runs/{idea_id}  → fetch breakdown history
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.idea_mill import IdeaMillAgent
from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand, BrandBrain
from app.models.content import ContentIdea
from app.models.intelligence import ScoringRun
from app.models.products import Product
from app.models.tenancy import User
from app.services.scoring import persist_run, score_idea

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.post("/{brand_id}/ideas/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_ideas(
    brand_id: uuid.UUID,
    count: int = Query(40, ge=5, le=200),
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return IdeaMillAgent().run(db, brand_id, count=count)


@router.get("/{brand_id}/ideas")
def list_ideas(
    brand_id: uuid.UUID,
    sort: str = Query("score_desc", pattern="^(score_desc|score_asc|created_desc)$"),
    platform: Optional[str] = None,
    content_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    q = select(ContentIdea).where(ContentIdea.brand_id == brand_id)
    if platform:
        q = q.where(ContentIdea.platform == platform)
    if content_type:
        q = q.where(ContentIdea.content_type == content_type)
    if status_filter:
        q = q.where(ContentIdea.status == status_filter)
    if sort == "score_desc":
        q = q.order_by(desc(ContentIdea.score))
    elif sort == "score_asc":
        q = q.order_by(ContentIdea.score.asc())
    else:
        q = q.order_by(desc(ContentIdea.created_at))
    rows = db.execute(q.limit(limit)).scalars().all()
    return [
        {
            "id": str(i.id),
            "title": i.title,
            "angle": i.angle,
            "platform": i.platform,
            "content_type": i.content_type,
            "product_ids": i.product_ids,
            "score": float(i.score),
            "reason": i.reason,
            "source": i.source,
            "status": i.status,
            "created_at": i.created_at.isoformat(),
        }
        for i in rows
    ]


@router.post("/{brand_id}/score/run")
def rescore_all(
    brand_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """Re-score every existing ContentIdea for this brand with the current
    brand_brain + trends + products. Returns count + new average."""
    _brand_or_404(db, brand_id, user)
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    products = list(db.execute(select(Product).where(Product.brand_id == brand_id)).scalars().all())
    pid_index = {str(p.id): p for p in products}
    ideas = list(db.execute(select(ContentIdea).where(ContentIdea.brand_id == brand_id)).scalars().all())
    totals: list[float] = []
    for idea in ideas:
        prods = [pid_index[pid] for pid in idea.product_ids if pid in pid_index]
        breakdown = score_idea(
            db,
            brand_id=brand_id,
            title=idea.title,
            angle=idea.angle,
            content_type=idea.content_type,
            keywords=[idea.title.split()[0] if idea.title else ""],
            products=prods,
            brain=brain,
        )
        idea.score = breakdown.total
        idea.reason = " | ".join(breakdown.notes)[:1900]
        persist_run(
            db, brand_id=brand_id, subject_type="idea", subject_id=idea.id,
            breakdown=breakdown, inputs={"rescore": True},
        )
        totals.append(breakdown.total)
    db.commit()
    avg = sum(totals) / len(totals) if totals else 0.0
    return {"rescored": len(totals), "avg_score": round(avg, 2)}


@router.get("/{brand_id}/scoring/runs/{idea_id}")
def get_runs_for_idea(
    brand_id: uuid.UUID,
    idea_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    rows = db.execute(
        select(ScoringRun)
        .where(ScoringRun.brand_id == brand_id)
        .where(ScoringRun.subject_id == idea_id)
        .order_by(desc(ScoringRun.created_at))
        .limit(20)
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "score_type": r.score_type,
            "total": float(r.total),
            "breakdown": r.breakdown,
            "inputs": r.inputs,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

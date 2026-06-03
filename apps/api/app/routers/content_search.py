"""Search across content (title + angle), scoped to org + brand."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_user
from app.models.brand import Brand
from app.models.content import ContentIdea, ContentItem
from app.models.tenancy import User

router = APIRouter()


@router.get("/search")
def search_content(
    brand_id: uuid.UUID,
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(25, ge=1, le=100),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    needle = f"%{q.lower()}%"

    items = list(
        db.execute(
            select(ContentItem)
            .where(ContentItem.brand_id == brand_id)
            .where(
                or_(
                    ContentItem.angle.ilike(needle),
                    ContentItem.content_type.ilike(needle),
                    ContentItem.platform.ilike(needle),
                    ContentItem.agent_name.ilike(needle),
                )
            )
            .order_by(desc(ContentItem.created_at))
            .limit(limit)
        ).scalars().all()
    )
    ideas = list(
        db.execute(
            select(ContentIdea)
            .where(ContentIdea.brand_id == brand_id)
            .where(or_(ContentIdea.title.ilike(needle), ContentIdea.angle.ilike(needle)))
            .order_by(desc(ContentIdea.score))
            .limit(limit)
        ).scalars().all()
    )
    return {
        "q": q,
        "content_items": [
            {"id": str(c.id), "platform": c.platform, "content_type": c.content_type,
             "status": c.status, "angle": c.angle, "kind": "content"} for c in items
        ],
        "ideas": [
            {"id": str(i.id), "title": i.title, "angle": i.angle, "score": float(i.score),
             "platform": i.platform, "content_type": i.content_type, "kind": "idea"}
            for i in ideas
        ],
    }

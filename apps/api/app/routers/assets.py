"""Assets — list per brand, optional filter by kind / content_item."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_user
from app.models.assets import Asset
from app.models.brand import Brand
from app.models.tenancy import User
from app.pipeline.storage import get_storage

router = APIRouter()


@router.get("/{brand_id}/assets")
def list_assets(
    brand_id: uuid.UUID,
    kind: Optional[str] = None,
    content_item_id: Optional[uuid.UUID] = None,
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    q = select(Asset).where(Asset.brand_id == brand_id)
    if kind:
        q = q.where(Asset.kind == kind)
    if content_item_id:
        q = q.where(Asset.content_item_id == content_item_id)
    rows = db.execute(q.order_by(desc(Asset.created_at)).limit(limit)).scalars().all()
    storage = get_storage()
    return [
        {
            "id": str(a.id),
            "kind": a.kind,
            "url": storage.url_for(a.storage_key),
            "mime": a.mime,
            "width": a.width,
            "height": a.height,
            "duration_s": float(a.duration_s),
            "content_item_id": str(a.content_item_id) if a.content_item_id else None,
            "meta": a.meta,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]

"""Publishing — export-mode + native publish (Phase 3)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.publishing import PublishLog
from app.models.tenancy import User
from app.publishers.dispatcher import publish_item
from app.services.publish_export import build_publish_bundle, export_to_storage

router = APIRouter()


def _own(db: Session, content_id: uuid.UUID, user: User) -> ContentItem:
    item = db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    brand = db.get(Brand, item.brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    return item


@router.post("/export/{content_id}")
def export_content(
    content_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """Build a publish bundle for any content item and persist the zip."""
    _own(db, content_id, user)
    return export_to_storage(db, content_id)


@router.get("/export/{content_id}/download")
def download_content(
    content_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _own(db, content_id, user)
    data, filename = build_publish_bundle(db, content_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/publish/{content_id}")
def publish_now(
    content_id: uuid.UUID,
    user: User = Depends(require_role("growth_head")),
    db: Session = Depends(get_db),
):
    """Native publish via the configured PublishTarget for this brand+platform.
    Falls back to export-bundle if no target is configured or it's in 'export' mode."""
    item = _own(db, content_id, user)
    if item.status not in {"approved", "scheduled", "published"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Item must be approved before publishing (status={item.status})")
    return publish_item(db, item)


@router.get("/logs/{content_id}")
def list_logs(
    content_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _own(db, content_id, user)
    rows = db.execute(
        select(PublishLog).where(PublishLog.content_item_id == content_id).order_by(desc(PublishLog.created_at))
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "platform": r.platform,
            "status": r.status,
            "external_id": r.external_id,
            "response": r.response,
            "published_at": r.published_at.isoformat(),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]

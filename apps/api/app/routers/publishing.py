"""Publishing — export-mode (Phase 1). Real API integrations land in Phase 3."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.content import ContentItem
from app.models.tenancy import User
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
    """Build a publish bundle for an approved (or any) content item and persist
    the zip to storage. Returns a URL the user can hand-off."""
    _own(db, content_id, user)
    return export_to_storage(db, content_id)


@router.get("/export/{content_id}/download")
def download_content(
    content_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    item = _own(db, content_id, user)
    data, filename = build_publish_bundle(db, content_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

"""PublishTarget CRUD — per brand, per platform.

credentials_ref is stored as a JSON string in the DB. The UI hides it behind
a "set credentials" action; never echoes raw secrets back in GET responses.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.publishing import PublishTarget
from app.models.tenancy import User

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


def _safe_credentials(target: PublishTarget) -> dict:
    """Don't echo secrets to the client. Just say whether credentials are set,
    which keys they contain, and whether they're encrypted at rest."""
    from app.core.crypto import decrypt, is_encrypted
    raw = (target.credentials_ref or "").strip()
    if not raw:
        return {"configured": False, "keys": [], "encrypted": False}
    try:
        d = json.loads(decrypt(raw))
        return {"configured": True, "keys": sorted(d.keys()), "encrypted": is_encrypted(raw)}
    except (json.JSONDecodeError, ValueError):
        return {"configured": True, "keys": [], "encrypted": is_encrypted(raw)}


class TargetIn(BaseModel):
    platform: str = Field(..., max_length=64)
    mode: str = Field("api", pattern="^(api|export)$")
    credentials: dict = Field(default_factory=dict)
    active: bool = True


class TargetUpdate(BaseModel):
    mode: Optional[str] = Field(None, pattern="^(api|export)$")
    credentials: Optional[dict] = None
    active: Optional[bool] = None


@router.get("/{brand_id}/publish-targets")
def list_targets(
    brand_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    rows = db.execute(select(PublishTarget).where(PublishTarget.brand_id == brand_id)).scalars().all()
    return [
        {
            "id": str(t.id),
            "platform": t.platform,
            "mode": t.mode,
            "active": t.active,
            "credentials": _safe_credentials(t),
            "created_at": t.created_at.isoformat(),
        }
        for t in rows
    ]


@router.post("/{brand_id}/publish-targets", status_code=status.HTTP_201_CREATED)
def create_target(
    brand_id: uuid.UUID,
    body: TargetIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    from app.core.crypto import encrypt
    blob = json.dumps(body.credentials) if body.credentials else ""
    t = PublishTarget(
        brand_id=brand_id,
        platform=body.platform,
        mode=body.mode,
        credentials_ref=encrypt(blob) if blob else "",
        active=body.active,
    )
    db.add(t)
    db.commit()
    return {"id": str(t.id)}


@router.patch("/{brand_id}/publish-targets/{target_id}")
def update_target(
    brand_id: uuid.UUID,
    target_id: uuid.UUID,
    body: TargetUpdate,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    t = db.get(PublishTarget, target_id)
    if not t or t.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target not found")
    if body.mode is not None:
        t.mode = body.mode
    if body.active is not None:
        t.active = body.active
    if body.credentials is not None:
        from app.core.crypto import encrypt
        blob = json.dumps(body.credentials)
        t.credentials_ref = encrypt(blob)
    db.commit()
    return {"id": str(t.id), "mode": t.mode, "active": t.active}


@router.delete("/{brand_id}/publish-targets/{target_id}")
def delete_target(
    brand_id: uuid.UUID,
    target_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    t = db.get(PublishTarget, target_id)
    if not t or t.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target not found")
    db.delete(t)
    db.commit()
    return {"deleted": str(target_id)}

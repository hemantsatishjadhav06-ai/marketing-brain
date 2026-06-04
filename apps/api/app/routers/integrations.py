"""Per-brand integrations — Magento for now, Shopify/Klaviyo/etc next.

GET   /brands/{brand_id}/integrations           → list connected providers (safe — no creds returned)
POST  /brands/{brand_id}/integrations/magento/connect   → set base_url + token (encrypted at rest)
POST  /brands/{brand_id}/integrations/magento/sync      → pull categories + products
GET   /brands/{brand_id}/integrations/magento/categories → cached categories
DELETE /brands/{brand_id}/integrations/magento          → disconnect (clears creds)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand, BrandBrain
from app.models.tenancy import User
from app.services.magento_sync import (
    cached_categories,
    is_configured,
    load_config,
    save_config,
    sync as magento_sync,
)

router = APIRouter()


def _brand_or_404(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/{brand_id}/integrations")
def list_integrations(
    brand_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    cfg = load_config(db, brand_id)
    return {
        "magento": {
            "connected": cfg is not None,
            "base_url": cfg[0] if cfg else None,
            "token_set": cfg is not None,
        },
    }


class MagentoConnectIn(BaseModel):
    base_url: str = Field(..., min_length=8, max_length=255)
    token: str = Field(..., min_length=8, max_length=512)


@router.post("/{brand_id}/integrations/magento/connect")
def magento_connect(
    brand_id: uuid.UUID,
    body: MagentoConnectIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    base_url = body.base_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "base_url must start with http:// or https://")
    save_config(db, brand_id, base_url=base_url, token=body.token)
    return {"connected": True, "base_url": base_url}


@router.post("/{brand_id}/integrations/magento/sync", status_code=status.HTTP_202_ACCEPTED)
def magento_sync_endpoint(
    brand_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    try:
        return magento_sync(db, brand_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001 — surface upstream Magento errors cleanly
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"magento sync failed: {e}")


@router.get("/{brand_id}/integrations/magento/categories")
def magento_list_categories(
    brand_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    return cached_categories(db, brand_id)


@router.delete("/{brand_id}/integrations/magento")
def magento_disconnect(
    brand_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    _brand_or_404(db, brand_id, user)
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if not brain:
        return {"disconnected": True}
    rules = dict(brain.platform_rules or {})
    rules.pop("magento", None)
    brain.platform_rules = rules
    db.commit()
    return {"disconnected": True}

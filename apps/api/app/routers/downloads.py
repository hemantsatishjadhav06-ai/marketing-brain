"""Per-creative downloads.

Users asked for: take out individual creatives — single image, single video,
single carousel slide, single variant — *or* the full automated bundle.

Endpoints (all return Response with the right MIME):
  GET /content/{content_id}/download/asset/{asset_id}
  GET /content/{content_id}/download/variant/{variant_id}
  POST /publishing/export/bulk  → zip-of-zips for many approved items
"""
from __future__ import annotations

import io
import json
import mimetypes
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.assets import Asset
from app.models.brand import Brand
from app.models.content import ContentItem, ContentVariant
from app.models.tenancy import User
from app.pipeline.storage import get_storage
from app.services.publish_export import build_publish_bundle

router = APIRouter()


def _own_item(db: Session, content_id: uuid.UUID, user: User) -> ContentItem:
    item = db.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    brand = db.get(Brand, item.brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    return item


@router.get("/content/{content_id}/download/asset/{asset_id}")
def download_asset(
    content_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """Single asset (image / video / carousel slide / audio) as a raw download."""
    item = _own_item(db, content_id, user)
    asset = db.get(Asset, asset_id)
    if not asset or asset.content_item_id != item.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found on this content")
    storage = get_storage()
    # LocalStorage exposes .root — open the file directly.
    root = getattr(storage, "root", None)
    if root is None:
        # remote storage → 302 to public URL
        return Response(status_code=302, headers={"Location": storage.url_for(asset.storage_key)})
    p = Path(root) / asset.storage_key
    if not p.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset bytes missing on disk")
    data = p.read_bytes()
    ext = p.suffix or ".bin"
    mime = asset.mime or mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    filename = f"{item.platform}_{item.content_type}_{asset.kind}_{asset.id}{ext}"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/content/{content_id}/download/variant/{variant_id}")
def download_variant(
    content_id: uuid.UUID,
    variant_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """Single A/B variant as a zip:
       variant.json + caption.txt + hashtags.txt + every asset of that variant."""
    item = _own_item(db, content_id, user)
    variant = db.get(ContentVariant, variant_id)
    if not variant or variant.content_item_id != item.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variant not found on this content")
    payload = variant.payload or {}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "variant.json",
            json.dumps(
                {
                    "content_item_id": str(item.id),
                    "variant_id": str(variant.id),
                    "label": variant.label,
                    "platform": item.platform,
                    "content_type": item.content_type,
                    "payload": payload,
                },
                indent=2,
                default=str,
            ),
        )
        cap_lines: list[str] = []
        for k in ("headline", "title", "subject_line", "caption"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                cap_lines.append(v)
        if isinstance(payload.get("cta"), str):
            cap_lines.append("")
            cap_lines.append(payload["cta"])
        zf.writestr("caption.txt", "\n".join(cap_lines) or item.angle)
        hashtags = payload.get("hashtags") or []
        if hashtags:
            zf.writestr("hashtags.txt", " ".join(hashtags))
        # bundle assets that match this variant (or all if labels aren't aligned)
        storage = get_storage()
        root = getattr(storage, "root", None)
        if root is not None:
            for a in (item.id and []):
                pass  # placeholder for typing
            from sqlalchemy import select
            assets = list(
                db.execute(select(Asset).where(Asset.content_item_id == item.id)).scalars().all()
            )
            for a in assets:
                # variant.A gets all assets; variant.B reuses the same image set for static_post/carousel
                p = Path(root) / a.storage_key
                if p.exists():
                    arc = f"assets/{a.kind}_{a.id}{p.suffix or '.bin'}"
                    zf.writestr(arc, p.read_bytes())
    data = buf.getvalue()
    filename = f"variant_{variant.label}_{item.platform}_{item.id}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class BulkExportIn(BaseModel):
    content_ids: list[uuid.UUID]


@router.post("/publishing/export/bulk")
def export_bulk(
    body: BulkExportIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """Zip-of-zips for many approved items — useful for hand-off to a creative
    team or to a manual scheduling tool."""
    if not body.content_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "content_ids required")
    buf = io.BytesIO()
    bundled = 0
    skipped: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as outer:
        for cid in body.content_ids:
            try:
                item = _own_item(db, cid, user)
            except HTTPException:
                skipped.append(str(cid)); continue
            inner_bytes, inner_name = build_publish_bundle(db, item.id)
            outer.writestr(inner_name, inner_bytes)
            bundled += 1
    if bundled == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no items found in your org")
    data = buf.getvalue()
    filename = f"marketing-brain_bulk_{bundled}_items.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Bundled": str(bundled),
            "X-Skipped": ",".join(skipped),
        },
    )

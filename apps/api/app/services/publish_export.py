"""Publish-export — bundle an approved ContentItem into a downloadable zip.

The zip contains everything a human (or a downstream automation) needs to
manually post on a channel: image(s) / video, caption, hashtags, metadata.

Used by the Publish-Export Agent and the /publishing/export endpoint.
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assets import Asset
from app.models.content import ContentItem
from app.pipeline.storage import get_storage, new_key


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:80]


def build_publish_bundle(db: Session, content_item_id: uuid.UUID) -> tuple[bytes, str]:
    """Returns (zip_bytes, filename)."""
    item = db.get(ContentItem, content_item_id)
    if not item:
        raise ValueError("content_item not found")
    assets = list(
        db.execute(
            select(Asset).where(Asset.content_item_id == content_item_id)
        ).scalars().all()
    )
    payload = item.payload or {}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # metadata
        zf.writestr(
            "metadata.json",
            json.dumps(
                {
                    "content_item_id": str(item.id),
                    "brand_id": str(item.brand_id),
                    "platform": item.platform,
                    "content_type": item.content_type,
                    "angle": item.angle,
                    "status": item.status,
                    "agent_name": item.agent_name,
                    "payload": payload,
                },
                indent=2,
                default=str,
            ),
        )
        # caption + hashtags + cta as plain text
        cap_lines: list[str] = []
        for k in ("headline", "title", "subject_line", "caption"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                cap_lines.append(v)
        cta = payload.get("cta")
        if isinstance(cta, str) and cta:
            cap_lines.append("")
            cap_lines.append(cta)
        zf.writestr("caption.txt", "\n".join(cap_lines) or item.angle)
        hashtags = payload.get("hashtags") or []
        if hashtags:
            zf.writestr("hashtags.txt", " ".join(hashtags))
        # blog body
        sections = payload.get("sections")
        if isinstance(sections, list):
            md: list[str] = []
            title = payload.get("title") or item.angle
            md.append(f"# {title}\n")
            for s in sections:
                if isinstance(s, dict):
                    md.append(f"\n## {s.get('h2', '')}\n\n{s.get('body', '')}\n")
            zf.writestr("post.md", "".join(md))
        # email html (very simple)
        blocks = payload.get("blocks")
        if isinstance(blocks, list) and item.content_type == "email":
            html_parts = ["<html><body>"]
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                t = b.get("type", "paragraph")
                txt = b.get("text", "")
                if t == "headline":
                    html_parts.append(f"<h1>{txt}</h1>")
                elif t == "cta":
                    html_parts.append(f"<p><a href='{b.get('url', '#')}'>{txt}</a></p>")
                else:
                    html_parts.append(f"<p>{txt}</p>")
            html_parts.append("</body></html>")
            zf.writestr("email.html", "".join(html_parts))
        # bundle assets
        storage_root = Path(get_storage().root)  # LocalStorage has .root
        for a in assets:
            src = storage_root / a.storage_key
            if src.exists():
                ext = src.suffix or ".bin"
                arcname = f"assets/{a.kind}_{_safe(str(a.id))}{ext}"
                zf.writestr(arcname, src.read_bytes())

    filename = f"{item.platform}_{item.content_type}_{item.id}.zip"
    return buf.getvalue(), filename


def export_to_storage(db: Session, content_item_id: uuid.UUID) -> dict:
    """Builds the zip and uploads it to the storage layer, returning a URL."""
    item = db.get(ContentItem, content_item_id)
    if item is None:
        raise ValueError("content_item not found")
    data, filename = build_publish_bundle(db, content_item_id)
    storage = get_storage()
    key = new_key(item.brand_id, "publish_export", "zip")
    url = storage.write_bytes(key, data)
    return {"url": url, "filename": filename, "bytes": len(data)}

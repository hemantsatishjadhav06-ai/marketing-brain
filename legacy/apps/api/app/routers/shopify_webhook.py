"""Shopify product webhook ingestion.

Configure Shopify to send `products/create`, `products/update`, `products/delete`
webhooks to `/webhooks/shopify/{brand_id}` and set the brand's secret with
SHOPIFY_WEBHOOK_SECRET. We verify HMAC then upsert the Product row.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.brand import Brand
from app.models.products import Product

router = APIRouter()


def _verify(body: bytes, hmac_header: str) -> bool:
    if not settings.SHOPIFY_WEBHOOK_SECRET:
        # in dev with no secret we accept everything (and log a warning header below)
        return True
    expected = base64.b64encode(
        hmac.new(settings.SHOPIFY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(expected, hmac_header or "")


@router.post("/{brand_id}", status_code=status.HTTP_200_OK)
async def shopify_product_webhook(
    brand_id: uuid.UUID,
    request: Request,
    x_shopify_topic: str = Header(default=""),
    x_shopify_hmac_sha256: str = Header(default=""),
):
    raw = await request.body()
    if not _verify(raw, x_shopify_hmac_sha256):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad hmac")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bad json")

    # use a fresh session — webhooks aren't tied to a user
    from app.core.db import SessionLocal
    db: Session = SessionLocal()
    try:
        brand = db.get(Brand, brand_id)
        if not brand:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
        sku = (payload.get("variants") or [{}])[0].get("sku") or str(payload.get("id"))
        topic = x_shopify_topic.lower()

        prod = db.execute(
            select(Product).where(Product.brand_id == brand_id).where(Product.sku == sku)
        ).scalar_one_or_none()

        if topic == "products/delete":
            if prod:
                db.delete(prod)
                db.commit()
            return {"status": "deleted", "sku": sku}

        if prod is None:
            prod = Product(brand_id=brand_id, sku=sku, title="")
            db.add(prod)
        prod.title = (payload.get("title") or prod.title)[:250]
        prod.description = (payload.get("body_html") or prod.description)[:8000]
        prod.category = ((payload.get("product_type") or "") or prod.category)[:120]
        variants = payload.get("variants") or []
        if variants:
            prod.price = float(variants[0].get("price") or prod.price or 0)
        images = payload.get("images") or []
        if images:
            prod.image_urls = [im.get("src") for im in images if im.get("src")][:8]
        prod.attributes = {
            "shopify_id": payload.get("id"),
            "handle": payload.get("handle"),
            "tags": payload.get("tags"),
            "vendor": payload.get("vendor"),
        }
        db.commit()
        return {"status": "upserted", "sku": sku, "topic": topic}
    finally:
        db.close()

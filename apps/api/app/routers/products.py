"""Products (brand-scoped CRUD + simple list)."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.guards.no_cross_brand import assert_single_brand
from app.models.brand import Brand
from app.models.products import Product
from app.models.tenancy import User
from app.schemas.products import ProductCreateIn, ProductOut, ProductUpdateIn

router = APIRouter()


def _own_brand(db: Session, brand_id: uuid.UUID, user: User) -> Brand:
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/{brand_id}/products/{product_id}/performance")
def product_performance(
    brand_id: uuid.UUID,
    product_id: uuid.UUID,
    days: int = 30,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Aggregate performance across every ContentItem that featured this
    product in the last N days. Used by Studio + the Products page."""
    from datetime import datetime, timedelta, timezone
    from app.models.content import ContentItem
    from app.models.publishing import ContentPerformance

    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    prod = db.get(Product, product_id)
    if not prod or prod.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found in this brand")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    pid_str = str(product_id)
    items = list(db.execute(
        select(ContentItem).where(ContentItem.brand_id == brand_id)
    ).scalars().all())
    matched = [i for i in items if isinstance(i.product_ids, list) and pid_str in [str(p) for p in i.product_ids]]
    if not matched:
        return {
            "product_id": pid_str, "sku": prod.sku, "title": prod.title,
            "days": days, "content_items": 0,
            "totals": {"impressions": 0, "engagements": 0, "clicks": 0, "conversions": 0, "revenue": 0.0},
            "top_content": [],
        }

    item_ids = [i.id for i in matched]
    perf_rows = list(db.execute(
        select(ContentPerformance, ContentItem)
        .join(ContentItem, ContentItem.id == ContentPerformance.content_item_id)
        .where(ContentPerformance.content_item_id.in_(item_ids))
        .where(ContentPerformance.created_at >= since)
    ).all())

    totals = {"impressions": 0, "engagements": 0, "clicks": 0, "conversions": 0, "revenue": 0.0}
    top: list[dict] = []
    for perf, item in perf_rows:
        totals["impressions"] += int(perf.impressions or 0)
        totals["engagements"] += int(perf.engagements or 0)
        totals["clicks"] += int(perf.clicks or 0)
        totals["conversions"] += int(perf.conversions or 0)
        totals["revenue"] += float(perf.revenue or 0)
        top.append({
            "content_item_id": str(item.id),
            "platform": item.platform, "content_type": item.content_type,
            "angle": item.angle,
            "impressions": int(perf.impressions or 0),
            "engagements": int(perf.engagements or 0),
            "revenue": float(perf.revenue or 0),
        })
    top.sort(key=lambda r: r["engagements"], reverse=True)
    return {
        "product_id": pid_str, "sku": prod.sku, "title": prod.title,
        "image_url": (prod.image_urls or [None])[0],
        "days": days,
        "content_items": len(matched),
        "totals": totals,
        "top_content": top[:10],
    }


@router.get("/{brand_id}/products", response_model=List[ProductOut])
def list_products(
    brand_id: uuid.UUID,
    category: str | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """List products in this brand. Optional ?category=<name> filter so the
    /create cascade can populate the Product dropdown after a Category pick."""
    _own_brand(db, brand_id, user)
    q = select(Product).where(Product.brand_id == brand_id)
    if category:
        q = q.where(Product.category == category)
    rows = db.execute(q.order_by(Product.created_at.desc())).scalars().all()
    assert_single_brand(rows, brand_id, context="products.list")
    return rows


@router.post("/{brand_id}/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    brand_id: uuid.UUID,
    payload: ProductCreateIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _own_brand(db, brand_id, user)
    margin = (payload.price - payload.cost) if payload.price and payload.cost else 0
    product = Product(
        brand_id=brand_id,
        sku=payload.sku,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        price=payload.price,
        cost=payload.cost,
        margin=margin,
        image_urls=payload.image_urls,
        attributes=payload.attributes,
        is_new=payload.is_new,
        is_bestseller=payload.is_bestseller,
        is_dead_stock=payload.is_dead_stock,
        is_discounted=payload.is_discounted,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/{brand_id}/products/{product_id}", response_model=ProductOut)
def update_product(
    brand_id: uuid.UUID,
    product_id: uuid.UUID,
    payload: ProductUpdateIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    _own_brand(db, brand_id, user)
    product = db.get(Product, product_id)
    if not product or product.brand_id != brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    if "price" in payload.model_dump(exclude_unset=True) or "cost" in payload.model_dump(exclude_unset=True):
        product.margin = (product.price or 0) - (product.cost or 0)
    db.commit()
    db.refresh(product)
    return product

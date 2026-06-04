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

"""Magento sync — pulls categories + products into the cockpit DB.

Storage:
- Categories cached on `BrandBrain.content_templates['magento_categories']` as a
  flat list of {external_id, name, parent_id, level, path, product_count}.
  Avoids an Alembic migration; trivially upgraded to a real table later.
- Products upserted into the existing `products` table by SKU; primary
  Magento image stored in `image_urls[0]` and category string in `category`.

Per-brand config (base_url + encrypted token) lives at
`BrandBrain.platform_rules['magento']`.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt, is_encrypted
from app.data_sources.magento import MagentoClient
from app.models.brand import BrandBrain
from app.models.products import Product


log = logging.getLogger("marketing_brain.magento.sync")


def save_config(db: Session, brand_id: uuid.UUID, *, base_url: str, token: str) -> None:
    """Encrypt + persist the per-brand Magento credentials."""
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if brain is None:
        brain = BrandBrain(brand_id=brand_id)
        db.add(brain)
        db.flush()
    rules = dict(brain.platform_rules or {})
    rules["magento"] = {"base_url": base_url.rstrip("/"), "token": encrypt(token)}
    brain.platform_rules = rules
    db.commit()


def load_config(db: Session, brand_id: uuid.UUID) -> tuple[str, str] | None:
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if not brain:
        return None
    cfg = (brain.platform_rules or {}).get("magento") or {}
    if not cfg.get("base_url") or not cfg.get("token"):
        return None
    return cfg["base_url"], decrypt(cfg["token"])


def get_client(db: Session, brand_id: uuid.UUID) -> MagentoClient | None:
    cfg = load_config(db, brand_id)
    if cfg is None:
        return None
    base_url, token = cfg
    return MagentoClient(base_url=base_url, token=token)


def cached_categories(db: Session, brand_id: uuid.UUID) -> list[dict]:
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if not brain:
        return []
    return list((brain.content_templates or {}).get("magento_categories") or [])


def _cache_categories(db: Session, brand_id: uuid.UUID, cats: list[dict]) -> None:
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if brain is None:
        brain = BrandBrain(brand_id=brand_id)
        db.add(brain); db.flush()
    tpl = dict(brain.content_templates or {})
    tpl["magento_categories"] = cats
    brain.content_templates = tpl
    db.commit()


def _category_name_for_id(cats: list[dict], cid: str) -> str:
    for c in cats:
        if c.get("external_id") == cid:
            return c.get("name") or ""
    return ""


def sync(
    db: Session, brand_id: uuid.UUID, *, max_products_per_category: int = 50,
) -> dict:
    """Pull categories + products from Magento into the cockpit DB."""
    client = get_client(db, brand_id)
    if client is None:
        raise ValueError("Magento is not connected for this brand. Use /settings/integrations first.")

    # 1) categories
    cats_objs = client.list_categories()
    cats = [c.as_dict() for c in cats_objs]
    _cache_categories(db, brand_id, cats)

    # 2) products — walk leaf categories (those with product_count > 0)
    leaf_cats = [c for c in cats if c["product_count"] > 0]
    upserted = 0
    seen_skus: set[str] = set()
    for cat in leaf_cats:
        try:
            prods = client.search_products(category_id=cat["external_id"], page_size=max_products_per_category)
        except Exception as e:  # noqa: BLE001
            log.warning("magento search failed for cat %s: %s", cat.get("external_id"), e)
            continue
        for mp in prods:
            if not mp.sku or mp.sku in seen_skus:
                continue
            seen_skus.add(mp.sku)
            existing = db.execute(
                select(Product).where(Product.brand_id == brand_id).where(Product.sku == mp.sku)
            ).scalar_one_or_none()
            if existing is None:
                existing = Product(brand_id=brand_id, sku=mp.sku, title="")
                db.add(existing)
            existing.title = (mp.name or existing.title)[:250]
            existing.description = (mp.description or existing.description)[:8000]
            existing.category = cat["name"][:120]
            existing.price = mp.price or existing.price or 0
            existing.image_urls = [mp.image_url] if mp.image_url else (existing.image_urls or [])
            existing.attributes = {
                **(existing.attributes or {}),
                "magento_status": mp.status,
                "magento_type": mp.type_id,
                "magento_category_ids": mp.category_ids,
                "magento_attrs": mp.attributes,
            }
            existing.status = "active" if mp.status == 1 else "inactive"
            upserted += 1
    db.commit()

    return {
        "categories_synced": len(cats),
        "leaf_categories_with_products": len(leaf_cats),
        "products_upserted": upserted,
        "skus_seen": len(seen_skus),
    }


def is_configured(db: Session, brand_id: uuid.UUID) -> bool:
    return load_config(db, brand_id) is not None

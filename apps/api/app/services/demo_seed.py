"""Demo product seed — populates a brand with realistic sample SKUs so the
cockpit's Category + Product dropdowns work immediately without Magento.

Used when:
- A new tenant evaluates the SaaS before connecting their store
- Magento credentials aren't ready yet (e.g. token scope being fixed)
- Local dev / smoke tests / pytests

Idempotent: skips brands that already have any product.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import BrandBrain
from app.models.products import Product


# ─── per-sport demo catalogues ─────────────────────────────────────────────────
DEMO_CATALOGUES: dict[str, dict[str, Any]] = {
    "tennis": {
        "categories": [
            {"external_id": "demo-rackets", "name": "Rackets", "parent_id": None, "level": 1, "path": "Tennis/Rackets", "product_count": 3, "image_url": "", "children": []},
            {"external_id": "demo-strings", "name": "Strings", "parent_id": None, "level": 1, "path": "Tennis/Strings", "product_count": 2, "image_url": "", "children": []},
            {"external_id": "demo-shoes",   "name": "Shoes",   "parent_id": None, "level": 1, "path": "Tennis/Shoes",   "product_count": 2, "image_url": "", "children": []},
            {"external_id": "demo-bags",    "name": "Bags",    "parent_id": None, "level": 1, "path": "Tennis/Bags",    "product_count": 1, "image_url": "", "children": []},
        ],
        "products": [
            {"sku": "DEMO-RACK-001", "title": "Pro Tour Racket 300g", "category": "Rackets", "price": 189.99, "margin": 60, "image_url": "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=400", "is_bestseller": True},
            {"sku": "DEMO-RACK-002", "title": "Lite Comp Racket 270g", "category": "Rackets", "price": 119.00, "margin": 40, "image_url": "https://images.unsplash.com/photo-1551958219-acbc608c6377?w=400", "is_new": True},
            {"sku": "DEMO-RACK-003", "title": "Junior Starter 250g",  "category": "Rackets", "price": 59.00,  "margin": 22, "image_url": "https://images.unsplash.com/photo-1530915534728-d12fef94de2e?w=400"},
            {"sku": "DEMO-STR-001",  "title": "Pro Polyester 1.25mm", "category": "Strings", "price": 19.50,  "margin": 11, "image_url": "https://images.unsplash.com/photo-1542144582-1ba00456b5e3?w=400", "is_bestseller": True},
            {"sku": "DEMO-STR-002",  "title": "Gut Hybrid 1.30mm",    "category": "Strings", "price": 39.00,  "margin": 18, "image_url": "https://images.unsplash.com/photo-1601758174039-bcf3a8e5e6c4?w=400", "is_discounted": True},
            {"sku": "DEMO-SHO-001",  "title": "Clay-Court Pro Shoe",  "category": "Shoes",   "price": 149.00, "margin": 55, "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=400", "is_new": True},
            {"sku": "DEMO-SHO-002",  "title": "All-Court Stability",  "category": "Shoes",   "price": 129.00, "margin": 48, "image_url": "https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=400"},
            {"sku": "DEMO-BAG-001",  "title": "6-Racket Tour Bag",    "category": "Bags",    "price": 89.00,  "margin": 30, "image_url": "https://images.unsplash.com/photo-1593766787879-7d8ed31a73b4?w=400", "is_dead_stock": True},
        ],
    },
    "padel": {
        "categories": [
            {"external_id": "demo-padel-rackets", "name": "Padel Rackets", "parent_id": None, "level": 1, "path": "Padel/Rackets", "product_count": 3, "image_url": "", "children": []},
            {"external_id": "demo-padel-balls",   "name": "Padel Balls",   "parent_id": None, "level": 1, "path": "Padel/Balls",   "product_count": 1, "image_url": "", "children": []},
            {"external_id": "demo-padel-grips",   "name": "Grips",         "parent_id": None, "level": 1, "path": "Padel/Grips",   "product_count": 2, "image_url": "", "children": []},
            {"external_id": "demo-padel-bags",    "name": "Bags",          "parent_id": None, "level": 1, "path": "Padel/Bags",    "product_count": 2, "image_url": "", "children": []},
        ],
        "products": [
            {"sku": "DEMO-PAD-001", "title": "Diamond Power Padel Racket",  "category": "Padel Rackets", "price": 219.00, "margin": 80, "image_url": "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=400", "is_bestseller": True},
            {"sku": "DEMO-PAD-002", "title": "Round Control Padel Racket",  "category": "Padel Rackets", "price": 149.00, "margin": 55, "image_url": "https://images.unsplash.com/photo-1599982884046-3a4c5e6b1f2f?w=400"},
            {"sku": "DEMO-PAD-003", "title": "Teardrop All-Round",          "category": "Padel Rackets", "price": 169.00, "margin": 62, "image_url": "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=400", "is_new": True},
            {"sku": "DEMO-PAD-004", "title": "Pro Tournament Balls (3-pk)", "category": "Padel Balls",   "price": 9.50,   "margin": 4,  "image_url": "https://images.unsplash.com/photo-1614632537229-b6f80a55b5cb?w=400"},
            {"sku": "DEMO-PAD-005", "title": "Tacky Pro Overgrip",          "category": "Grips",         "price": 4.99,   "margin": 2,  "image_url": "https://images.unsplash.com/photo-1542144582-1ba00456b5e3?w=400", "is_bestseller": True},
            {"sku": "DEMO-PAD-006", "title": "Cushion Replacement Grip",    "category": "Grips",         "price": 7.50,   "margin": 3,  "image_url": "https://images.unsplash.com/photo-1542144582-1ba00456b5e3?w=400"},
            {"sku": "DEMO-PAD-007", "title": "Pro Tour Padel Bag",          "category": "Bags",          "price": 89.00,  "margin": 35, "image_url": "https://images.unsplash.com/photo-1593766787879-7d8ed31a73b4?w=400"},
            {"sku": "DEMO-PAD-008", "title": "Compact Shoulder Bag",        "category": "Bags",          "price": 49.00,  "margin": 18, "image_url": "https://images.unsplash.com/photo-1593766787879-7d8ed31a73b4?w=400", "is_discounted": True},
        ],
    },
    "pickleball": {
        "categories": [
            {"external_id": "demo-pb-paddles", "name": "Paddles", "parent_id": None, "level": 1, "path": "Pickleball/Paddles", "product_count": 3, "image_url": "", "children": []},
            {"external_id": "demo-pb-balls",   "name": "Balls",   "parent_id": None, "level": 1, "path": "Pickleball/Balls",   "product_count": 2, "image_url": "", "children": []},
            {"external_id": "demo-pb-nets",    "name": "Nets",    "parent_id": None, "level": 1, "path": "Pickleball/Nets",    "product_count": 1, "image_url": "", "children": []},
            {"external_id": "demo-pb-apparel", "name": "Apparel", "parent_id": None, "level": 1, "path": "Pickleball/Apparel", "product_count": 2, "image_url": "", "children": []},
        ],
        "products": [
            {"sku": "DEMO-PB-001", "title": "Carbon Power Paddle",          "category": "Paddles", "price": 199.00, "margin": 70, "image_url": "https://images.unsplash.com/photo-1631458803283-15ad6dc9f49d?w=400", "is_bestseller": True},
            {"sku": "DEMO-PB-002", "title": "Fibreglass Control Paddle",    "category": "Paddles", "price": 89.00,  "margin": 30, "image_url": "https://images.unsplash.com/photo-1631458803340-25b3c1e76bca?w=400"},
            {"sku": "DEMO-PB-003", "title": "Beginner Wood Paddle",         "category": "Paddles", "price": 24.99,  "margin": 8,  "image_url": "https://images.unsplash.com/photo-1631458803430-c75d8b7d7c39?w=400", "is_new": True},
            {"sku": "DEMO-PB-004", "title": "Outdoor Tournament Balls (6)", "category": "Balls",   "price": 14.99,  "margin": 5,  "image_url": "https://images.unsplash.com/photo-1614632537229-b6f80a55b5cb?w=400"},
            {"sku": "DEMO-PB-005", "title": "Indoor Soft Balls (6-pk)",     "category": "Balls",   "price": 12.50,  "margin": 4,  "image_url": "https://images.unsplash.com/photo-1614632537229-b6f80a55b5cb?w=400"},
            {"sku": "DEMO-PB-006", "title": "Portable Net 22ft",            "category": "Nets",    "price": 169.00, "margin": 55, "image_url": "https://images.unsplash.com/photo-1622279457486-62dcc4a431d6?w=400", "is_dead_stock": True},
            {"sku": "DEMO-PB-007", "title": "Performance Polo (Men's)",     "category": "Apparel", "price": 39.00,  "margin": 15, "image_url": "https://images.unsplash.com/photo-1551488831-00ddcb6c6bd3?w=400"},
            {"sku": "DEMO-PB-008", "title": "Court Shorts (Women's)",       "category": "Apparel", "price": 34.00,  "margin": 12, "image_url": "https://images.unsplash.com/photo-1525507119028-ed4c629a60a3?w=400", "is_discounted": True},
        ],
    },
}


def seed_demo(db: Session, brand_id: uuid.UUID, sport: str) -> dict:
    """Idempotent — skips if any product already exists for this brand."""
    existing_count = db.execute(
        select(Product).where(Product.brand_id == brand_id)
    ).scalars().all()
    if existing_count:
        return {"skipped": True, "reason": f"brand already has {len(existing_count)} products", "products_created": 0}

    catalogue = DEMO_CATALOGUES.get(sport)
    if not catalogue:
        return {"skipped": True, "reason": f"no demo catalogue for sport={sport}", "products_created": 0}

    # 1) populate fake categories on brand_brain so the cascade UI shows them
    brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand_id)).scalar_one_or_none()
    if brain is None:
        brain = BrandBrain(brand_id=brand_id); db.add(brain); db.flush()
    tpl = dict(brain.content_templates or {})
    tpl["magento_categories"] = catalogue["categories"]
    brain.content_templates = tpl

    # 2) create products
    created = 0
    for p in catalogue["products"]:
        prod = Product(
            brand_id=brand_id,
            sku=p["sku"],
            title=p["title"],
            description=f"Demo product for testing the {sport} content brain.",
            category=p["category"],
            price=p["price"],
            cost=max(0, p["price"] - p["margin"]),
            margin=p["margin"],
            image_urls=[p["image_url"]] if p.get("image_url") else [],
            attributes={"source": "demo_seed"},
            status="active",
            is_new=bool(p.get("is_new")),
            is_bestseller=bool(p.get("is_bestseller")),
            is_dead_stock=bool(p.get("is_dead_stock")),
            is_discounted=bool(p.get("is_discounted")),
        )
        db.add(prod)
        created += 1
    db.commit()
    return {
        "skipped": False,
        "products_created": created,
        "categories_seeded": len(catalogue["categories"]),
        "sport": sport,
    }


def seed_demo_all(db: Session, brand_id_by_sport: dict[str, uuid.UUID]) -> dict:
    out = {"results": []}
    total = 0
    for sport, bid in brand_id_by_sport.items():
        r = seed_demo(db, bid, sport)
        r["brand_id"] = str(bid); r["sport"] = sport
        out["results"].append(r)
        total += int(r.get("products_created", 0))
    out["products_created_total"] = total
    return out

"""Product schemas."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from pydantic import BaseModel

from app.schemas.common import ORM


class ProductOut(ORM):
    id: uuid.UUID
    brand_id: uuid.UUID
    sku: str
    title: str
    description: str
    category: str
    price: float
    cost: float
    margin: float
    image_urls: List[str] = []
    attributes: Dict[str, Any] = {}
    status: str
    is_new: bool
    is_bestseller: bool
    is_dead_stock: bool
    is_discounted: bool


class ProductCreateIn(BaseModel):
    sku: str
    title: str
    description: str = ""
    category: str = ""
    price: float = 0
    cost: float = 0
    image_urls: List[str] = []
    attributes: Dict[str, Any] = {}
    is_new: bool = False
    is_bestseller: bool = False
    is_dead_stock: bool = False
    is_discounted: bool = False


class ProductUpdateIn(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    price: float | None = None
    cost: float | None = None
    image_urls: List[str] | None = None
    attributes: Dict[str, Any] | None = None
    is_new: bool | None = None
    is_bestseller: bool | None = None
    is_dead_stock: bool | None = None
    is_discounted: bool | None = None
    status: str | None = None

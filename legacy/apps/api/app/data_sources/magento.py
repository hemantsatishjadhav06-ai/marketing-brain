"""Magento 2 REST connector.

Authenticates with a Bearer admin/integration token. Pulls categories +
products + media so the cockpit can populate the Create form's Category →
Product cascade with real client data.

Usage:
    client = MagentoClient(base_url="https://tennisoutlet.in", token="…")
    categories = client.list_categories()
    products = client.list_products_in_category(cat_id, page_size=100)
    media = client.get_product_media(sku)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator

import httpx


log = logging.getLogger("marketing_brain.magento")


@dataclass
class MagentoCategory:
    external_id: str
    name: str
    parent_id: str | None
    level: int
    path: str
    product_count: int = 0
    image_url: str = ""
    children: list["MagentoCategory"] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "external_id": self.external_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "level": self.level,
            "path": self.path,
            "product_count": self.product_count,
            "image_url": self.image_url,
            "children": [c.as_dict() for c in self.children],
        }


@dataclass
class MagentoProduct:
    sku: str
    name: str
    price: float
    status: int                # 1 = enabled
    type_id: str
    image_url: str = ""
    description: str = ""
    category_ids: list[str] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "sku": self.sku, "name": self.name, "price": self.price, "status": self.status,
            "type_id": self.type_id, "image_url": self.image_url,
            "description": self.description, "category_ids": self.category_ids,
            "attributes": self.attributes,
        }


class MagentoClient:
    def __init__(self, *, base_url: str, token: str, timeout_s: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_s = timeout_s

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/rest/V1/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout_s, headers=self.headers) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            return r.json()

    # ─── categories ─────────────────────────────────────────────────────────
    def list_categories(self, root_id: int = 1) -> list[MagentoCategory]:
        """Flatten the category tree into a list of MagentoCategory."""
        data = self._get("categories", params={"rootCategoryId": root_id})
        out: list[MagentoCategory] = []

        def walk(node: dict, parent_id: str | None = None, depth: int = 0, path: str = ""):
            ext = str(node.get("id"))
            name = node.get("name", "")
            level = int(node.get("level", depth))
            cur_path = f"{path}/{name}" if path else name
            cat = MagentoCategory(
                external_id=ext,
                name=name,
                parent_id=parent_id,
                level=level,
                path=cur_path,
                product_count=int(node.get("product_count", 0)),
            )
            out.append(cat)
            for child in node.get("children_data") or []:
                walk(child, parent_id=ext, depth=depth + 1, path=cur_path)

        walk(data)
        return out

    # ─── products ──────────────────────────────────────────────────────────
    def search_products(
        self,
        *,
        category_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
        sort: str = "created_at",
    ) -> list[MagentoProduct]:
        """SearchCriteria interface — see Magento 2 docs."""
        params: dict = {
            "searchCriteria[currentPage]": page,
            "searchCriteria[pageSize]": page_size,
            "searchCriteria[sortOrders][0][field]": sort,
            "searchCriteria[sortOrders][0][direction]": "DESC",
        }
        if category_id:
            params.update({
                "searchCriteria[filterGroups][0][filters][0][field]": "category_id",
                "searchCriteria[filterGroups][0][filters][0][value]": category_id,
                "searchCriteria[filterGroups][0][filters][0][conditionType]": "eq",
            })
        data = self._get("products", params=params)
        return [self._product_from_dict(p) for p in (data.get("items") or [])]

    def get_product(self, sku: str) -> MagentoProduct | None:
        try:
            data = self._get(f"products/{sku}")
            return self._product_from_dict(data)
        except httpx.HTTPStatusError:
            return None

    def get_product_media(self, sku: str) -> list[dict]:
        try:
            return self._get(f"products/{sku}/media")
        except httpx.HTTPStatusError:
            return []

    # ─── helpers ───────────────────────────────────────────────────────────
    def _product_from_dict(self, p: dict) -> MagentoProduct:
        # primary image: first media_gallery_entries[].file → /media/catalog/product
        image_url = ""
        for entry in p.get("media_gallery_entries") or []:
            if entry.get("disabled"):
                continue
            f = entry.get("file") or ""
            if f:
                image_url = f"{self.base_url}/media/catalog/product{f}"
                break
        # categories
        cat_ids: list[str] = []
        for ext in p.get("extension_attributes") or {}:
            pass
        ext_attrs = p.get("extension_attributes") or {}
        if isinstance(ext_attrs, dict):
            for cl in ext_attrs.get("category_links") or []:
                if cl.get("category_id"):
                    cat_ids.append(str(cl["category_id"]))
        # description from custom_attributes
        description = ""
        attrs = {}
        for ca in p.get("custom_attributes") or []:
            code = ca.get("attribute_code"); val = ca.get("value")
            if code:
                attrs[code] = val
            if code == "description" and isinstance(val, str):
                description = val
        return MagentoProduct(
            sku=str(p.get("sku") or ""),
            name=str(p.get("name") or ""),
            price=float(p.get("price") or 0),
            status=int(p.get("status") or 0),
            type_id=str(p.get("type_id") or ""),
            image_url=image_url,
            description=description,
            category_ids=cat_ids,
            attributes=attrs,
        )

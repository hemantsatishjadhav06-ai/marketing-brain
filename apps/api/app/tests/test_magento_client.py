"""Magento client smoke tests — pure-data helpers (no HTTP)."""
from __future__ import annotations

from app.data_sources.magento import MagentoClient, MagentoCategory


def _client():
    return MagentoClient(base_url="https://example.com/", token="dummy")


def test_base_url_trailing_slash_stripped():
    c = _client()
    assert c.base_url == "https://example.com"


def test_headers_have_bearer():
    c = _client()
    assert c.headers["Authorization"] == "Bearer dummy"
    assert c.headers["Accept"] == "application/json"


def test_product_from_dict_extracts_image_and_attrs():
    c = _client()
    p = c._product_from_dict({
        "sku": "ABC", "name": "Test", "price": 99.5, "status": 1, "type_id": "simple",
        "media_gallery_entries": [
            {"disabled": True, "file": "/x.jpg"},
            {"disabled": False, "file": "/y.jpg"},
        ],
        "custom_attributes": [
            {"attribute_code": "description", "value": "<p>great</p>"},
            {"attribute_code": "brand", "value": "Wilson"},
        ],
        "extension_attributes": {
            "category_links": [{"category_id": "12"}, {"category_id": "34"}]
        },
    })
    assert p.sku == "ABC"
    assert p.image_url.endswith("/y.jpg")
    assert p.description == "<p>great</p>"
    assert "brand" in p.attributes
    assert p.category_ids == ["12", "34"]


def test_category_as_dict_roundtrip():
    cat = MagentoCategory(external_id="5", name="Rackets", parent_id="1", level=2, path="Tennis/Rackets", product_count=12)
    d = cat.as_dict()
    assert d["external_id"] == "5"
    assert d["product_count"] == 12

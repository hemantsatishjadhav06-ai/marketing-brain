"""Brand schemas."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from pydantic import BaseModel

from app.schemas.common import ORM


class BrandOut(ORM):
    id: uuid.UUID
    org_id: uuid.UUID
    sport: str
    name: str
    website_url: str
    timezone: str
    active: bool
    accent_color: str


class BrandCreateIn(BaseModel):
    sport: str  # tennis | padel | pickleball | badminton | squash
    name: str
    website_url: str = ""
    timezone: str = "Asia/Kolkata"
    accent_color: str | None = None


class BrandUpdateIn(BaseModel):
    name: str | None = None
    website_url: str | None = None
    timezone: str | None = None
    active: bool | None = None
    accent_color: str | None = None


class BrandBrainOut(ORM):
    id: uuid.UUID
    brand_id: uuid.UUID
    voice: str
    tone: str
    banned_phrases: List[str] = []
    visual_rules: Dict[str, Any] = {}
    cta_rules: Dict[str, Any] = {}
    platform_rules: Dict[str, Any] = {}
    seo_keywords: List[str] = []
    geo_prompts: List[str] = []
    competitors: List[str] = []
    content_templates: Dict[str, Any] = {}


class BrandBrainUpdateIn(BaseModel):
    voice: str | None = None
    tone: str | None = None
    banned_phrases: List[str] | None = None
    visual_rules: Dict[str, Any] | None = None
    cta_rules: Dict[str, Any] | None = None
    platform_rules: Dict[str, Any] | None = None
    seo_keywords: List[str] | None = None
    geo_prompts: List[str] | None = None
    competitors: List[str] | None = None
    content_templates: Dict[str, Any] | None = None

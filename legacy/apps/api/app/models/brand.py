"""Brands (sport verticals) + brand brain + audiences."""
from __future__ import annotations

import enum
import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, uuid_pk


class Sport(str, enum.Enum):
    tennis = "tennis"
    padel = "padel"
    pickleball = "pickleball"
    badminton = "badminton"
    squash = "squash"


class UserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    growth_head = "growth_head"
    marketer = "marketer"
    intern = "intern"
    viewer = "viewer"


class Brand(Base, TimestampMixin):
    __tablename__ = "brands"
    __table_args__ = (UniqueConstraint("org_id", "sport", name="uq_brand_sport"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), index=True, nullable=False)
    sport: Mapped[str] = mapped_column(String(32), nullable=False)  # tennis | padel | ...
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    website_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    accent_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#CCFF00")


class BrandBrain(Base, TimestampMixin):
    __tablename__ = "brand_brain"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), unique=True, nullable=False)
    voice: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    tone: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    banned_phrases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    visual_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    cta_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    platform_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    seo_keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    geo_prompts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    competitors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    content_templates: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Audience(Base, TimestampMixin):
    __tablename__ = "audiences"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    affinity_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

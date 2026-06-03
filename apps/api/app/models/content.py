"""Content ideas, items, variants, critic reviews, calendar entries."""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, uuid_pk


class ContentStatus(str, enum.Enum):
    idea = "idea"
    drafted = "drafted"
    under_review = "under_review"
    approved = "approved"
    scheduled = "scheduled"
    published = "published"
    failed = "failed"


class ContentIdea(Base, TimestampMixin):
    __tablename__ = "content_ideas"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    angle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")  # ai | human
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idea")


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    idea_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_ideas.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    angle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    product_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idea", index=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")  # ai | human
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class ContentVariant(Base, TimestampMixin):
    __tablename__ = "content_variants"

    id: Mapped[uuid.UUID] = uuid_pk()
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class CriticReview(Base, TimestampMixin):
    __tablename__ = "critic_reviews"

    id: Mapped[uuid.UUID] = uuid_pk()
    content_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="CASCADE"), index=True, nullable=False)
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    weighted_total: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocking_issues: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    fixes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reviewer: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")  # ai | human


class CalendarEntry(Base, TimestampMixin):
    __tablename__ = "calendar_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    angle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idea")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

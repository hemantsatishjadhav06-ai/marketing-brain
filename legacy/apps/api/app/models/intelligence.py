"""Trends + scoring runs (brand-scoped)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, uuid_pk


class Trend(Base, TimestampMixin):
    __tablename__ = "trends"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # google_trends|serp|youtube|competitor
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    signal_strength: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    slope: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False, default=0)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ttl_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ScoringRun(Base, TimestampMixin):
    __tablename__ = "scoring_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), index=True, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)  # product | idea | content_item
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    score_type: Mapped[str] = mapped_column(String(32), nullable=False)  # demand | trend | audience | content
    total: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

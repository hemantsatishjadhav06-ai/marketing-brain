"""Quick-create — agency mode.

Bypasses the calendar. Marketer picks an agent + brand + angle (+ optional
product + overrides) → backend creates an ad-hoc CalendarEntry on today + fires
the agent → returns the resulting content_item_id so the UI can redirect to Studio.

The overrides block lets the agency tune model / tone / length / custom
instructions per request without permanently changing brand brain.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.registry import AGENTS, draft_entry
from app.core.db import get_db
from app.core.security import require_role
from app.models.brand import Brand
from app.models.content import CalendarEntry
from app.models.tenancy import User
from app.services.agent_metadata import AGENT_METADATA, list_metadata

router = APIRouter()


@router.get("/agents")
def list_agents():
    """All registered agents with their fields — used by the /create UI."""
    return list_metadata()


class Overrides(BaseModel):
    tone: str | None = None
    length: str | None = None       # "short" | "medium" | "long"
    model: str | None = None        # "auto" | "drafting" | "reasoning"
    custom_instructions: str | None = None


class CreateBody(BaseModel):
    brand_id: uuid.UUID
    agent_name: str = Field(..., max_length=64)
    angle: str = Field(..., min_length=2, max_length=400)
    platform: str | None = None              # falls back to agent default
    content_type: str | None = None          # falls back to agent default
    product_id: uuid.UUID | None = None      # legacy single-product
    product_ids: list[uuid.UUID] | None = None  # 1-5 products for comparisons / carousels
    overrides: Overrides | None = None


@router.post("/create")
def quick_create(
    body: CreateBody,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    if body.agent_name not in AGENTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown agent: {body.agent_name}")
    brand = db.get(Brand, body.brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")

    meta = AGENT_METADATA[body.agent_name]
    platform = body.platform or meta.default_platform
    content_type = body.content_type or meta.default_content_type
    # multi-product preferred; fall back to legacy single
    if body.product_ids:
        product_ids = [str(p) for p in body.product_ids][:5]
    elif body.product_id:
        product_ids = [str(body.product_id)]
    else:
        product_ids = []

    entry = CalendarEntry(
        brand_id=body.brand_id,
        date=date.today(),
        platform=platform,
        content_type=content_type,
        product_ids=product_ids,
        angle=body.angle.strip(),
        agent_name=body.agent_name,
        score=0,
        reason=f"ad-hoc create by {user.email}" + (f" · overrides: {body.overrides.model_dump(exclude_none=True)}" if body.overrides else ""),
        status="planned",
        position=0,
    )
    db.add(entry)
    db.flush()

    # Stash overrides on the entry so the agent can pick them up.
    # We piggy-back on the reason field's structure today; Phase 6 swaps for a
    # dedicated CalendarEntry.payload column.
    if body.overrides:
        entry.reason = (entry.reason + " | " + body.overrides.model_dump_json())[:1900]
    db.commit()

    try:
        result = draft_entry(db, body.brand_id, entry.id, body.agent_name)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {
        "content_item_id": result.get("content_item_id"),
        "agent": body.agent_name,
        "platform": platform,
        "content_type": content_type,
        "ad_hoc_entry_id": str(entry.id),
        **{k: v for k, v in result.items() if k not in ("content_item_id",)},
    }

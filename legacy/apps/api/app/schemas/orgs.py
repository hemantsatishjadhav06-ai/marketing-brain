"""Org schemas."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from pydantic import BaseModel

from app.schemas.common import ORM


class OrgOut(ORM):
    id: uuid.UUID
    name: str
    timezone: str
    monthly_cost_cap_usd: float
    settings: Dict[str, Any] = {}


class OrgUpdateIn(BaseModel):
    name: str | None = None
    timezone: str | None = None
    monthly_cost_cap_usd: float | None = None
    settings: Dict[str, Any] | None = None


class CostMeter(BaseModel):
    cap_usd: float
    spent_usd: float
    remaining_usd: float
    pct_used: float

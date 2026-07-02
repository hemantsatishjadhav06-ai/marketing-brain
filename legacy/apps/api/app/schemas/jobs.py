"""Job schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.schemas.common import ORM


class JobOut(ORM):
    id: uuid.UUID
    org_id: uuid.UUID
    brand_id: Optional[uuid.UUID]
    type: str
    status: str
    payload: Dict[str, Any] = {}
    result: Dict[str, Any] = {}
    error: str
    cost_usd: float
    model: str
    tokens_in: int
    tokens_out: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    progress: int
    created_at: datetime


class JobCreateIn(BaseModel):
    type: str
    brand_id: Optional[uuid.UUID] = None
    payload: Dict[str, Any] = {}

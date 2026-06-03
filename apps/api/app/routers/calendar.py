"""Calendar — list + generate stubs."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.content import CalendarEntry
from app.models.tenancy import User

router = APIRouter()


@router.get("/{brand_id}/calendar")
def list_entries(brand_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    rows = db.execute(
        select(CalendarEntry).where(CalendarEntry.brand_id == brand_id).order_by(CalendarEntry.date)
    ).scalars().all()
    return [
        {
            "id": str(e.id),
            "date": e.date.isoformat(),
            "platform": e.platform,
            "content_type": e.content_type,
            "angle": e.angle,
            "score": float(e.score),
            "reason": e.reason,
            "status": e.status,
            "agent_name": e.agent_name,
        }
        for e in rows
    ]


@router.post("/{brand_id}/calendar/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_calendar(
    brand_id: uuid.UUID,
    user: User = Depends(require_role("growth_head")),
    db: Session = Depends(get_db),
):
    """Phase 1 wiring: queues a 'calendar.generate' job → CalendarAgent.run(brand_id).
    Phase 0: stub.
    """
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return {"status": "not_implemented_in_phase_0", "brand_id": str(brand_id)}

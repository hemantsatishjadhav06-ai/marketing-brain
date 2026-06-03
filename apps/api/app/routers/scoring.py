"""Scoring endpoints — landing in Phase 1; Phase 0 ships the route stub."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.tenancy import User

router = APIRouter()


@router.post("/{brand_id}/score/run")
def run_scoring(
    brand_id: uuid.UUID,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    """Phase 1: this queues a scoring job that computes Product Demand + Content Priority
    for every product and stores `scoring_runs` rows.

    Phase 0: returns a stub so the UI can wire the button.
    """
    brand = db.get(Brand, brand_id)
    if not brand or brand.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return {"status": "not_implemented_in_phase_0", "brand_id": str(brand_id)}

"""Org info + cost meter + white-label theme."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.cost_guard import month_to_date_spend
from app.core.db import get_db
from app.core.security import require_user
from app.models.tenancy import Org, User
from app.schemas.orgs import CostMeter, OrgOut, OrgUpdateIn

router = APIRouter()


class ThemeIn(BaseModel):
    brand_name: Optional[str] = None
    accent_color: Optional[str] = None
    logo_url: Optional[str] = None
    hide_powered_by: Optional[bool] = None


@router.get("/me", response_model=OrgOut)
def my_org(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return db.get(Org, user.org_id)


@router.patch("/me", response_model=OrgOut)
def update_my_org(payload: OrgUpdateIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(org, k, v)
    db.commit()
    db.refresh(org)
    return org


@router.get("/me/theme")
def get_theme(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """White-label theming. Stored in Org.settings.theme."""
    org = db.get(Org, user.org_id)
    return (org.settings or {}).get("theme", {
        "brand_name": org.name,
        "accent_color": "#CCFF00",
        "logo_url": "",
        "hide_powered_by": False,
    })


@router.put("/me/theme")
def set_theme(body: ThemeIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    settings_blob = dict(org.settings or {})
    theme = dict(settings_blob.get("theme") or {})
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            theme[k] = v
    settings_blob["theme"] = theme
    org.settings = settings_blob
    db.commit()
    return theme


@router.get("/me/cost", response_model=CostMeter)
def cost_meter(user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    cap = Decimal(org.monthly_cost_cap_usd or 0)
    spent = month_to_date_spend(db, user.org_id)
    remaining = max(cap - spent, Decimal(0))
    pct = float(spent / cap) * 100 if cap > 0 else 0.0
    return CostMeter(
        cap_usd=float(cap),
        spent_usd=float(spent),
        remaining_usd=float(remaining),
        pct_used=round(pct, 2),
    )

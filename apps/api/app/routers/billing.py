"""Billing endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role
from app.models.tenancy import User
from app.services.billing import create_checkout, get_subscription_summary

router = APIRouter()


@router.get("/summary")
def summary(user: User = Depends(require_role("admin"))):
    return get_subscription_summary(user.org_id)


class CheckoutIn(BaseModel):
    success_url: str
    cancel_url: str
    price_id: str | None = None


@router.post("/checkout")
def checkout(
    body: CheckoutIn,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    sess = create_checkout(
        db, user.org_id,
        price_id=body.price_id,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return {"id": sess.id, "url": sess.url}

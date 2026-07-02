"""Auth: login (with optional 2FA gate), register (admin-invite), me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    require_role,
    require_user,
    verify_password,
)
from app.models.tenancy import Org, User
from app.schemas.auth import LoginIn, MeOut, RegisterIn, TokenOut

router = APIRouter()


def _totp_enabled(org: Org, user_id) -> bool:
    settings_blob = (org.settings or {}).get("totp") or {}
    return bool(settings_blob.get(str(user_id), {}).get("enabled"))


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """Returns a TokenOut when 2FA is off, or a `{requires_2fa, user_id}` envelope
    when the user has 2FA enabled. The client then posts to /auth/2fa/verify-login."""
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    org = db.get(Org, user.org_id)
    if _totp_enabled(org, user.id):
        return {"requires_2fa": True, "user_id": str(user.id)}
    token = create_access_token(user.id, user.org_id, user.role)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=MeOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterIn,
    db: Session = Depends(get_db),
    inviter: User = Depends(require_role("admin")),
):
    """Admins/Owners invite new team members into their org."""
    if db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    user = User(
        org_id=inviter.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(require_user)):
    return user

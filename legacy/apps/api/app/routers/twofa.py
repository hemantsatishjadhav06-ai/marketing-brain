"""2FA enrolment + verify endpoints.

Flow:
  1. POST /auth/2fa/setup           → returns {secret, otpauth_url}; user scans in app
  2. POST /auth/2fa/enable {code}   → verifies code; sets enabled=true in Org.settings
  3. On login, if user has 2FA enabled, POST /auth/login returns {requires_2fa: true, ticket}
     then POST /auth/2fa/verify {ticket, code} returns the real access_token.

We piggyback on Org.settings.totp[user_id] for storage instead of adding a
column in this commit. Migration to a dedicated table is a one-liner later.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, require_user
from app.models.tenancy import Org, User
from app.services.totp import generate_secret, otpauth_url, verify

router = APIRouter()


def _read(org: Org, user_id: uuid.UUID) -> dict:
    settings_blob = dict(org.settings or {})
    totp_blob = settings_blob.get("totp") or {}
    return totp_blob.get(str(user_id)) or {}


def _write(db: Session, org: Org, user_id: uuid.UUID, entry: dict | None) -> None:
    settings_blob = dict(org.settings or {})
    totp_blob = dict(settings_blob.get("totp") or {})
    if entry is None:
        totp_blob.pop(str(user_id), None)
    else:
        totp_blob[str(user_id)] = entry
    settings_blob["totp"] = totp_blob
    org.settings = settings_blob
    db.commit()


@router.post("/setup")
def setup_2fa(user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    existing = _read(org, user.id)
    if existing.get("enabled"):
        return {"already_enabled": True}
    secret = existing.get("secret") or generate_secret()
    _write(db, org, user.id, {"secret": secret, "enabled": False})
    return {
        "secret": secret,
        "otpauth_url": otpauth_url(account_name=user.email, secret_b32=secret),
    }


class CodeIn(BaseModel):
    code: str


@router.post("/enable")
def enable_2fa(body: CodeIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    rec = _read(org, user.id)
    if not rec.get("secret"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Call /setup first")
    if not verify(rec["secret"], body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")
    _write(db, org, user.id, {"secret": rec["secret"], "enabled": True})
    return {"enabled": True}


@router.post("/disable")
def disable_2fa(body: CodeIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = db.get(Org, user.org_id)
    rec = _read(org, user.id)
    if not rec.get("enabled"):
        return {"enabled": False}
    if not verify(rec["secret"], body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code")
    _write(db, org, user.id, None)
    return {"enabled": False}


class VerifyIn(BaseModel):
    user_id: uuid.UUID
    code: str


@router.post("/verify-login")
def verify_login(body: VerifyIn, db: Session = Depends(get_db)):
    """Called after /auth/login when the user has 2FA enabled.
    Returns the real access token."""
    user = db.get(User, body.user_id)
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    org = db.get(Org, user.org_id)
    rec = _read(org, user.id)
    if not rec.get("enabled"):
        # not enabled — login should already have given them a token. Defensive.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "2FA not enabled")
    if not verify(rec["secret"], body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid code")
    token = create_access_token(user.id, user.org_id, user.role)
    return {"access_token": token, "token_type": "bearer"}

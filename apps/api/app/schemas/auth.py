"""Auth schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr

from app.schemas.common import ORM


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    role: str = "marketer"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(ORM):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    role: str
    active: bool

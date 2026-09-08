"""Multi-company onboarding routes: signup, invites, password reset, and the
master account's company overview.

Access model:
  * /api/signup and /api/invites/accept and /api/auth/forgot|reset are public
    (signup additionally gated by SIGNUPS_OPEN).
  * Managing a company's invites requires the master (admin) or that company's
    own owner.
  * /api/companies is master-only.
"""
from fastapi import APIRouter, Depends

from ._shared import *  # noqa: F401,F403
from ..services import onboarding

router = APIRouter()


class SignupIn(BaseModel):
    company_name: str
    email: str
    password: str
    website: str = ""


class InviteIn(BaseModel):
    email: str
    role: str = "client"


class AcceptIn(BaseModel):
    token: str
    password: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    password: str


def _can_manage_brand(user, bid):
    """Master, or this company's own owner/admin."""
    if user.get("role") == "admin":
        return
    if user.get("brand_id") == bid and user.get("role") in ("owner", "admin"):
        return
    raise HTTPException(403, "Only the master account or this company's owner can do that")


@router.post("/api/signup")
def signup(body: SignupIn):
    if not onboarding.signups_open():
        raise HTTPException(403, "Self-serve signup is closed — ask the team to create your company.")
    try:
        return onboarding.signup(body.company_name, body.website, body.email, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/brands/{bid}/invites")
def invite_user(bid: str, body: InviteIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _can_manage_brand(user, bid)
    try:
        return onboarding.create_invite(bid, body.email, body.role, invited_by=user.get("uid", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/brands/{bid}/invites")
def brand_invites(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    _can_manage_brand(user, bid)
    return {"invites": onboarding.list_invites(bid)}


@router.post("/api/invites/accept")
def accept_invite(body: AcceptIn):
    try:
        return onboarding.accept_invite(body.token, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/auth/forgot")
def forgot(body: ForgotIn):
    # Never reveals whether the email exists.
    return onboarding.request_reset(body.email)


@router.post("/api/auth/reset")
def reset(body: ResetIn):
    try:
        return onboarding.reset_password(body.token, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/companies")
def list_companies(user=Depends(current_user)):
    _admin_only(user)
    return {"companies": onboarding.companies()}

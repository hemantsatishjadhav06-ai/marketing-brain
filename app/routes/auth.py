import re

from fastapi import APIRouter, Request
from ._shared import *  # noqa: F401,F403
from ..core import guard

router = APIRouter()

LOGIN_LIMIT = 10       # attempts
LOGIN_WINDOW = 300     # per 5 minutes, per IP


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    # Active in production (where auth is enforced); bypassed on dev/test
    # instances that run with DIRECT_ACCESS on.
    if not direct_access_enabled():
        ip = guard.client_ip(request)
        if not guard.rate_ok(f"login:{ip}", LOGIN_LIMIT, LOGIN_WINDOW):
            raise HTTPException(429, "Too many login attempts — wait a few minutes and try again.")
        # Per-account throttle: cannot be dodged by spoofing client addresses.
        if not guard.rate_ok(f"login-acct:{(body.email or '').strip().lower()}", LOGIN_LIMIT, LOGIN_WINDOW):
            raise HTTPException(429, "Too many login attempts for this account — wait a few minutes and try again.")
    u = db.get_user_by_email(body.email)
    if not u or not auth.check_pw(body.password, u["pw_hash"]):
        raise HTTPException(401, "Wrong email or password")
    if auth.needs_rehash(u["pw_hash"]):
        u["pw_hash"] = auth.hash_pw(body.password)
        db.update_user_password(u["id"], u["pw_hash"])
    return {"token": auth.make_token(u["id"], u["role"], u.get("brand_id") or "", pwv=auth.pw_version(u["pw_hash"])),
            "role": u["role"], "brand_id": u.get("brand_id") or "", "email": u["email"]}


@router.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user


@router.get("/api/users")
def users(user=Depends(current_user)):
    _admin_only(user)
    return db.list_users()


@router.post("/api/users")
def add_user(body: UserIn, user=Depends(current_user)):
    _admin_only(user)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", (body.email or "").strip()):
        raise HTTPException(400, "Enter a valid email address")
    if len(body.password or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.get_user_by_email(body.email):
        raise HTTPException(400, "A user with this email already exists")
    if body.role == "client" and not body.brand_id:
        raise HTTPException(400, "Client logins need a brand_id")
    uid = db.create_user(body.email, auth.hash_pw(body.password), body.role, body.brand_id)
    return {"id": uid, "email": body.email, "role": body.role, "brand_id": body.brand_id}


@router.delete("/api/users/{uid}")
def remove_user(uid: str, user=Depends(current_user)):
    _admin_only(user)
    db.delete_user(uid)
    return {"ok": True}


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
    rows = db.list_users()
    try:
        assigned = db.all_assignments()
    except Exception:
        assigned = {}
    for r in rows:
        if r.get("role") == "manager":
            r["brand_ids"] = assigned.get(r["id"], [])
    return rows


@router.post("/api/users")
def add_user(body: UserIn, user=Depends(current_user)):
    _admin_only(user)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", (body.email or "").strip()):
        raise HTTPException(400, "Enter a valid email address")
    if len(body.password or "") < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.get_user_by_email(body.email):
        raise HTTPException(400, "A user with this email already exists")
    if body.role not in ROLES:
        raise HTTPException(400, f"role must be one of: {', '.join(ROLES)}")
    if body.role in ("client", "owner") and not body.brand_id:
        raise HTTPException(400, f"{body.role.capitalize()} logins need a brand_id")
    if body.brand_id and not db.get_brand(body.brand_id):
        raise HTTPException(400, "Unknown brand_id")
    for b in body.brand_ids or []:
        if not db.get_brand(b):
            raise HTTPException(400, f"Unknown brand in brand_ids: {b}")
    uid = db.create_user(body.email, auth.hash_pw(body.password), body.role,
                         body.brand_id if body.role in ("client", "owner") else "")
    out = {"id": uid, "email": body.email, "role": body.role, "brand_id": body.brand_id}
    if body.role == "manager":
        out["brand_ids"] = db.set_assignments(uid, body.brand_ids or [])
    return out


class AssignIn(BaseModel):
    brand_ids: list[str] = []


@router.put("/api/users/{uid}/brands")
def assign_brands(uid: str, body: AssignIn, user=Depends(current_user)):
    """Set which clients an account-manager runs. Takes effect on their next request."""
    _admin_only(user)
    target = db.get_user(uid)
    if not target:
        raise HTTPException(404, "User not found")
    if target.get("role") != "manager":
        raise HTTPException(400, "Only manager accounts take brand assignments")
    for b in body.brand_ids:
        if not db.get_brand(b):
            raise HTTPException(400, f"Unknown brand: {b}")
    return {"ok": True, "user_id": uid, "brand_ids": db.set_assignments(uid, body.brand_ids)}


@router.get("/api/users/{uid}/brands")
def assigned_brands(uid: str, user=Depends(current_user)):
    _admin_only(user)
    if not db.get_user(uid):
        raise HTTPException(404, "User not found")
    return {"user_id": uid, "brand_ids": db.get_assignments(uid)}


@router.delete("/api/users/{uid}")
def remove_user(uid: str, user=Depends(current_user)):
    _admin_only(user)
    db.delete_user(uid)
    return {"ok": True}


from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/auth/login")
def login(body: LoginIn):
    u = db.get_user_by_email(body.email)
    if not u or not auth.check_pw(body.password, u["pw_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return {"token": auth.make_token(u["id"], u["role"], u.get("brand_id") or ""),
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


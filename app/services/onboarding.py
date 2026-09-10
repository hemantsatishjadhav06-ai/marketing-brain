"""Self-serve multi-company onboarding (Layer 0 / Agent 0).

Turns the single-admin app into a real multi-tenant SaaS the master account can
run on top of:

  master (role 'admin')  — sees and manages every company; created out of band.
  owner  (role 'owner')  — owns one company (brand); can invite its users.
  client (role 'client') — an individual user locked to one company.

Three flows live here, all on the same 3-backend store as the rest of the app:

  * Company signup   — create a company (brand) + its owner in one step.
  * User invites     — an owner/master invites a teammate to a company by token.
  * Password reset   — request a reset token, then set a new password.

Public signup is gated by the SIGNUPS_OPEN env flag (off by default) so opening
account creation to the world is a deliberate switch, never an accident. Invite
and reset tokens carry their own expiry.
"""
from __future__ import annotations

import os
import re
import time

from ..core import database as db, auth

INVITE_TABLE = "invites"
RESET_TABLE = "password_resets"
INVITE_TTL = 7 * 86400      # 7 days
RESET_TTL = 3600            # 1 hour
ROLES = ("admin", "owner", "client")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def signups_open() -> bool:
    return os.environ.get("SIGNUPS_OPEN", "").strip().lower() in {"1", "true", "yes", "on"}


def _dev_tokens() -> bool:
    # When set, reset tokens are returned in the API response (no email wired yet).
    return os.environ.get("AUTH_DEV_TOKENS", "").strip().lower() in {"1", "true", "yes", "on"}


def _slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "company"


def _unique_slug(name):
    base = _slugify(name)
    try:
        existing = {b.get("slug") for b in db.list_brands()}
    except Exception:
        existing = set()
    if base not in existing:
        return base
    return base + "-" + db.new_id()[:4]


# ---------- company signup ----------

def signup(company_name, website, email, password):
    """Create a company (brand) and its owner user. Returns ids + a session token."""
    company_name = (company_name or "").strip()
    email = (email or "").strip().lower()
    if not company_name or not email or not password:
        raise ValueError("company_name, email and password are required")
    if not EMAIL_RE.match(email):
        raise ValueError("enter a valid email address")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if db.get_user_by_email(email):
        raise ValueError("a user with this email already exists")

    bid = db.create_brand(company_name, _unique_slug(company_name), (website or "").strip(), {})
    pw_hash = auth.hash_pw(password)
    uid = db.create_user(email, pw_hash, role="owner", brand_id=bid)
    token = auth.make_token(uid, "owner", bid, pwv=auth.pw_version(pw_hash))
    return {"brand_id": bid, "user_id": uid, "role": "owner", "email": email, "token": token}


# ---------- invites ----------

def create_invite(brand_id, email, role, invited_by=""):
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("email is required")
    if role not in ("owner", "client"):
        raise ValueError("role must be 'owner' or 'client'")
    if db.get_user_by_email(email):
        raise ValueError("a user with this email already exists")
    token = db.new_id() + db.new_id()  # 24 hex chars
    iid = db.insert_doc(
        INVITE_TABLE, brand_id, {"invited_by": invited_by},
        email=email, role=role, token=token, status="pending",
    )
    return {"id": iid, "email": email, "role": role, "brand_id": brand_id,
            "token": token, "accept_path": f"/api/invites/accept"}


def list_invites(brand_id):
    return [
        {"id": r["id"], "email": r.get("email"), "role": r.get("role"),
         "status": r.get("status"), "created_at": r.get("created_at")}
        for r in db.list_docs(INVITE_TABLE, brand_id)
    ]


def accept_invite(token, password):
    if not token or not password:
        raise ValueError("token and password are required")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    inv = db.get_doc_by(INVITE_TABLE, token=token)
    if not inv or inv.get("status") != "pending":
        raise ValueError("this invite is invalid or already used")
    if (inv.get("created_at") or 0) + INVITE_TTL < time.time():
        db.update_doc(INVITE_TABLE, inv["id"], status="expired")
        raise ValueError("this invite has expired")
    email = inv.get("email")
    if db.get_user_by_email(email):
        db.update_doc(INVITE_TABLE, inv["id"], status="accepted")
        raise ValueError("a user with this email already exists")
    pw_hash = auth.hash_pw(password)
    uid = db.create_user(email, pw_hash, role=inv.get("role") or "client",
                         brand_id=inv.get("brand_id"))
    db.update_doc(INVITE_TABLE, inv["id"], status="accepted")
    token_out = auth.make_token(uid, inv.get("role") or "client", inv.get("brand_id"), pwv=auth.pw_version(pw_hash))
    return {"user_id": uid, "email": email, "role": inv.get("role"),
            "brand_id": inv.get("brand_id"), "token": token_out}


# ---------- password reset ----------

def request_reset(email):
    """Issue a reset token. Always returns ok (never reveals whether the email
    exists); includes the token only when AUTH_DEV_TOKENS is set (no email wired)."""
    email = (email or "").strip().lower()
    out = {"ok": True}
    u = db.get_user_by_email(email) if email else None
    if u:
        token = db.new_id() + db.new_id()
        db.insert_doc(RESET_TABLE, "", {"user_id": u["id"], "email": email},
                      token=token, status="pending")
        if _dev_tokens():
            out["reset_token"] = token
    return out


def reset_password(token, new_password):
    if not token or not new_password:
        raise ValueError("token and new password are required")
    if len(new_password) < 8:
        raise ValueError("password must be at least 8 characters")
    row = db.get_doc_by(RESET_TABLE, token=token)
    if not row or row.get("status") != "pending":
        raise ValueError("this reset link is invalid or already used")
    if (row.get("created_at") or 0) + RESET_TTL < time.time():
        db.update_doc(RESET_TABLE, row["id"], status="expired")
        raise ValueError("this reset link has expired")
    uid = (row.get("payload") or {}).get("user_id")
    if not uid:
        raise ValueError("this reset link is invalid")
    db.update_user_password(uid, auth.hash_pw(new_password))
    db.update_doc(RESET_TABLE, row["id"], status="used")
    return {"ok": True}


# ---------- master overview ----------

def companies():
    """Every company (brand) with its user roster — the master account's view."""
    users_by_brand = {}
    for u in db.list_users():
        users_by_brand.setdefault(u.get("brand_id") or "", []).append(
            {"id": u["id"], "email": u["email"], "role": u.get("role")})
    out = []
    for b in db.list_brands():
        roster = users_by_brand.get(b["id"], [])
        owner = next((u["email"] for u in roster if u["role"] == "owner"), None)
        out.append({
            "brand_id": b["id"], "name": b["name"], "slug": b.get("slug"),
            "website": b.get("website"), "status": b.get("status"),
            "owner": owner, "user_count": len(roster), "users": roster,
        })
    return out

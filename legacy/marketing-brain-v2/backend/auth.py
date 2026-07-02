"""Lightweight auth: salted password hashes + HMAC-signed bearer tokens.

Roles:
  admin  — sees and manages every brand, creates client logins.
  client — locked to exactly one brand workspace.
"""
import base64
import hashlib
import hmac
import json
import os
import time

SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me")
TOKEN_TTL = 30 * 86400  # 30 days


def hash_pw(pw, salt=None):
    salt = salt or os.urandom(8).hex()
    return salt + ":" + hashlib.sha256((salt + pw).encode()).hexdigest()


def check_pw(pw, stored):
    try:
        salt, h = stored.split(":", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hashlib.sha256((salt + pw).encode()).hexdigest(), h)


def _sign(raw):
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:40]


def make_token(uid, role, brand_id=""):
    payload = {"uid": uid, "role": role, "brand_id": brand_id or "", "exp": time.time() + TOKEN_TTL}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return raw + "." + _sign(raw)


def verify_token(token):
    """Returns payload dict or None."""
    try:
        raw, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sign(raw), sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

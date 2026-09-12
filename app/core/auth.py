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

DEFAULT_SECRET = "dev-secret-change-me"
SECRET = os.environ.get("SECRET_KEY", DEFAULT_SECRET)
TOKEN_TTL = 30 * 86400  # 30 days
PBKDF2_ITERS = 210_000  # OWASP guidance for PBKDF2-HMAC-SHA256


def hash_pw(pw, salt=None):
    """PBKDF2-HMAC-SHA256. A single unsalted-work SHA-256 round was GPU-crackable
    at billions/sec; this adds a real work factor. Format: pbkdf2$iters$salt$hex."""
    salt = salt or os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), PBKDF2_ITERS)
    return f"pbkdf2${PBKDF2_ITERS}${salt}${dk.hex()}"


def check_pw(pw, stored):
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iters, salt, h = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), int(iters))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(dk.hex(), h)
    # legacy salt:sha256 rows stay verifiable so nobody is locked out; login
    # re-hashes them on the next successful sign-in (see needs_rehash).
    try:
        salt, h = stored.split(":", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hashlib.sha256((salt + pw).encode()).hexdigest(), h)


def pw_version(pw_hash):
    """Short fingerprint of the stored hash. Embedded in tokens so a password
    change/reset invalidates every session issued before it."""
    return hashlib.sha256((pw_hash or "").encode()).hexdigest()[:12]


def needs_rehash(stored):
    return not (stored or "").startswith(f"pbkdf2${PBKDF2_ITERS}$")


def _sign(raw):
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:40]


def make_token(uid, role, brand_id="", pwv=""):
    payload = {"uid": uid, "role": role, "brand_id": brand_id or "", "exp": time.time() + TOKEN_TTL}
    if pwv:
        payload["pwv"] = pwv
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

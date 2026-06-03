"""TOTP 2FA — minimal RFC 6238 implementation (no external crypto deps).

We store the shared secret in User.password_hash's sibling field? No — we add
a `totp_secret` column via Alembic migration. For Phase 4 we stuff it into a
lightweight per-user row in Org.settings.totp[user_id] to avoid a migration in
this commit; in Phase 5 it moves to a `user_secrets` table.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote


def generate_secret(length: int = 20) -> str:
    """RFC 4226: 160-bit secret, base32-encoded."""
    return base64.b32encode(os.urandom(length)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * ((8 - len(secret_b32) % 8) % 8))
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code_int = (
        (h[offset] & 0x7F) << 24
        | (h[offset + 1] & 0xFF) << 16
        | (h[offset + 2] & 0xFF) << 8
        | (h[offset + 3] & 0xFF)
    )
    return str(code_int % (10 ** digits)).zfill(digits)


def now_code(secret_b32: str, step: int = 30, digits: int = 6) -> str:
    return _hotp(secret_b32, int(time.time()) // step, digits)


def verify(secret_b32: str, code: str, *, window: int = 1, step: int = 30, digits: int = 6) -> bool:
    if not code or not code.isdigit():
        return False
    now = int(time.time()) // step
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret_b32, now + offset, digits), code):
            return True
    return False


def otpauth_url(*, account_name: str, secret_b32: str, issuer: str = "Marketing Brain") -> str:
    label = quote(f"{issuer}:{account_name}", safe="")
    params = f"secret={secret_b32}&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits=6&period=30"
    return f"otpauth://totp/{label}?{params}"

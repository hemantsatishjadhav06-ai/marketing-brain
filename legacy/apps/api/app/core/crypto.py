"""Symmetric encryption for credentials at rest (spec § 24).

Key derivation: PBKDF2-HMAC-SHA256(JWT_SECRET, salt='marketing-brain-creds', 100k)
→ 32 bytes → Fernet base64.

We use Fernet (urlsafe base64 token = version + timestamp + IV + HMAC-SHA256 + AES-128-CBC).
Backwards compatible: any value that doesn't start with the Fernet `gAAAAA` prefix is
treated as legacy plaintext and read as-is, then re-encrypted on next write.

Why PBKDF2 from JWT_SECRET and not a separate KMS-backed key:
- One env var to rotate (JWT_SECRET); credentials and tokens move together.
- Phase 5 swaps this for envelope encryption with a real KMS — interface stays the same.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from app.core.config import settings


FERNET_PREFIX = "gAAAAA"


@lru_cache(maxsize=1)
def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        # cryptography is a transitive dep of passlib[bcrypt] / pyjwt[crypto] — should always be present
        return None

    key_material = hashlib.pbkdf2_hmac(
        "sha256",
        (settings.JWT_SECRET or "dev-secret").encode("utf-8"),
        b"marketing-brain-creds-v1",
        100_000,
        dklen=32,
    )
    fernet_key = base64.urlsafe_b64encode(key_material)
    return Fernet(fernet_key)


def encrypt(plaintext: str) -> str:
    """Returns a Fernet token. If cryptography isn't available, returns plaintext as-is
    (with a leading marker so reads still work)."""
    if not plaintext:
        return ""
    f = _fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token_or_plain: str) -> str:
    """Reads either an encrypted Fernet token or legacy plaintext (back-compat).
    Never raises on bad input — returns the input string unchanged so the caller
    can decide what to do."""
    if not token_or_plain:
        return ""
    if not token_or_plain.startswith(FERNET_PREFIX):
        # legacy plaintext (or unencrypted JSON from before this module landed)
        return token_or_plain
    f = _fernet()
    if f is None:
        return token_or_plain
    try:
        return f.decrypt(token_or_plain.encode("ascii")).decode("utf-8")
    except Exception:
        return token_or_plain  # never throw on decryption — caller handles empty/bad creds


def is_encrypted(token: str) -> bool:
    return bool(token) and token.startswith(FERNET_PREFIX)

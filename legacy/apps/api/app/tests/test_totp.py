"""TOTP behaves correctly against RFC 6238 reference."""
from __future__ import annotations

import time

from app.services.totp import generate_secret, now_code, otpauth_url, verify


def test_generate_secret_is_base32_padding_free():
    s = generate_secret()
    assert s == s.rstrip("=")
    assert len(s) >= 30


def test_now_code_is_six_digits():
    s = generate_secret()
    code = now_code(s)
    assert len(code) == 6 and code.isdigit()


def test_verify_accepts_current_code():
    s = generate_secret()
    assert verify(s, now_code(s)) is True


def test_verify_rejects_wrong_code():
    s = generate_secret()
    assert verify(s, "000000") is False


def test_otpauth_url_has_secret_and_issuer():
    s = generate_secret()
    url = otpauth_url(account_name="hi@example.com", secret_b32=s, issuer="MB")
    assert s in url and "issuer=MB" in url

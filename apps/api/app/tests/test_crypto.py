"""Symmetric credential encryption — round-trips, back-compat, no-throw on bad input."""
from __future__ import annotations

from app.core.crypto import decrypt, encrypt, is_encrypted


def test_round_trip():
    secret = '{"bearer_token": "AAA-secret-123"}'
    enc = encrypt(secret)
    assert enc != secret
    assert is_encrypted(enc)
    assert decrypt(enc) == secret


def test_legacy_plaintext_passes_through():
    plain = '{"legacy": true}'
    assert not is_encrypted(plain)
    assert decrypt(plain) == plain


def test_decrypt_never_raises_on_bad_input():
    assert decrypt("") == ""
    assert decrypt("garbage") == "garbage"
    assert decrypt("gAAAAA-totally-not-valid") in ("gAAAAA-totally-not-valid", "")


def test_empty_encrypt_returns_empty():
    assert encrypt("") == ""

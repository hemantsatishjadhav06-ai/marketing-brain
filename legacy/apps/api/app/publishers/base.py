"""Common publisher interface.

A Publisher takes a ContentItem and a PublishTarget and returns a PublishResult.
The result is what we persist on a PublishLog row.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.models.content import ContentItem
from app.models.publishing import PublishTarget


@dataclass
class PublishResult:
    ok: bool
    status: str                 # "published" | "exported" | "failed" | "scheduled"
    external_id: str = ""       # platform-side id
    url: str = ""               # public URL of the post if available
    response: dict = field(default_factory=dict)
    error: str = ""


class Publisher(Protocol):
    """Implemented per platform. Concrete classes live in publishers/<name>.py."""

    name: str

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult: ...


def credentials(target: PublishTarget) -> dict:
    """credentials_ref is a Fernet-encrypted JSON blob (spec § 24).
    Falls back to legacy plaintext JSON if the value was stored before
    encryption landed — those get re-encrypted on next write."""
    import json
    from app.core.crypto import decrypt

    raw = (target.credentials_ref or "").strip()
    if not raw:
        return {}
    try:
        decoded = decrypt(raw)
        return json.loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return {}

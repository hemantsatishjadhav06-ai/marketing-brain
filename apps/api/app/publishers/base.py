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
    """credentials_ref is a JSON-encoded blob (we keep it simple for Phase 3;
    Phase 4 will move secrets to a real KV store with envelope encryption)."""
    import json

    raw = (target.credentials_ref or "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}

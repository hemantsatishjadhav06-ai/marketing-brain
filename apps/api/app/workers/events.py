"""Emit SSE-compatible events via Redis pub/sub.

Pattern from V1: every state transition emits one event. Persistence to a
`job_events` table can be added in Phase 1 when we want history.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import redis

from app.core.config import settings


_r: redis.Redis | None = None


def _client() -> redis.Redis:
    global _r
    if _r is None:
        _r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _r


def emit(job_id: str | uuid.UUID, *, status: str, message: str = "", data: dict | None = None) -> None:
    payload = {
        "job_id": str(job_id),
        "status": status,
        "message": message,
        "data": data or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _client().publish(f"jobs.{job_id}", json.dumps(payload))

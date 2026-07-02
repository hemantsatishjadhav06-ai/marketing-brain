"""SSE: live job updates via Redis pub/sub."""
from __future__ import annotations

import asyncio
import json
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.security import decode_token

router = APIRouter()


async def _event_stream(job_id: str):
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"jobs.{job_id}"
    await pubsub.subscribe(channel)
    try:
        # tiny hello so client knows we're connected
        yield f"event: hello\ndata: {{\"job_id\":\"{job_id}\"}}\n\n"
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
            if msg is None:
                yield ": keep-alive\n\n"
                continue
            data = msg["data"] if isinstance(msg["data"], str) else json.dumps(msg["data"])
            yield f"data: {data}\n\n"
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await r.close()


@router.get("/jobs/{job_id}")
async def job_stream(job_id: uuid.UUID, token: str = Query(...)):
    # EventSource can't send Authorization headers — JWT comes via query string
    try:
        decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")
    return StreamingResponse(_event_stream(str(job_id)), media_type="text/event-stream")

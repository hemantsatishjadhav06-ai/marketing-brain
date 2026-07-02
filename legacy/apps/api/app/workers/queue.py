"""RQ queue factory + enqueue helper."""
from __future__ import annotations

from functools import lru_cache

import redis
from rq import Queue

from app.core.config import settings


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


@lru_cache(maxsize=1)
def get_queue() -> Queue:
    return Queue("default", connection=_redis(), default_timeout=60 * 30)


def enqueue_job(job_id: str) -> None:
    """Enqueue a Job (uuid as str) for the worker to pick up."""
    from app.workers.job_handlers import run_job  # local import to avoid cycle
    q = get_queue()
    q.enqueue(run_job, job_id, job_id=job_id, retry=None)

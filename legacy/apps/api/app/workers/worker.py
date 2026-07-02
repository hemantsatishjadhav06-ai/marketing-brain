"""RQ Worker entrypoint."""
from __future__ import annotations

import logging

from rq import Worker

from app.core.config import settings
from app.workers.queue import _redis, get_queue


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    q = get_queue()
    w = Worker([q], connection=_redis())
    w.work(with_scheduler=True)


if __name__ == "__main__":
    main()

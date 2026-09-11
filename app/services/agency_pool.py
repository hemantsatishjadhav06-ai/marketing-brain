"""Bounded, fair background worker pool for portfolio-scale work.

Twenty clients on one Railway worker cannot each spawn their own thread the
way `autopilot` does: image generation and LLM calls would fan out to 20+
concurrent HTTP calls and trip provider rate limits, and one noisy client
could starve the rest. This pool gives the agency:

  * a hard ceiling on concurrent jobs      (AGENCY_MAX_WORKERS, default 3)
  * at most ONE active job per brand       (a second submit for a running brand queues)
  * round-robin fairness across brands     (brand A's 5 queued jobs never block brand B)
  * durable job records in the `jobs` table so progress survives redeploys
  * BG_SYNC=1 runs every job inline        (deterministic tests, no threads)

Jobs are plain callables; the pool passes a `log(msg)` function so the job can
stream progress into its own record.
"""
from __future__ import annotations

import collections
import os
import threading
import time
import traceback

from ..core import database as db

JOB_KIND = "agency_job"


def _sync() -> bool:
    return os.environ.get("BG_SYNC", "").strip().lower() in {"1", "true", "yes", "on"}


def max_workers() -> int:
    try:
        return max(1, int(os.environ.get("AGENCY_MAX_WORKERS", "3")))
    except ValueError:
        return 3


class BrandPool:
    def __init__(self):
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._queues: dict[str, collections.deque] = {}   # brand_id -> deque(job dicts)
        self._ring: collections.deque = collections.deque()  # brand ids, round-robin order
        self._active: set[str] = set()                     # brands with a running job
        self._jobs: dict[str, dict] = {}                   # job_id -> job (in-process cache)
        self._workers: list[threading.Thread] = []
        self._running = 0

    # ---------- persistence ----------
    def _persist(self, j):
        try:
            db.save_job(JOB_KIND, j["id"], j["state"], j.get("log", []),
                        {k: v for k, v in j.items() if k not in ("state", "log", "fn", "args")})
        except Exception:
            pass

    def _log(self, j, msg):
        j.setdefault("log", []).append(f"{time.strftime('%H:%M:%S')} {msg}")
        self._persist(j)

    # ---------- submit ----------
    def submit(self, brand_id: str, kind: str, fn, *args, meta: dict | None = None) -> dict:
        """Queue `fn(log, *args)` for `brand_id`. Returns the job record."""
        j = {"id": db.new_id(), "brand_id": brand_id, "kind": kind, "state": "queued",
             "log": [], "submitted": time.time(), "started": None, "finished": None,
             "result": None, "error": None, "fn": fn, "args": args}
        if meta:
            j.update({k: v for k, v in meta.items() if k not in j})
        if _sync():
            self._jobs[j["id"]] = j
            self._persist(j)
            self._run(j)
            return self.public(j)
        with self._cv:
            self._jobs[j["id"]] = j
            q = self._queues.setdefault(brand_id, collections.deque())
            q.append(j)
            if brand_id not in self._ring:
                self._ring.append(brand_id)
            self._persist(j)
            self._ensure_workers()
            self._cv.notify()
        return self.public(j)

    # ---------- workers ----------
    def _ensure_workers(self):
        want = max_workers()
        alive = [t for t in self._workers if t.is_alive()]
        self._workers = alive
        for n in range(len(alive), want):
            t = threading.Thread(target=self._worker, name=f"agency-pool-{n}", daemon=True)
            t.start()
            self._workers.append(t)

    def _next(self):
        """Pick the next job round-robin over brands that are not already active."""
        for _ in range(len(self._ring)):
            bid = self._ring[0]
            self._ring.rotate(-1)
            if bid in self._active:
                continue
            q = self._queues.get(bid)
            if q:
                j = q.popleft()
                self._active.add(bid)
                if not q:
                    self._queues.pop(bid, None)
                    try:
                        self._ring.remove(bid)
                    except ValueError:
                        pass
                return j
        return None

    def _worker(self):
        while True:
            with self._cv:
                j = self._next()
                while j is None:
                    self._cv.wait(timeout=5)
                    j = self._next()
                self._running += 1
            try:
                self._run(j)
            finally:
                with self._cv:
                    self._running -= 1
                    self._active.discard(j["brand_id"])
                    self._cv.notify_all()

    def _run(self, j):
        j["state"] = "running"
        j["started"] = time.time()
        self._log(j, f"started {j['kind']}")
        try:
            j["result"] = j["fn"](lambda m: self._log(j, m), *j["args"])
            j["state"] = "done"
            self._log(j, "done")
        except Exception as e:
            j["error"] = str(e)[:500]
            j["trace"] = traceback.format_exc()[-1500:]
            j["state"] = "failed"
            self._log(j, f"failed: {e}")
        j["finished"] = time.time()
        self._persist(j)

    # ---------- inspection ----------
    @staticmethod
    def public(j):
        return {k: v for k, v in j.items() if k not in ("fn", "args", "trace")}

    def get(self, job_id):
        j = self._jobs.get(job_id)
        if j:
            return self.public(j)
        row = db.get_job(JOB_KIND, job_id)
        if row:
            row.setdefault("id", job_id)
        return row

    def jobs_for(self, brand_ids=None, limit=200):
        """Recent jobs, cache first, then durable rows; filtered to visible brands."""
        out = {}
        try:
            for k, v in db.list_jobs(JOB_KIND).items():
                v.setdefault("id", k)
                out[k] = v
        except Exception:
            pass
        for k, j in self._jobs.items():
            out[k] = self.public(j)
        rows = list(out.values())
        if brand_ids is not None:
            allowed = set(brand_ids)
            rows = [r for r in rows if r.get("brand_id") in allowed]
        rows.sort(key=lambda r: -(r.get("submitted") or r.get("updated_at") or 0))
        return rows[:limit]

    def status(self):
        with self._lock:
            queued = sum(len(q) for q in self._queues.values())
            return {"max_workers": max_workers(), "running": self._running, "queued": queued,
                    "active_brands": sorted(self._active),
                    "workers_alive": sum(t.is_alive() for t in self._workers), "sync": _sync()}

    def wait_idle(self, timeout=30.0) -> bool:
        """Test helper: block until nothing is queued or running."""
        end = time.time() + timeout
        with self._cv:
            while (self._running or self._queues) and time.time() < end:
                self._cv.wait(timeout=0.2)
            return not (self._running or self._queues)


POOL = BrandPool()

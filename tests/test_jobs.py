"""Durable background-job state: reel/autopilot job state is mirrored to the
`jobs` table so it survives a process restart (Railway redeploys on every push)
and is readable after the in-process cache is gone."""
from __future__ import annotations

import os
import tempfile

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "jobs_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())

from app.core import database as db  # noqa: E402
from app.routes import _shared  # noqa: E402


@pytest.fixture(autouse=True)
def _init():
    db.init_db()


def test_save_and_get_job_roundtrip():
    db.save_job("reel", "job-1", "running", ["10:00 started"], {"creative_id": None, "brand_id": "b1"})
    j = db.get_job("reel", "job-1")
    assert j["state"] == "running" and j["log"] == ["10:00 started"] and j["brand_id"] == "b1"


def test_reel_state_survives_cache_loss():
    _shared._reel_set("job-2", state="running", creative_id=None, brand_id="b2")
    _shared._rs_log("job-2", "painting scene 1")
    _shared._reel_set("job-2", state="done", creative_id="cre9")
    _shared.REEL_JOBS.pop("job-2", None)          # simulate a redeploy wiping the cache
    j = _shared._reel_get("job-2")                 # falls back to the DB
    assert j is not None and j["state"] == "done" and j["creative_id"] == "cre9"
    assert any("painting scene 1" in line for line in j["log"])


def test_autopilot_state_persists_and_lists():
    _shared._ap_set("brand-A", state="running", log=[])
    _shared._ap_log("brand-A", "engaged")
    _shared._ap_set("brand-A", state="done")
    _shared.AUTOPILOT.pop("brand-A", None)
    assert (_shared._ap_get("brand-A") or {}).get("state") == "done"
    assert "brand-A" in _shared._ap_all()


def test_interrupt_stale_jobs():
    db.save_job("reel", "stale", "running", [], {})
    # backdate it so it counts as stale
    import time
    with db._lock, db._conn() as c:
        c.execute("UPDATE jobs SET updated_at=? WHERE kind='reel' AND job_key='stale'", (time.time() - 99999,))
    db.interrupt_stale_jobs()
    assert db.get_job("reel", "stale")["state"] == "interrupted"

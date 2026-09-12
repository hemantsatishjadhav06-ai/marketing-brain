"""DB INTEGRITY + JOBS — what survives a brand delete, and job-state durability
(extends tests/test_jobs.py; does not repeat its cases)."""
from __future__ import annotations

import os
import time

import pytest

from app.core import database as db
from app.routes import _shared
from app.services import memory as mem, workspace as ws

from .conftest import client, hdr, seed_creative, seed_idea, signup_org, u


def _seed_everything(o):
    bid = o["brand_id"]
    iid = seed_idea(bid)
    cid = seed_creative(bid)
    db.insert_doc("calendar_items", bid, {"t": 1}, idea_id=iid, channel="instagram", date="2030-01-01", time="10:00")
    db.insert_doc("publish_queue", bid, {}, creative_id=cid, channel="instagram", mode="simulated", status="published")
    db.insert_doc("metrics", bid, {"views": 1}, channel="instagram", post_ref="p")
    db.set_connector(bid, "instagram", {"access_token": "t"})
    db.insert_doc("competitors", bid, {}, name="c", url="https://c.invalid")
    mem.remember(bid, "rule", kind="rule")
    rid = mem.start_run(bid, "blueprint", creative_id=cid); mem.finish_run(rid, "done")
    from app.services import inbox
    inbox.record_inbound(bid, "whatsapp", "+1", "hi")
    db.insert_doc("invites", bid, {}, email="i@i.test", role="client", token="tok" + u(), status="pending")
    db.save_job("autopilot", bid, "done", [], {})
    db.bump_gen_usage(bid, "2030-01-01")
    ws.write_text(o["brand"]["slug"], "instagram/creatives/x.md", "x")
    return bid


def _count(table, bid, col="brand_id"):
    with db._conn() as c:
        return c.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {col}=?", (bid,)).fetchone()["n"]


CASCADED = ["ideas", "calendar_items", "creatives", "publish_queue", "metrics", "connector_settings"]
ORPHANED = ["competitors", "brand_memory", "agent_runs", "conversations", "messages", "invites", "users", "gen_usage"]


@pytest.mark.parametrize("table", CASCADED)
def DB_delete_brand_cascades(admin, table):
    o = signup_org("Cascade Co"); bid = _seed_everything(o)
    assert _count(table, bid) >= 1
    assert client.delete(f"/api/brands/{bid}", headers=hdr(admin["token"])).status_code == 200
    assert _count(table, bid) == 0


@pytest.mark.defect
@pytest.mark.parametrize("table", ORPHANED)
def DB_delete_brand_leaves_no_orphans(admin, table):
    """DEFECT (app/core/database.py delete_brand): only 6 tables are cleaned; the rest
    keep rows pointing at a brand that no longer exists."""
    o = signup_org("Orphan Co"); bid = _seed_everything(o)
    assert _count(table, bid) >= 1, f"seed failed for {table}"
    assert client.delete(f"/api/brands/{bid}", headers=hdr(admin["token"])).status_code == 200
    assert _count(table, bid) == 0, f"{table}: {_count(table, bid)} row(s) orphaned after brand delete"


@pytest.mark.defect
def DB_delete_brand_cleans_jobs_row(admin):
    o = signup_org("Jobs Co"); bid = _seed_everything(o)
    client.delete(f"/api/brands/{bid}", headers=hdr(admin["token"]))
    assert db.get_job("autopilot", bid) is None, "jobs row survives brand delete"


@pytest.mark.defect
def DB_deleted_brand_users_cannot_login(admin):
    """DEFECT: the deleted company's owner keeps a working login + token (brand_id dangles)
    and the email can never be re-used for a new signup."""
    o = signup_org("Ghost Co"); bid = o["brand_id"]
    client.delete(f"/api/brands/{bid}", headers=hdr(admin["token"]))
    r = client.post("/api/auth/login", json={"email": o["email"], "password": o["password"]}, headers={"X-Forwarded-For": "203.0.113.200"})
    assert r.status_code == 401, f"owner of a deleted company still logs in: {r.status_code} {r.text[:80]}"


@pytest.mark.defect
def DB_delete_brand_removes_workspace_files(admin):
    o = signup_org("Files Co"); bid = _seed_everything(o)
    path = ws.brand_dir(o["brand"]["slug"])
    assert os.path.isdir(path)
    client.delete(f"/api/brands/{bid}", headers=hdr(admin["token"]))
    assert not os.path.exists(path), "tenant workspace files remain on disk after delete"


def DB_delete_unknown_brand_404(admin):
    assert client.delete("/api/brands/nope-" + u(), headers=hdr(admin["token"])).status_code == 404


def DB_delete_brand_does_not_touch_other_brand(admin):
    a = signup_org("Keep Co"); b = signup_org("Drop Co")
    _seed_everything(a); _seed_everything(b)
    client.delete(f"/api/brands/{b['brand_id']}", headers=hdr(admin["token"]))
    for t in CASCADED + ["competitors", "brand_memory"]:
        assert _count(t, a["brand_id"]) >= 1, t


def DB_password_reset_rows_have_no_brand_scope():
    """Fact: password_resets rows are written with brand_id='' so they can never be
    cascaded per company; noted with the orphan defect."""
    from app.services import onboarding
    o = signup_org("Reset Co")
    onboarding.request_reset(o["email"])
    rows = [r for r in db.list_docs("password_resets", "") if (r.get("payload") or {}).get("email") == o["email"]]
    assert rows and rows[0]["brand_id"] == ""


# ------------------------------------------------------------ jobs (extends tests/test_jobs.py)

def JOBS_get_unknown_job_is_none():
    assert db.get_job("reel", "never-" + u()) is None
    assert _shared._reel_get("never-" + u()) is None


def JOBS_save_job_upserts_in_place():
    k = "up-" + u()
    db.save_job("reel", k, "running", ["a"], {"creative_id": None})
    db.save_job("reel", k, "done", ["a", "b"], {"creative_id": "c1"})
    j = db.get_job("reel", k)
    assert j["state"] == "done" and j["log"] == ["a", "b"] and j["creative_id"] == "c1"
    assert len([x for x in db.list_jobs("reel") if x == k]) == 1


def JOBS_kinds_are_isolated():
    k = "same-key-" + u()
    db.save_job("reel", k, "done", [], {})
    db.save_job("autopilot", k, "failed", [], {})
    assert db.get_job("reel", k)["state"] == "done" and db.get_job("autopilot", k)["state"] == "failed"


def JOBS_interrupt_stale_leaves_fresh_running_jobs_alone():
    fresh, stale = "fresh-" + u(), "stale-" + u()
    db.save_job("reel", fresh, "running", [], {})
    db.save_job("reel", stale, "running", [], {})
    with db._lock, db._conn() as c:
        c.execute("UPDATE jobs SET updated_at=? WHERE job_key=?", (time.time() - 7200, stale))
    db.interrupt_stale_jobs()
    assert db.get_job("reel", fresh)["state"] == "running"
    assert db.get_job("reel", stale)["state"] == "interrupted"


def JOBS_interrupt_stale_ignores_finished_jobs():
    k = "done-old-" + u()
    db.save_job("reel", k, "done", [], {})
    with db._lock, db._conn() as c:
        c.execute("UPDATE jobs SET updated_at=? WHERE job_key=?", (time.time() - 7200, k))
    db.interrupt_stale_jobs()
    assert db.get_job("reel", k)["state"] == "done"


def JOBS_reel_state_readable_via_api_after_cache_wipe():
    o = signup_org("Reel Co")
    k = "api-" + u()
    _shared._reel_set(k, state="done", creative_id="c9", brand_id=o["brand_id"])
    _shared.REEL_JOBS.pop(k, None)
    r = client.get(f"/api/reel-studio/jobs/{k}", headers=hdr(o["token"]))
    assert r.status_code == 200 and r.json()["state"] == "done" and r.json()["creative_id"] == "c9"


def JOBS_interrupted_autopilot_can_be_restarted(monkeypatch):
    from app.routes import autopilot as ap
    o = signup_org("Restart Co")
    db.save_job("autopilot", o["brand_id"], "interrupted", [], {})
    _shared.AUTOPILOT.pop(o["brand_id"], None)
    monkeypatch.setattr(ap, "_run_autopilot", lambda bid, cfg: None)
    assert client.post(f"/api/brands/{o['brand_id']}/autopilot", json={}, headers=hdr(o["token"])).status_code == 200

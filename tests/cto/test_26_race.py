"""26 APPROVAL RACE — concurrent approvals on one creative must leave one consistent state."""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from app.core import database as db
from app.main import app

from .conftest import hdr, seed_creative, signup_org


@pytest.fixture
def org():
    return signup_org("Acme Widgets")


def _fire(n, fn):
    errors, results = [], []

    def run(i):
        try:
            results.append(fn(i))
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))

    ts = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    [t.start() for t in ts]
    [t.join(15) for t in ts]
    return results, errors


def RACE_two_concurrent_approvals_consistent(org):
    bid, cid = org["brand_id"], seed_creative(org["brand_id"])
    states = ["approved", "changes_requested"]

    def fn(i):
        c = TestClient(app)
        return c.post(f"/api/brands/{bid}/creatives/{cid}/approval",
                      json={"state": states[i], "comment": f"c{i}"}, headers=hdr(org["token"])).status_code

    results, errors = _fire(2, fn)
    assert errors == [] and results == [200, 200]
    doc = db.get_doc("creatives", cid)
    ap = doc["payload"]["approval"]
    assert ap["state"] in states and ap["comment"] in ("c0", "c1")
    assert doc["payload"]["title"] == "Seeded creative", "payload lost under concurrent write"


def RACE_ten_concurrent_approvals_no_errors(org):
    bid, cid = org["brand_id"], seed_creative(org["brand_id"])

    def fn(i):
        c = TestClient(app)
        return c.post(f"/api/brands/{bid}/creatives/{cid}/approval", json={"state": "approved", "comment": str(i)},
                      headers=hdr(org["token"])).status_code

    results, errors = _fire(10, fn)
    assert errors == [] and results == [200] * 10
    assert db.get_doc("creatives", cid)["payload"]["approval"]["state"] == "approved"


@pytest.mark.defect
def RACE_concurrent_payload_writers_do_not_lose_each_others_fields(org, fake_ai):
    """DEFECT (app/routes/studio.py set_approval + algo_audit; app/routes/brain.py _patch):
    every creative mutation is read-modify-write of the whole JSON payload with no
    row lock or version — a concurrent approval and audit overwrite each other."""
    bid, cid = org["brand_id"], seed_creative(org["brand_id"])
    barrier = threading.Barrier(2)

    def approve(_):
        c = TestClient(app); barrier.wait(5)
        return c.post(f"/api/brands/{bid}/creatives/{cid}/approval", json={"state": "approved"}, headers=hdr(org["token"])).status_code

    def audit(_):
        c = TestClient(app); barrier.wait(5)
        return c.post(f"/api/brands/{bid}/creatives/{cid}/algo-audit", headers=hdr(org["token"])).status_code

    lost = 0
    for _ in range(8):
        db.update_doc("creatives", cid, payload={"title": "Seeded creative", "format": "post"})
        barrier.reset()
        ta, tb = threading.Thread(target=approve, args=(0,)), threading.Thread(target=audit, args=(0,))
        ta.start(); tb.start(); ta.join(10); tb.join(10)
        p = db.get_doc("creatives", cid)["payload"]
        if not (p.get("approval") and p.get("algo_audit") is not None):
            lost += 1
    assert lost == 0, f"lost-update observed in {lost}/8 rounds (approval or algo_audit field vanished)"


@pytest.mark.defect
def RACE_concurrent_live_publish_single_platform_post(org, monkeypatch):
    """DEFECT (app/routes/publishing.py publish): the 'already published live' check reads
    publish_queue BEFORE the platform call and the row is inserted AFTER it, so two
    simultaneous clicks both pass the check and both post. A realistic 200 ms platform
    round-trip makes the window deterministic."""
    from app.services import connectors
    calls = []
    lock = threading.Lock()

    def fake_publish(*a, **k):
        with lock:
            calls.append(a)
        import time; time.sleep(0.2)   # a real Graph API call is never instantaneous
        return {"platform_response": {"id": "x"}}

    monkeypatch.setattr(connectors, "publish", fake_publish)
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})

    def fn(i):
        return TestClient(app).post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": "live"},
                                    headers=hdr(org["token"])).status_code

    results, errors = _fire(2, fn)
    assert errors == []
    assert len(calls) == 1, f"platform received {len(calls)} posts for one creative"

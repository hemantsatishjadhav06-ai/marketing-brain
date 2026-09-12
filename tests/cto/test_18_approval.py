"""18/25 APPROVAL ENFORCEMENT + IDEMPOTENCY — live publishing is a security control."""
from __future__ import annotations

import threading
import time

import pytest

from app.core import database as db
from app.routes import _shared, autopilot as autopilot_routes
from app.services import connectors

from .conftest import client, hdr, seed_creative, signup_org


@pytest.fixture
def org():
    return signup_org("Acme Widgets")  # name deliberately avoids the built-in logo table


@pytest.fixture
def no_publish(monkeypatch):
    """Any live connector call is a test failure unless the test explicitly allows it."""
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("connectors.publish was called")

    monkeypatch.setattr(connectors, "publish", boom)
    return calls


def _rows(bid):
    return db.list_docs("publish_queue", bid)


# ------------------------------------------------------------ live requires approval

def APPROVAL_unapproved_publish_blocked(org, no_publish):
    cid = seed_creative(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/publish", json={"creative_id": cid, "mode": "live"},
                    headers=hdr(org["token"]))
    assert r.status_code == 400 and "approv" in r.text.lower()
    assert _rows(org["brand_id"]) == [] and no_publish == []


def APPROVAL_changes_requested_publish_blocked(org, no_publish):
    cid = seed_creative(org["brand_id"])
    client.post(f"/api/brands/{org['brand_id']}/creatives/{cid}/approval",
                json={"state": "changes_requested", "comment": "no"}, headers=hdr(org["token"]))
    r = client.post(f"/api/brands/{org['brand_id']}/publish", json={"creative_id": cid, "mode": "live"},
                    headers=hdr(org["token"]))
    assert r.status_code == 400 and _rows(org["brand_id"]) == [] and no_publish == []


def APPROVAL_approved_live_without_credentials_400(org, no_publish):
    cid = seed_creative(org["brand_id"], approved=True)
    r = client.post(f"/api/brands/{org['brand_id']}/publish", json={"creative_id": cid, "mode": "live"},
                    headers=hdr(org["token"]))
    assert r.status_code == 400 and "credentials" in r.text.lower()
    assert _rows(org["brand_id"]) == [], "a failed live publish must not leave a 'published' row"
    assert no_publish == []


def APPROVAL_approved_live_with_credentials_calls_connector_once(org, monkeypatch):
    calls = []
    monkeypatch.setattr(connectors, "publish", lambda *a, **k: (calls.append(a) or {"platform_response": {"id": "p1"}}))
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})
    r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": "live"}, headers=hdr(org["token"]))
    assert r.status_code == 200 and r.json()["status"] == "published" and r.json()["mode"] == "live"
    assert len(calls) == 1 and calls[0][0] == "instagram"
    assert calls[0][1] == {"access_token": "t", "ig_user_id": "1"}


def APPROVAL_live_connector_failure_recorded_not_hidden(org, monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("platform said no")
    monkeypatch.setattr(connectors, "publish", fail)
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})
    r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": "live"}, headers=hdr(org["token"]))
    assert r.status_code == 200 and r.json()["status"] == "failed"
    assert "platform said no" in r.json()["payload"]["error"]


def APPROVAL_approval_revoked_after_approve_blocks_live(org, no_publish):
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})
    client.post(f"/api/brands/{bid}/creatives/{cid}/approval", json={"state": "changes_requested"}, headers=hdr(org["token"]))
    r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": "live"}, headers=hdr(org["token"]))
    assert r.status_code == 400 and no_publish == []


def APPROVAL_only_two_states_accepted(org):
    cid = seed_creative(org["brand_id"])
    for bad in ("published", "approve", "APPROVED", "", "live"):
        r = client.post(f"/api/brands/{org['brand_id']}/creatives/{cid}/approval", json={"state": bad}, headers=hdr(org["token"]))
        assert r.status_code == 400, bad
    assert db.get_doc("creatives", cid)["payload"].get("approval") is None


# ------------------------------------------------------------ bypass attempts

@pytest.mark.parametrize("mode", ["LIVE", "Live", " live", "live ", "production", "real"])
def APPROVAL_mode_variants_never_hit_connector(org, no_publish, mode):
    bid = org["brand_id"]
    cid = seed_creative(bid)  # unapproved
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})
    r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": mode}, headers=hdr(org["token"]))
    assert no_publish == [], f"mode={mode!r} reached the live connector"
    assert r.status_code in (200, 400, 422)


@pytest.mark.defect
def APPROVAL_unknown_mode_rejected_not_logged_as_published(org, no_publish):
    """DEFECT (app/routes/publishing.py publish): any mode string other than exactly
    'live' is treated as a dry run but stored verbatim with status='published'. The
    publish log then shows mode='LIVE' status='published' for a post that never left
    the box — and for an UNAPPROVED creative."""
    bid = org["brand_id"]
    cid = seed_creative(bid)
    r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": "LIVE"}, headers=hdr(org["token"]))
    assert r.status_code == 422 or r.status_code == 400, f"mode='LIVE' accepted: {r.status_code} {r.json()}"


def APPROVAL_mode_switch_does_not_bypass_live_gate(org, no_publish):
    bid = org["brand_id"]
    cid = seed_creative(bid)
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})
    for mode in ("auto", "manual"):
        assert client.post(f"/api/brands/{bid}/mode", json={"mode": mode}, headers=hdr(org["token"])).status_code == 200
        r = client.post(f"/api/brands/{bid}/publish", json={"creative_id": cid, "mode": "live"}, headers=hdr(org["token"]))
        assert r.status_code == 400 and no_publish == []


def APPROVAL_direct_connector_endpoint_not_exposed():
    paths = client.get("/openapi.json").json()["paths"]
    assert not any("connectors/publish" in p or p.endswith("/live") for p in paths), paths.keys()


def APPROVAL_proceed_refused_until_approved(org, fake_ai):
    bid = org["brand_id"]
    cid = seed_creative(bid, blueprint={"static_image_prompt": "p"})
    r = client.post(f"/api/brands/{bid}/creatives/{cid}/proceed", headers=hdr(org["token"]))
    assert r.status_code == 400 and "approve" in r.text.lower()
    time.sleep(0.2)
    assert fake_ai.fal_calls == [], "proceed spent on fal without approval"


def APPROVAL_proceed_refused_without_blueprint(org, fake_ai):
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    r = client.post(f"/api/brands/{bid}/creatives/{cid}/proceed", headers=hdr(org["token"]))
    assert r.status_code == 400 and fake_ai.fal_calls == []


def APPROVAL_proceed_runs_once_approved(org, fake_ai):
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True, blueprint={"static_image_prompt": "p"})
    r = client.post(f"/api/brands/{bid}/creatives/{cid}/proceed", headers=hdr(org["token"]))
    assert r.status_code == 200
    for _ in range(50):
        if (db.get_doc("creatives", cid)["payload"].get("gen_status") or "").startswith("done"):
            break
        time.sleep(0.05)
    assert fake_ai.fal_calls and fake_ai.fal_calls[0][0] == "image"


def APPROVAL_revise_resets_approval(org, fake_ai):
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True, blueprint={"static_image_prompt": "p"})
    r = client.post(f"/api/brands/{bid}/creatives/{cid}/revise", json={"instruction": "bigger logo"}, headers=hdr(org["token"]))
    assert r.status_code == 200
    for _ in range(50):
        p = db.get_doc("creatives", cid)["payload"]
        if (p.get("gen_status") or "").startswith("done") or "failed" in (p.get("gen_status") or ""):
            break
        time.sleep(0.05)
    assert (p.get("gen_status") or "").startswith("done"), p.get("gen_status")
    assert p.get("approval") is None, "a revised asset must need a fresh decision"


# ------------------------------------------------------------ idempotency

@pytest.mark.defect
def PUBLISH_duplicate_request_single_publish(org, no_publish):
    """DEFECT (app/routes/publishing.py publish): no idempotency key / no check for an
    existing published row — the same creative published twice yields TWO rows."""
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    body = {"creative_id": cid, "mode": "simulated"}
    assert client.post(f"/api/brands/{bid}/publish", json=body, headers=hdr(org["token"])).status_code == 200
    client.post(f"/api/brands/{bid}/publish", json=body, headers=hdr(org["token"]))
    # A dry run is logged as 'simulated' (never 'published' — see STATE_simulated_publish_*);
    # idempotency means ONE row for the creative, whatever its status.
    rows = [r for r in _rows(bid) if r["creative_id"] == cid]
    assert len(rows) == 1, f"ONE publish row expected, got {len(rows)}"
    assert rows[0]["status"] == "simulated"


@pytest.mark.defect
def PUBLISH_duplicate_live_request_single_connector_call(org, monkeypatch):
    """DEFECT: a double-click on 'publish live' posts to the platform twice."""
    calls = []
    monkeypatch.setattr(connectors, "publish", lambda *a, **k: (calls.append(a) or {"platform_response": {"id": "p"}}))
    bid = org["brand_id"]
    cid = seed_creative(bid, approved=True)
    db.set_connector(bid, "instagram", {"access_token": "t", "ig_user_id": "1"})
    body = {"creative_id": cid, "mode": "live"}
    client.post(f"/api/brands/{bid}/publish", json=body, headers=hdr(org["token"]))
    client.post(f"/api/brands/{bid}/publish", json=body, headers=hdr(org["token"]))
    assert len(calls) == 1, f"platform received {len(calls)} posts for one creative"


@pytest.mark.defect
def IDEMP_reel_studio_duplicate_request_single_job(org, monkeypatch):
    """DEFECT (app/routes/brands.py reel_studio): every call spawns a new paid job and a
    new creative — no de-duplication per creative/prompt."""
    monkeypatch.setattr(_shared, "_run_reel_studio", lambda *a, **k: None)
    import app.routes.brands as brands_routes
    monkeypatch.setattr(brands_routes, "_run_reel_studio", lambda *a, **k: None)
    bid = org["brand_id"]
    body = {"prompt": "A 20-second reel about our spring launch, cinematic style"}
    a = client.post(f"/api/brands/{bid}/reel-studio", json=body, headers=hdr(org["token"]))
    b = client.post(f"/api/brands/{bid}/reel-studio", json=body, headers=hdr(org["token"]))
    assert a.status_code == 200
    assert b.status_code in (400, 409) or b.json().get("job_id") == a.json()["job_id"], \
        f"second request started a second job: {b.json()}"


@pytest.mark.defect
def IDEMP_reel_studio_from_existing_creative_does_not_crash(org, monkeypatch, fake_ai):
    """DEFECT (app/routes/brands.py reel_studio): the Script-to-Video path calls
    json.dumps but `json` is never imported (_shared only exports io/os/time/threading)
    -> NameError -> HTTP 500 on every request with a creative_id."""
    bid = org["brand_id"]
    cid = seed_creative(bid, script={"shots": []}, format="reel")
    from .conftest import client_no_raise
    r = client_no_raise.post(f"/api/brands/{bid}/reel-studio", json={"creative_id": cid}, headers=hdr(org["token"]))
    assert r.status_code == 200, f"reel-studio with creative_id -> {r.status_code}"


def IDEMP_autopilot_second_call_400_while_running(org, monkeypatch):
    release = threading.Event()

    def slow_runner(bid, cfg):
        _shared._ap_set(bid, state="running", log=[])
        release.wait(5)
        _shared._ap_set(bid, state="done")

    monkeypatch.setattr(autopilot_routes, "_run_autopilot", slow_runner)
    bid = org["brand_id"]
    try:
        first = client.post(f"/api/brands/{bid}/autopilot", json={"ideas_per_channel": 1}, headers=hdr(org["token"]))
        assert first.status_code == 200
        time.sleep(0.2)
        second = client.post(f"/api/brands/{bid}/autopilot", json={"ideas_per_channel": 1}, headers=hdr(org["token"]))
        assert second.status_code == 400 and "already running" in second.text
    finally:
        release.set()
        time.sleep(0.1)


@pytest.mark.defect
def RACE_autopilot_concurrent_starts_single_run(org, monkeypatch):
    """DEFECT (app/routes/autopilot.py autopilot): the 'already running' check reads state
    that the *worker thread* sets later; two requests in the thread-start window both
    pass and two autopilot runs (double spend) start."""
    from fastapi.testclient import TestClient
    from app.main import app
    starts = []
    release = threading.Event()

    def runner(bid, cfg):
        starts.append(time.time())
        time.sleep(0.2)                       # the real runner does DB work before/while the flag lands
        _shared._ap_set(bid, state="running", log=[])
        release.wait(5)
        _shared._ap_set(bid, state="done")

    monkeypatch.setattr(autopilot_routes, "_run_autopilot", runner)
    bid = org["brand_id"]
    codes = []

    def fire():
        c = TestClient(app)
        codes.append(c.post(f"/api/brands/{bid}/autopilot", json={"ideas_per_channel": 1}, headers=hdr(org["token"])).status_code)

    ts = [threading.Thread(target=fire) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    release.set(); time.sleep(0.3)
    assert sorted(codes) == [200, 400] and len(starts) == 1, f"codes={codes} runs started={len(starts)}"

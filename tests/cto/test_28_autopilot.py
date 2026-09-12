"""28 AUTOPILOT SAFETY — autopilot must never publish live or spend without the guards."""
from __future__ import annotations

import time

import pytest

from app.ai import engine
from app.core import database as db
from app.routes import _shared, autopilot as autopilot_routes
from app.schemas import AutopilotIn
from app.services import connectors

from .conftest import REAL_CHAT, REAL_GENERATE_IMAGE, REAL_JSON_CHAT, client, hdr, signup_org


@pytest.fixture
def ready_org():
    o = signup_org("Acme Widgets")
    db.update_brand(o["brand_id"], setup={"channels": ["instagram"], "mode": "auto"}, status="ready")
    o["brand"] = db.get_brand(o["brand_id"])
    return o


@pytest.fixture
def no_publish(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("live publish from autopilot")

    monkeypatch.setattr(connectors, "publish", boom)
    return calls


def AUTOPILOT_never_publishes_or_approves(ready_org, fake_ai, no_publish):
    bid = ready_org["brand_id"]
    _shared._run_autopilot(bid, AutopilotIn(ideas_per_channel=2, creatives_per_channel=2, generate_images=True))
    j = _shared._ap_get(bid)
    assert j["state"] == "done", j["log"]
    assert no_publish == [] and fake_ai.fal_calls == []
    assert db.list_docs("publish_queue", bid) == []
    creatives = db.list_docs("creatives", bid)
    assert creatives and all(c["payload"].get("approval") is None for c in creatives), "autopilot self-approved"
    assert fake_ai.image_calls, "images requested but none generated (mock)"


def AUTOPILOT_default_config_does_not_generate_images(ready_org, fake_ai):
    bid = ready_org["brand_id"]
    _shared._run_autopilot(bid, AutopilotIn())
    assert fake_ai.image_calls == [] and fake_ai.voice_calls == []


@pytest.mark.defect
def AUTOPILOT_image_spend_counts_against_daily_budget(ready_org, fake_ai):
    """DEFECT (app/routes/_shared.py _run_autopilot -> _generate_image / _generate_ideas):
    the route-level _gen_guard (kill-switch + GEN_DAILY_CAP) is skipped, so autopilot
    spend is never counted or capped."""
    bid = ready_org["brand_id"]
    _shared._run_autopilot(bid, AutopilotIn(ideas_per_channel=1, creatives_per_channel=1, generate_images=True))
    day = time.strftime("%Y-%m-%d", time.gmtime())
    assert db.gen_usage_count(bid, day) >= len(fake_ai.image_calls) >= 1, \
        f"{len(fake_ai.image_calls)} paid image call(s), budget counter={db.gen_usage_count(bid, day)}"


@pytest.mark.defect
def AUTOPILOT_respects_daily_cap(ready_org, fake_ai, monkeypatch):
    monkeypatch.setenv("GEN_DAILY_CAP", "1")
    bid = ready_org["brand_id"]
    _shared._run_autopilot(bid, AutopilotIn(ideas_per_channel=3, creatives_per_channel=3, generate_images=True))
    assert len(fake_ai.image_calls) <= 1, f"cap=1 but autopilot generated {len(fake_ai.image_calls)} images"


def AUTOPILOT_kill_switch_stops_all_generation(ready_org, fake_ai, monkeypatch):
    """Uses the REAL _chat/_json_chat/generate_image: their first statement is the
    kill-switch check, which raises before any I/O."""
    monkeypatch.setenv("GENERATION_DISABLED", "true")
    monkeypatch.setattr(engine, "_chat", REAL_CHAT)
    monkeypatch.setattr(engine, "_json_chat", REAL_JSON_CHAT)
    monkeypatch.setattr(engine, "generate_image", REAL_GENERATE_IMAGE)
    bid = ready_org["brand_id"]
    _shared._run_autopilot(bid, AutopilotIn(ideas_per_channel=1, generate_images=True))
    j = _shared._ap_get(bid)
    assert j["state"] == "failed" and "disabled" in " ".join(j["log"]).lower(), j["log"]
    assert db.list_docs("ideas", bid) == [] and db.list_docs("creatives", bid) == []


def AUTOPILOT_route_ideas_blocked_by_kill_switch(ready_org, monkeypatch):
    monkeypatch.setenv("GENERATION_DISABLED", "true")
    r = client.post(f"/api/brands/{ready_org['brand_id']}/ideas", json={"count": 1}, headers=hdr(ready_org["token"]))
    assert r.status_code == 429


def AUTOPILOT_all_only_starts_ready_brands_and_only_for_admin(admin, ready_org, monkeypatch):
    started = []
    monkeypatch.setattr(autopilot_routes, "_run_autopilot", lambda bid, cfg: started.append(bid))
    monkeypatch.setattr(autopilot_routes.time, "sleep", lambda s: None)
    not_ready = signup_org("Sleepy Co")  # status 'new'
    assert client.post("/api/autopilot/all", json={}, headers=hdr(ready_org["token"])).status_code == 403
    r = client.post("/api/autopilot/all", json={}, headers=hdr(admin["token"]))
    assert r.status_code == 200
    time.sleep(0.2)
    assert ready_org["brand_id"] in started and not_ready["brand_id"] not in started


def AUTOPILOT_client_role_can_start_autopilot_for_own_brand(ready_org, monkeypatch):
    """Observation for product review: any user of the brand (incl. 'client') can start a
    paid autopilot run. Not a spec'd defect; recorded so nobody assumes admin-only."""
    from .conftest import make_client_user
    monkeypatch.setattr(autopilot_routes, "_run_autopilot", lambda bid, cfg: None)
    cu = make_client_user(ready_org["brand_id"])
    r = client.post(f"/api/brands/{ready_org['brand_id']}/autopilot", json={}, headers=hdr(cu["token"]))
    assert r.status_code == 200


def AUTOPILOT_failure_is_recorded_not_swallowed(ready_org, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model exploded")
    monkeypatch.setattr(engine, "_json_chat", boom)
    bid = ready_org["brand_id"]
    _shared._run_autopilot(bid, AutopilotIn(ideas_per_channel=1))
    j = _shared._ap_get(bid)
    assert j["state"] == "failed" and "model exploded" in " ".join(j["log"])

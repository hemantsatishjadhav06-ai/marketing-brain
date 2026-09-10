"""20 CALENDAR / STATE MACHINE — is any lifecycle enforced on ideas, creatives, publish rows?"""
from __future__ import annotations

import pytest

from app.core import database as db

from .conftest import client, hdr, seed_creative, seed_idea, signup_org


@pytest.fixture
def org():
    return signup_org("Acme Widgets")


@pytest.mark.defect
def STATE_idea_cannot_jump_to_published(org):
    """DEFECT (app/routes/pipeline.py idea_state): no transition table — 'proposed' goes
    straight to 'published' (or any string) with one POST."""
    iid = seed_idea(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/ideas/{iid}/state", json={"state": "published"}, headers=hdr(org["token"]))
    assert r.status_code == 400, f"proposed -> published accepted: {r.status_code}"
    assert db.get_doc("ideas", iid)["state"] == "proposed"


@pytest.mark.defect
@pytest.mark.parametrize("bad", ["banana", "", "APPROVED", "approved; DROP", " approved"])
def STATE_idea_state_vocabulary_enforced(org, bad):
    iid = seed_idea(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/ideas/{iid}/state", json={"state": bad}, headers=hdr(org["token"]))
    assert r.status_code == 400, f"idea state {bad!r} accepted and stored: {db.get_doc('ideas', iid)['state']!r}"


@pytest.mark.defect
def STATE_idea_state_requires_explicit_state(org):
    """An empty body silently approves the idea (default 'approved')."""
    iid = seed_idea(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/ideas/{iid}/state", json={}, headers=hdr(org["token"]))
    assert r.status_code in (400, 422), f"empty body -> state={db.get_doc('ideas', iid)['state']!r}"


def STATE_idea_state_body_must_be_object(org):
    iid = seed_idea(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/ideas/{iid}/state", json=["approved"], headers=hdr(org["token"]))
    assert r.status_code == 422


def STATE_creative_approval_vocabulary_enforced(org):
    cid = seed_creative(org["brand_id"])
    ok = client.post(f"/api/brands/{org['brand_id']}/creatives/{cid}/approval", json={"state": "approved"}, headers=hdr(org["token"]))
    assert ok.status_code == 200 and ok.json()["payload"]["approval"]["state"] == "approved"
    bad = client.post(f"/api/brands/{org['brand_id']}/creatives/{cid}/approval", json={"state": "published"}, headers=hdr(org["token"]))
    assert bad.status_code == 400


def STATE_approval_records_actor(org):
    cid = seed_creative(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/creatives/{cid}/approval", json={"state": "approved"}, headers=hdr(org["token"]))
    ap = r.json()["payload"]["approval"]
    assert ap["by"] == org["user_id"] and ap["role"] == "owner" and ap["at"] > 0


@pytest.mark.defect
def STATE_simulated_publish_of_unapproved_creative_not_logged_as_published(org):
    """DEFECT: a dry run on an UNAPPROVED creative writes status='published' into the
    publish log — the log cannot be trusted as 'what went out'."""
    cid = seed_creative(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/publish", json={"creative_id": cid, "mode": "simulated"}, headers=hdr(org["token"]))
    assert r.status_code == 200
    assert r.json()["status"] != "published", f"simulated dry run stored as {r.json()['status']!r}"


def STATE_scheduled_simulated_publish_is_queued_not_published(org):
    cid = seed_creative(org["brand_id"])
    r = client.post(f"/api/brands/{org['brand_id']}/publish",
                    json={"creative_id": cid, "mode": "simulated", "scheduled_for": "2030-01-01T10:00"}, headers=hdr(org["token"]))
    assert r.status_code == 200 and r.json()["status"] == "queued"


def STATE_no_endpoint_advances_calendar_or_queued_rows():
    """Documents the gap: nothing moves calendar_items off 'planned' or publish_queue off
    'queued' — there is no scheduler and no transition endpoint. Asserted from OpenAPI so
    the report is factual, not a guess."""
    paths = client.get("/openapi.json").json()["paths"]
    cal_mut = [p for p, ops in paths.items() if "calendar" in p and any(m in ops for m in ("post", "put", "patch", "delete")) and "{" in p.split("calendar")[-1]]
    queue_mut = [p for p, ops in paths.items() if "publish" in p and "{" in p.split("publish")[-1]]
    assert cal_mut == [] and queue_mut == [], (cal_mut, queue_mut)

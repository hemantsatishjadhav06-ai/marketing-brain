"""Airtable content calendar — base per client, push upserts, pull applies human edits."""
from __future__ import annotations

import json
import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "atcal.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ.pop("DIRECT_ACCESS", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.core import auth, database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import airtable_calendar as at, workspace as ws  # noqa: E402

client = TestClient(app)


class FakeAirtable:
    """Records what the service sends and answers like Airtable would."""
    def __init__(self):
        self.calls = []
        self.records = {}   # table -> list of records

    def request(self, method, url, headers=None, json=None, params=None):
        self.calls.append((method, url, json, params))
        r = type("R", (), {})()
        if method == "POST" and url.endswith("/meta/bases"):
            r.status_code = 200; r.json = lambda: {"id": "appTESTBASE000001", "tables": []}; return r
        if method == "PATCH":
            table = url.rsplit("/", 1)[1]
            rows = self.records.setdefault(table, [])
            for rec in json["records"]:
                key = rec["fields"].get("MB ID")
                ex = next((x for x in rows if x["fields"].get("MB ID") == key), None)
                if ex:
                    ex["fields"].update(rec["fields"])
                else:
                    rows.append({"id": "rec" + uuid.uuid4().hex[:14], "fields": dict(rec["fields"])})
            r.status_code = 200; r.json = lambda: {"records": json["records"]}; return r
        if method == "GET":
            table = url.rsplit("/", 1)[1]
            r.status_code = 200; r.json = lambda: {"records": self.records.get(table, [])}; return r
        r.status_code = 500; r.json = lambda: {"error": {"message": "nope"}}; r.text = "nope"; return r


@pytest.fixture
def fake(monkeypatch):
    f = FakeAirtable()

    class Cli:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def post(self, url, headers=None, json=None): return f.request("POST", url, headers, json)
        def patch(self, url, headers=None, json=None): return f.request("PATCH", url, headers, json)
        def get(self, url, headers=None, params=None): return f.request("GET", url, headers, None, params)
    monkeypatch.setattr(at.httpx, "Client", Cli)
    return f


def _brand(with_creds=True):
    slug = "at" + uuid.uuid4().hex[:6]
    bid = db.create_brand("AT " + slug, slug, "https://example.invalid", {}, "")
    ws.create_workspace(slug, ["instagram"])
    if with_creds:
        db.set_connector(bid, "airtable", {"api_key": "pat.x", "workspace_id": "wspTEST0000000001"})
    iid = db.insert_doc("ideas", bid, {"title": "Idea one", "format": "post", "hook": "h", "concept": "c", "virality": {"score": 70}}, channel="instagram")
    cid = db.insert_doc("creatives", bid, {"title": "Creative one", "caption": "Original caption", "format": "post"}, idea_id=iid, channel="instagram", format="post")
    db.update_doc("creatives", cid, asset_path="instagram/assets/x.png")
    c1 = db.insert_doc("calendar_items", bid, {"title": "Slot 1", "format": "post"}, idea_id=iid, channel="instagram", date="2030-01-05", time="10:00")
    c2 = db.insert_doc("calendar_items", bid, {"title": "Slot 2", "format": "reel"}, idea_id=None, channel="instagram", date="2030-01-07", time="18:00")
    return bid, iid, cid, c1, c2


def _admin():
    uid = db.create_user(f"a-{uuid.uuid4().hex[:6]}@t.local", auth.hash_pw("pw12345678"), role="admin")
    return {"Authorization": "Bearer " + auth.make_token(uid, "admin", "")}


def test_SCHEMA_has_calendar_fields():
    t = {x["name"]: x for x in at.schema("Neo")}
    names = [f["name"] for f in t[at.CAL]["fields"]]
    assert names[0] == "Title" and {"Date", "Status", "Channel", "Caption", "MB ID", "Last synced"} <= set(names)
    st = next(f for f in t[at.CAL]["fields"] if f["name"] == "Status")
    assert [c["name"] for c in st["options"]["choices"]] == at.STATUSES


def test_ENSURE_BASE_creates_once_and_stores_id(fake):
    bid, *_ = _brand()
    r1 = at.ensure_base(bid)
    assert r1["created"] and r1["base_id"] == "appTESTBASE000001" and r1["next"]
    body = fake.calls[0][2]
    assert body["workspaceId"] == "wspTEST0000000001" and body["name"].startswith("Marketing Brain — ") and len(body["tables"]) == 3
    r2 = at.ensure_base(bid)
    assert not r2["created"] and len([c for c in fake.calls if c[0] == "POST"]) == 1
    assert db.get_connectors(bid)["airtable"]["base_id"] == "appTESTBASE000001"


def test_ENSURE_BASE_needs_workspace_or_base():
    bid, *_ = _brand(with_creds=False)
    db.set_connector(bid, "airtable", {"api_key": "pat.x"})
    with pytest.raises(RuntimeError):
        at.ensure_base(bid)
    assert not at.connected(_brand(with_creds=False)[0])


def test_AGENCY_DEFAULT_used_when_brand_has_none(fake):
    bid, *_ = _brand(with_creds=False)
    db.set_setting("airtable", {"api_key": "pat.agency", "workspace_id": "wspAGENCY00000001"})
    try:
        assert at.connected(bid) and at.creds_for(bid)["_agency"]
        r = at.ensure_base(bid)
        assert r["created"] and db.get_connectors(bid)["airtable"] == {"base_id": "appTESTBASE000001", "_agency_default": True}
    finally:
        db.set_setting("airtable", {})


def test_PUSH_upserts_calendar_ideas_creatives(fake):
    bid, iid, cid, c1, c2 = _brand()
    r = at.push(bid)
    assert r["ok"] and r["pushed"] == {"calendar": 2, "ideas": 1, "creatives": 1}
    cal = fake.records[at.CAL]
    row = next(x for x in cal if x["fields"]["MB ID"] == c1)
    assert row["fields"]["Status"] == "Planned" and row["fields"]["Caption"] == "Original caption" and row["fields"]["MB Creative"] == cid
    assert row["fields"]["Date"] == "2030-01-05" and row["fields"]["Approval"] == "Waiting"
    patch_call = next(c for c in fake.calls if c[0] == "PATCH")
    assert patch_call[2]["performUpsert"]["fieldsToMergeOn"] == ["MB ID"]
    r2 = at.push(bid)  # idempotent: same rows, no duplicates
    assert len(fake.records[at.CAL]) == 2 and r2["pushed"]["calendar"] == 2


def test_PULL_applies_human_edits_and_remembers_caption(fake):
    bid, iid, cid, c1, c2 = _brand()
    at.push(bid)
    cal = fake.records[at.CAL]
    row = next(x for x in cal if x["fields"]["MB ID"] == c1)
    row["fields"].update({"Status": "Scheduled", "Date": "2030-01-09", "Time": "09:30", "Notes": "client prefers morning",
                          "Caption": "Tighter caption from the client"})
    fake.records[at.CAL].append({"id": "recSTRAY", "fields": {"Title": "Added by hand", "MB ID": "does-not-exist"}})
    r = at.pull(bid)
    assert r["ok"] and r["calendar"] == 1 and r["captions"] == 1 and r["skipped"] == 1
    it = db.get_doc("calendar_items", c1)
    assert it["status"] == "scheduled" and it["date"] == "2030-01-09" and it["time"] == "09:30" and it["payload"]["notes"] == "client prefers morning"
    cr = db.get_doc("creatives", cid)
    assert cr["payload"]["caption"] == "Tighter caption from the client" and cr["payload"].get("approval") is None
    mem = db.list_docs("brand_memory", bid)
    assert any("Airtable" in (m["payload"] or {}).get("content", "") for m in mem)
    # nothing changed → nothing written
    r2 = at.pull(bid)
    assert r2["calendar"] == 0 and r2["captions"] == 0


def test_ROUTES_status_push_pull_and_tenancy(fake):
    bid, *_ = _brand(); h = _admin()
    s = client.get(f"/api/brands/{bid}/airtable", headers=h).json()
    assert s["connected"] and s["can_create"] and s["base_id"] is None
    r = client.post(f"/api/brands/{bid}/airtable/push", headers=h)
    assert r.status_code == 200 and r.json()["created"] and r.json()["url"].startswith("https://airtable.com/app")
    assert client.post(f"/api/brands/{bid}/airtable/pull", headers=h).status_code == 200
    s = client.get(f"/api/brands/{bid}/airtable", headers=h).json()
    assert s["base_id"] == "appTESTBASE000001" and s["last_push"] and s["last_pull"]
    other, *_ = _brand(with_creds=False)
    uid = db.create_user(f"c-{uuid.uuid4().hex[:6]}@t.local", auth.hash_pw("pw12345678"), role="client", brand_id=other)
    ch = {"Authorization": "Bearer " + auth.make_token(uid, "client", other)}
    assert client.post(f"/api/brands/{bid}/airtable/push", headers=ch).status_code == 403
    assert client.post(f"/api/brands/{other}/airtable/push", headers=ch).status_code == 400  # not connected


def test_CALENDAR_BUILD_pushes_automatically(fake, monkeypatch):
    from app.routes import _shared
    bid, *_ = _brand(); h = _admin()
    monkeypatch.setattr(_shared.ai_engine, "generate_calendar", lambda *a, **k: [
        {"idea_id": None, "channel": "instagram", "date": "2030-02-01", "time": "10:00", "title": "New slot", "format": "post"}])
    r = client.post(f"/api/brands/{bid}/calendar", json={"days": 7}, headers=h)
    assert r.status_code == 200 and r.json()["airtable"]["ok"] and r.json()["airtable"]["pushed"]["calendar"] == 1


def test_AGENCY_SETTINGS_airtable_default():
    h = _admin()
    r = client.put("/api/agency/settings", json={"airtable": {"api_key": "pat.a", "workspace_id": "nope"}}, headers=h)
    assert r.status_code == 400
    r = client.put("/api/agency/settings", json={"airtable": {"api_key": "pat.a", "workspace_id": "wspAGENCY00000002"}}, headers=h)
    assert r.status_code == 200 and r.json()["airtable"]["configured"]
    g = client.get("/api/agency/settings", headers=h).json()
    assert g["airtable"]["workspace_id"] == "wspAGENCY00000002" and "api_key" not in json.dumps(g)
    db.set_setting("airtable", {})

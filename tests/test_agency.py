"""Agency Operating System — twenty clients, one operator.

Covers: manager role isolation, portfolio health + alerts, the bounded fair
BrandPool, the weekly cycle across 20 brands with per-client caps, bulk
approve/publish going through the same gates as single-item routes (no IDOR,
no approval bypass, no duplicate live publish), templated onboarding, per-client
config reaching the prompt, monthly reports and white-label settings.
AI is faked; no network.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "agency.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ["BG_SYNC"] = "1"          # pool jobs run inline: deterministic
os.environ.pop("DIRECT_ACCESS", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.ai import engine  # noqa: E402
from app.core import auth, database as db, guard  # noqa: E402
from app.main import app  # noqa: E402
from app.services import (agency_cycle, agency_pool, agency_templates, brand_config,  # noqa: E402
                          workspace as ws)

client = TestClient(app)

FAKE = {
    "ideas": [{"title": f"Idea {n}", "format": "post", "hook": "h", "concept": "c", "virality": {"score": 40 + n}}
              for n in range(1, 5)],
    "calendar": [{"idea_id": None, "channel": "instagram", "date": "2031-01-0%d" % n, "time": "10:00",
                  "title": f"Slot {n}", "format": "post", "notes": ""} for n in range(1, 4)],
    "title": "Fake creative", "format": "post", "caption": "cap", "hashtags": {"broad": ["x"]}, "image_prompt": "p",
}


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    calls = {"json": [], "chat": []}

    def _json(system, user, *a, **k):
        calls["json"].append((system, user))
        import copy
        return copy.deepcopy(FAKE)

    def _chat(messages, *a, **k):
        calls["chat"].append(messages)
        return "We did things. It produced results. Next we recommend more."

    monkeypatch.setattr(engine, "_json_chat", _json)
    monkeypatch.setattr(engine, "_chat", _chat)
    monkeypatch.setattr(engine, "generate_image", lambda *a, **k: b"\x89PNG fake")
    monkeypatch.delenv("GENERATION_DISABLED", raising=False)
    monkeypatch.delenv("GEN_DAILY_CAP", raising=False)
    guard._hits.clear()
    return calls


def _u():
    return uuid.uuid4().hex[:8]


def _brand(name="Client", ready=True, vertical="generic"):
    bid = db.create_brand(f"{name} {_u()}", ws.slugify(f"{name} {_u()}"), "", {}, "")
    brand_config.seed(bid, agency_templates.get(vertical)["config"])
    if ready:
        db.update_brand(bid, setup={"channels": ["instagram"], "cadence": "3/wk", "goals": [], "language": "English"},
                        status="ready")
        ws.create_workspace(db.get_brand(bid)["slug"], ["instagram"])
    return bid


def _user(role, bid="", brand_ids=None):
    uid = db.create_user(f"{role}-{_u()}@t.local", auth.hash_pw("pw12345678"), role=role, brand_id=bid)
    if brand_ids is not None:
        db.set_assignments(uid, brand_ids)
    return uid, {"Authorization": "Bearer " + auth.make_token(uid, role, bid)}


def _creative(bid, approved=False):
    p = {"title": "T", "format": "post", "caption": "c", "hashtags": {"broad": ["a"]}}
    if approved:
        p["approval"] = {"state": "approved", "comment": "", "by": "x", "role": "admin", "at": 0}
    return db.insert_doc("creatives", bid, p, channel="instagram", format="post")


# ---------------- manager role ----------------

def test_MGR_sees_only_assigned_brands():
    a, b, c = _brand("A"), _brand("B"), _brand("C")
    _, h = _user("manager", brand_ids=[a, b])
    ids = {x["id"] for x in client.get("/api/brands", headers=h).json()}
    assert a in ids and b in ids and c not in ids
    assert client.get(f"/api/brands/{a}", headers=h).status_code == 200
    assert client.get(f"/api/brands/{c}", headers=h).status_code == 403
    q = client.get("/api/approvals", headers=h).json()
    assert all(i["brand_id"] in (a, b) for i in q["waiting_for_approval"])


def test_MGR_unassignment_takes_effect_immediately():
    a = _brand("A")
    uid, h = _user("manager", brand_ids=[a])
    assert client.get(f"/api/brands/{a}", headers=h).status_code == 200
    db.set_assignments(uid, [])
    assert client.get(f"/api/brands/{a}", headers=h).status_code == 403


def test_MGR_cannot_reach_admin_screens():
    _, h = _user("manager", brand_ids=[])
    assert client.get("/api/users", headers=h).status_code == 403
    assert client.post("/api/agency/onboard", json={"name": "X co", "vertical": "generic"}, headers=h).status_code == 403
    assert client.put("/api/agency/settings", json={"branding": {"agency_name": "x"}}, headers=h).status_code == 403


def test_MGR_admin_creates_manager_and_assigns():
    a, b = _brand("A"), _brand("B")
    _, adm = _user("admin")
    r = client.post("/api/users", json={"email": f"m-{_u()}@t.local", "password": "pw12345678",
                                        "role": "manager", "brand_ids": [a]}, headers=adm)
    assert r.status_code == 200 and r.json()["brand_ids"] == [a]
    uid = r.json()["id"]
    r = client.put(f"/api/users/{uid}/brands", json={"brand_ids": [a, b]}, headers=adm)
    assert sorted(r.json()["brand_ids"]) == sorted([a, b])
    assert client.put(f"/api/users/{uid}/brands", json={"brand_ids": ["nope"]}, headers=adm).status_code == 400
    r = client.post("/api/users", json={"email": f"z-{_u()}@t.local", "password": "pw12345678", "role": "superuser"},
                    headers=adm)
    assert r.status_code == 400
    users = client.get("/api/users", headers=adm).json()
    me = next(u for u in users if u["id"] == uid)
    assert sorted(me["brand_ids"]) == sorted([a, b])


def test_MGR_client_and_owner_locked_out_of_agency_routes():
    a = _brand("A")
    _, ch = _user("client", bid=a)
    _, oh = _user("owner", bid=a)
    for h in (ch, oh):
        assert client.get("/api/agency/portfolio", headers=h).status_code == 403
        assert client.post("/api/agency/cycle", json={}, headers=h).status_code == 403
        assert client.post("/api/agency/bulk/approve", json={"items": []}, headers=h).status_code == 403


def test_MGR_workspace_files_scoped_to_assignments():
    a, c = _brand("A"), _brand("C")
    ba, bc = db.get_brand(a), db.get_brand(c)
    ws.write_text(ba["slug"], "brand-profile/x.txt", "a")
    ws.write_text(bc["slug"], "brand-profile/x.txt", "c")
    _, h = _user("manager", brand_ids=[a])
    assert client.get(f"/workspaces/{ba['slug']}/brand-profile/x.txt", headers=h).status_code == 200
    assert client.get(f"/workspaces/{bc['slug']}/brand-profile/x.txt", headers=h).status_code == 404


# ---------------- portfolio ----------------

def test_PORTFOLIO_health_and_alerts():
    a = _brand("Quiet", ready=True)
    b = _brand("Busy", ready=True)
    _creative(b)
    db.set_connector(b, "instagram", {"token": "x"})
    _, h = _user("manager", brand_ids=[a, b])
    p = client.get("/api/agency/portfolio", headers=h).json()
    assert p["totals"]["clients"] == 2
    rows = {r["brand_id"]: r for r in p["clients"]}
    assert "no_connectors" in {x["code"] for x in rows[a]["alerts"]}
    assert "quiet" in {x["code"] for x in rows[a]["alerts"]}
    assert "approvals_waiting" in {x["code"] for x in rows[b]["alerts"]}
    assert rows[b]["score"] > rows[a]["score"]
    assert p["pool"]["max_workers"] >= 1
    al = client.get("/api/agency/alerts", headers=h).json()
    assert al["count"] >= 3 and all(x["brand_id"] in (a, b) for x in al["alerts"])


def test_PORTFOLIO_stale_approval_is_critical():
    a = _brand("Stale")
    cid = _creative(a)
    db.update_doc("creatives", cid, created_at=time.time() - 80 * 3600)
    _, h = _user("admin")
    rows = {r["brand_id"]: r for r in client.get("/api/agency/portfolio", headers=h).json()["clients"]}
    assert any(x["code"] == "approvals_stale" and x["level"] == "crit" for x in rows[a]["alerts"])


# ---------------- pool ----------------

def test_POOL_bounded_and_fair(monkeypatch):
    monkeypatch.setenv("BG_SYNC", "0")
    monkeypatch.setenv("AGENCY_MAX_WORKERS", "2")
    pool = agency_pool.BrandPool()
    peak = {"n": 0, "cur": 0}
    lock = threading.Lock()
    order = []

    def job(log, tag):
        with lock:
            peak["cur"] += 1
            peak["n"] = max(peak["n"], peak["cur"])
            order.append(tag)
        time.sleep(0.05)
        with lock:
            peak["cur"] -= 1
        return tag

    # brand A floods 4 jobs, brand B and C submit one each afterwards
    for i in range(4):
        pool.submit("A", "t", job, f"A{i}")
    pool.submit("B", "t", job, "B0")
    pool.submit("C", "t", job, "C0")
    assert pool.wait_idle(10)
    assert peak["n"] <= 2, "pool exceeded its worker ceiling"
    # fairness: B and C ran before A's later jobs, and A never ran two at once
    assert order.index("B0") < order.index("A2") and order.index("C0") < order.index("A3")
    assert all(j["state"] == "done" for j in pool.jobs_for(["A", "B", "C"]))
    assert db.get_job(agency_pool.JOB_KIND, pool.jobs_for(["A"])[0]["id"])["state"] == "done"


def test_POOL_failed_job_is_recorded():
    pool = agency_pool.BrandPool()

    def bad(log):
        log("about to fail")
        raise RuntimeError("boom")
    j = pool.submit("Z", "t", bad)
    assert j["state"] == "failed" and "boom" in j["error"]
    assert "trace" not in pool.get(j["id"])


# ---------------- cycle ----------------

def test_CYCLE_twenty_clients_land_in_approvals(_fake_ai):
    ids = [_brand(f"C{n}") for n in range(20)]
    _, h = _user("admin")
    r = client.post("/api/agency/cycle", json={"brand_ids": ids, "label": "test"}, headers=h)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["state"] == "done" and c["counts"]["done"] == 20 and c["counts"]["failed"] == 0
    for bid in ids:
        res = c["brands"][bid]["result"]
        assert res["ideas"] == 4 and res["calendar"] == 3 and res["creatives"] == 3
        cr = db.list_docs("creatives", bid)
        assert len(cr) == 3 and all(not (x["payload"].get("approval") or {}).get("state") for x in cr)
        assert not db.list_docs("publish_queue", bid), "a cycle must never publish"
        assert db.get_brand(bid)["profile"]["last_cycle"]["summary"]["creatives"] == 3
    # recorded + visible
    lst = client.get("/api/agency/cycles", headers=h).json()["cycles"]
    assert any(x["id"] == c["id"] for x in lst)
    assert client.get(f"/api/agency/cycles/{c['id']}", headers=h).json()["progress"] == 1.0


def test_CYCLE_per_client_cap_stops_only_that_client():
    a, b = _brand("Capped"), _brand("Free")
    brand_config.set(a, {"caps": {"gen_daily": 1}})
    day = time.strftime("%Y-%m-%d", time.gmtime())
    db.bump_gen_usage(a, day)  # already at cap
    _, h = _user("admin")
    c = client.post("/api/agency/cycle", json={"brand_ids": [a, b]}, headers=h).json()
    ra, rb = c["brands"][a]["result"], c["brands"][b]["result"]
    assert ra["ideas"] == 0 and ra["creatives"] == 0 and any("client daily cap" in s for s in ra["skipped"])
    assert rb["ideas"] == 4 and rb["creatives"] == 3


def test_CYCLE_global_kill_switch_respected(monkeypatch):
    a = _brand("K")
    monkeypatch.setenv("GENERATION_DISABLED", "1")
    _, h = _user("admin")
    c = client.post("/api/agency/cycle", json={"brand_ids": [a]}, headers=h).json()
    r = c["brands"][a]["result"]
    assert r["ideas"] == 0 and r["creatives"] == 0 and r["skipped"]


def test_CYCLE_manager_cannot_cycle_unassigned_brand():
    a, c = _brand("A"), _brand("C")
    _, h = _user("manager", brand_ids=[a])
    assert client.post("/api/agency/cycle", json={"brand_ids": [c]}, headers=h).status_code == 403
    r = client.post("/api/agency/cycle", json={}, headers=h)  # empty = all visible ready brands
    assert r.status_code == 200 and set(r.json()["brand_ids"]) == {a}


def test_CYCLE_cron_kicks_due_brands(monkeypatch):
    a = _brand("Due")
    monkeypatch.setenv("CRON_KEY", "k")
    before = agency_cycle.due_brands()
    assert a in before
    r = client.get("/api/cron?key=k").json()
    assert r["agency_cycle"] and r["agency_cycle"]["brands"] >= 1
    assert a not in agency_cycle.due_brands()
    assert client.get("/api/cron?key=wrong").json().get("agency_cycle") is None


def test_CYCLE_queued_brand_is_not_due_again(monkeypatch):
    a = _brand("Queued")
    monkeypatch.setattr(agency_pool.POOL, "submit", lambda *x, **k: {"id": "fake", "state": "queued"})
    agency_cycle.start([a], by="t")
    assert a not in agency_cycle.due_brands(), "a client waiting in the pool must not be re-queued"


def test_JOBS_stale_queued_jobs_interrupted_on_boot():
    db.save_job(agency_pool.JOB_KIND, "old-q", "queued", [], {"brand_id": "x"})
    db.save_job(agency_pool.JOB_KIND, "old-r", "running", [], {"brand_id": "x"})
    db.interrupt_stale_jobs(older_than_s=-1)
    assert db.get_job(agency_pool.JOB_KIND, "old-q")["state"] == "interrupted"
    assert db.get_job(agency_pool.JOB_KIND, "old-r")["state"] == "interrupted"


# ---------------- bulk ----------------

def test_BULK_approve_same_gate_no_idor():
    a, c = _brand("A"), _brand("C")
    ca, cc = _creative(a), _creative(c)
    _, h = _user("manager", brand_ids=[a])
    r = client.post("/api/agency/bulk/approve", json={"items": [
        {"brand_id": a, "creative_id": ca},
        {"brand_id": c, "creative_id": cc},          # not assigned
        {"brand_id": a, "creative_id": cc},          # wrong brand for this creative (IDOR)
    ]}, headers=h).json()
    assert r["ok"] == 1 and r["failed"] == 2
    assert db.get_doc("creatives", ca)["payload"]["approval"]["state"] == "approved"
    assert not db.get_doc("creatives", cc)["payload"].get("approval")
    assert "forbidden" in r["results"][1]["error"] and "not found" in r["results"][2]["error"]


def test_BULK_changes_requested_needs_comment():
    a = _brand("A")
    ca = _creative(a)
    _, h = _user("admin")
    r = client.post("/api/agency/bulk/approve", json={"items": [{"brand_id": a, "creative_id": ca}],
                                                      "state": "changes_requested"}, headers=h)
    assert r.status_code == 400
    r = client.post("/api/agency/bulk/approve", json={"items": [{"brand_id": a, "creative_id": ca}],
                                                      "state": "changes_requested", "comment": "shorter"}, headers=h)
    assert r.status_code == 200 and r.json()["ok"] == 1


def test_BULK_publish_live_requires_approval_and_creds_and_no_duplicate(monkeypatch):
    from app.services import connectors
    a = _brand("A")
    unapproved, approved = _creative(a), _creative(a, approved=True)
    _, h = _user("admin")
    r = client.post("/api/agency/bulk/publish", json={"mode": "live", "items": [
        {"brand_id": a, "creative_id": unapproved}, {"brand_id": a, "creative_id": approved}]}, headers=h).json()
    assert r["ok"] == 0 and "approved" in r["results"][0]["error"] and "credentials" in r["results"][1]["error"]
    db.set_connector(a, "instagram", {"token": "x"})
    monkeypatch.setattr(connectors, "publish", lambda *a, **k: {"id": "ig1"})
    r = client.post("/api/agency/bulk/publish", json={"mode": "live", "items": [
        {"brand_id": a, "creative_id": approved}]}, headers=h).json()
    assert r["ok"] == 1 and r["results"][0]["status"] == "published"
    r = client.post("/api/agency/bulk/publish", json={"mode": "live", "items": [
        {"brand_id": a, "creative_id": approved}]}, headers=h).json()
    assert r["ok"] == 0 and "already published" in r["results"][0]["error"]
    assert sum(1 for p in db.list_docs("publish_queue", a) if p["status"] == "published") == 1


def test_BULK_publish_mode_validated_and_simulated_never_published():
    a = _brand("A")
    ca = _creative(a)
    _, h = _user("admin")
    assert client.post("/api/agency/bulk/publish", json={"mode": "LIVE", "items": [{"brand_id": a, "creative_id": ca}]},
                       headers=h).status_code == 400
    r = client.post("/api/agency/bulk/publish", json={"mode": "simulated", "items": [{"brand_id": a, "creative_id": ca}]},
                    headers=h).json()
    assert r["ok"] == 1 and r["results"][0]["status"] == "simulated"


def test_BULK_queue_grouped_by_visible_brand():
    a, c = _brand("A"), _brand("C")
    _creative(a); _creative(a); _creative(c)
    _, h = _user("manager", brand_ids=[a])
    q = client.get("/api/agency/queue", headers=h).json()
    assert [g["brand_id"] for g in q["groups"]] == [a] and q["totals"]["waiting"] == 2


# ---------------- onboarding + config ----------------

def test_ONBOARD_template_seeds_config_and_marks_ready(_fake_ai):
    _, h = _user("admin")
    r = client.post("/api/agency/onboard", json={"name": f"Smile Dental {_u()}", "vertical": "dental",
                                                 "config": {"cta": {"contact": "+91 90000 00000"}},
                                                 "setup": {"channels": ["instagram"]}}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    b = db.get_brand(d["brand_id"])
    assert b["status"] == "ready" and d["job_state"] == "done"
    cfg = brand_config.get(b)
    assert cfg["vertical"] == "dental" and cfg["cta"]["contact"] == "+91 90000 00000"
    assert "BOOK" in cfg["triggers"] and cfg["pointer_allowed"] is False
    assert b["setup"]["channels"] == ["instagram"] and b["setup"]["mode"] == "auto"
    assert client.post("/api/agency/onboard", json={"name": "X co", "vertical": "plumbing"}, headers=h).status_code == 400
    assert client.post("/api/agency/onboard", json={"name": "X co", "website": "http://127.0.0.1/"}, headers=h).status_code == 400


def test_CONFIG_reaches_prompt_and_is_gated(_fake_ai):
    a = _brand("Cfg", vertical="restaurant")
    brand_config.set(a, {"dont": ["mention competitors"], "market_brief": {"location": "Baner, Pune"}})
    _, h = _user("admin")
    r = client.post(f"/api/brands/{a}/ideas", json={"channels": ["instagram"], "count": 2}, headers=h)
    assert r.status_code == 200, r.text
    text = " ".join(u for _, u in _fake_ai["json"])
    assert "mention competitors" in text and "Baner, Pune" in text and "GROUNDED PROJECT FACTS" not in text
    _, ch = _user("client", bid=a)
    assert client.get(f"/api/brands/{a}/config", headers=ch).status_code == 200
    assert client.put(f"/api/brands/{a}/config", json={"config": {"dont": []}}, headers=ch).status_code == 403
    r = client.put(f"/api/brands/{a}/config", json={"config": {"caps": {"gen_daily": 5}, "evil": 1}}, headers=h).json()
    assert r["config"]["caps"]["gen_daily"] == 5 and "evil" not in r["config"]
    assert r["config"]["caps"]["creatives_per_cycle"] == 5  # dict keys merge, not replace


def test_TEMPLATES_listed_for_operators():
    _, h = _user("manager", brand_ids=[])
    t = client.get("/api/agency/templates", headers=h).json()
    ids = {x["id"] for x in t["templates"]}
    assert {"real_estate", "dental", "restaurant", "saas", "generic"} <= ids


# ---------------- reports + settings ----------------

def test_REPORT_monthly_numbers_narrative_and_html(_fake_ai):
    a = _brand("Rep")
    _creative(a, approved=True)
    db.insert_doc("publish_queue", a, {"simulated": False}, creative_id="x", channel="instagram", mode="live", status="published")
    db.insert_doc("metrics", a, {"views": 120, "likes": 8}, channel="instagram", post_ref="p1")
    _, h = _user("admin")
    period = time.strftime("%Y-%m", time.gmtime())
    assert client.post(f"/api/brands/{a}/reports", json={"period": "2026/09"}, headers=h).status_code == 400
    r = client.post(f"/api/brands/{a}/reports", json={"period": period}, headers=h)
    assert r.status_code == 200, r.text
    rep = r.json()
    n = rep["payload"]["numbers"]
    assert n["creatives"] == 1 and n["approved"] == 1 and n["published"] == 1 and n["metric_totals"]["views"] == 120
    assert "recommend" in rep["payload"]["narrative"]
    assert any(x["id"] == rep["id"] for x in client.get(f"/api/brands/{a}/reports", headers=h).json()["reports"])
    client.put("/api/agency/settings", json={"branding": {"agency_name": "Acme Growth", "accent": "#ff0000"}}, headers=h)
    html = client.get(f"/api/brands/{a}/reports/{rep['id']}/html", headers=h).text
    assert "Acme Growth" in html and "#ff0000" in html and "<script" not in html
    # tenant wall on reports
    c = _brand("Other")
    _, oh = _user("client", bid=c)
    assert client.get(f"/api/brands/{a}/reports/{rep['id']}", headers=oh).status_code == 403
    assert client.get(f"/api/brands/{c}/reports/{rep['id']}", headers=oh).status_code == 404


def test_REPORT_renders_without_model(monkeypatch):
    a = _brand("NoAI")
    monkeypatch.setattr(engine, "_chat", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    _, h = _user("admin")
    r = client.post(f"/api/brands/{a}/reports", json={"period": "2026-01"}, headers=h)
    assert r.status_code == 200 and r.json()["payload"]["narrative"] == ""


def test_SETTINGS_validation_and_public_branding():
    _, h = _user("admin")
    assert client.put("/api/agency/settings", json={"branding": {"accent": "red"}}, headers=h).status_code == 400
    assert client.put("/api/agency/settings", json={"branding": {"logo_url": "javascript:alert(1)"}}, headers=h).status_code == 400
    assert client.put("/api/agency/settings", json={"defaults": {"approval_sla_hours": "x"}}, headers=h).status_code == 400
    r = client.put("/api/agency/settings", json={"branding": {"agency_name": "Neo Agency"},
                                                 "defaults": {"approval_sla_hours": 24, "auto_cycle": False}}, headers=h).json()
    assert r["branding"]["agency_name"] == "Neo Agency" and r["defaults"]["approval_sla_hours"] == 24
    assert client.get("/api/agency/branding").json()["agency_name"] == "Neo Agency"
    assert "footer" not in client.get("/api/agency/branding").json()
    assert agency_cycle.due_brands() == []  # auto_cycle off → nothing is due
    client.put("/api/agency/settings", json={"defaults": {"auto_cycle": True}}, headers=h)


def test_DELETE_brand_cascades_assignments_and_reports():
    a = _brand("Gone")
    uid, _ = _user("manager", brand_ids=[a])
    db.insert_doc("reports", a, {"x": 1}, period="2026-01", kind="monthly")
    _, h = _user("admin")
    assert client.delete(f"/api/brands/{a}", headers=h).status_code == 200
    assert db.get_assignments(uid) == [] and db.list_docs("reports", a) == []

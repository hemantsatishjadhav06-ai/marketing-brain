"""Paid-media planner v2 + Connections hub.

The model proposes; the planner owns the numbers and the rules. These tests pin
the rules: budget capped and split exactly, HOUSING restrictions applied and
re-applied on edit, estimates from benchmarks, Meta launch declares the special
category and creates one ad set per audience (PAUSED), the catalogue is honest,
connect validates fields, test-connection is read-only and records status.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "ads2.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ.setdefault("MAX_DAILY_AD_BUDGET", "5000")
os.environ.pop("DIRECT_ACCESS", None)
os.environ.pop("AD_SPEND_DISABLED", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.core import auth, database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import channels  # noqa: E402
from app.services import ad_planner, agency_templates, brand_config, channel_catalog, meta_ads  # noqa: E402
from app.services import workspace as ws  # noqa: E402

client = TestClient(app)

META_RAW = {
    "campaign": {"name": "Neopolis — Leads", "objective": "OUTCOME_LEADS"},
    "ad_sets": [
        {"name": "Kokapet buyers", "audience_label": "IT professionals 28-45",
         "targeting": {"geo": {"countries": ["IN"], "cities": [{"name": "Hyderabad", "radius_km": 10}], "pincodes": ["500075"]},
                       "age_min": 28, "age_max": 45, "genders": ["male"], "interests": ["Real estate", "Apartments"],
                       "lookalike": "1% of leads", "exclusions": ["renters"]},
         "placements": ["instagram_feed", "instagram_reels", "tiktok"], "budget_share": 0.7, "ad_ids": ["A"]},
        {"name": "NRI investors", "targeting": {"geo": {"countries": ["AE", "US"]}, "age_min": 30, "age_max": 60,
                                                "interests": ["NRI investment"]},
         "placements": ["facebook_feed"], "budget_share": 0.3, "ad_ids": ["B"]},
    ],
    "ads": [{"id": "A", "primary_text": "p", "headline": "x" * 60, "description": "d" * 50, "cta": "WHATSAPP_MESSAGE"},
            {"id": "B", "primary_text": "q", "headline": "h", "description": "d"}],
    "lead_capture": {"method": "whatsapp"}, "kpis": {"primary": "cpl"},
}
GOOGLE_RAW = {
    "campaign": {"name": "Neopolis — Search"}, "locations": [{"name": "Hyderabad", "radius_km": 30}],
    "bidding": {"strategy": "NONSENSE"},
    "ad_groups": [{"name": "Landlord share", "budget_share": 0.6,
                   "keywords": [{"text": "landlord share flats hyderabad", "match": "exact"}, "flats in kokapet", {"text": "", "match": "BROAD"}],
                   "negative_keywords": ["free", "jobs"], "rsa": {"headlines": ["h" * 40], "descriptions": ["d" * 100]}},
                  {"name": "Kokapet", "budget_share": 0.4, "keywords": [{"text": "kokapet 3bhk", "match": "PHRASE"}]}],
}


def _brand(vertical="real_estate"):
    bid = db.create_brand(f"Co {uuid.uuid4().hex[:6]}", ws.slugify("co" + uuid.uuid4().hex[:6]), "https://www.neopolisinfra.com", {}, "")
    brand_config.seed(bid, agency_templates.get(vertical)["config"])
    return bid


def _user(role, bid=""):
    uid = db.create_user(f"{role}-{uuid.uuid4().hex[:8]}@t.local", auth.hash_pw("pw12345678"), role=role, brand_id=bid)
    return {"Authorization": "Bearer " + auth.make_token(uid, role, bid)}


@pytest.fixture(autouse=True)
def _mock_ai(monkeypatch):
    import copy
    holder = {"raw": META_RAW}

    def fake(system, user, *a, **k):
        holder["last"] = (system, user)
        return copy.deepcopy(GOOGLE_RAW if "Google Ads search planner" in system else holder["raw"])
    monkeypatch.setattr(channels.ai_engine, "_json_chat", fake)
    return holder


# ---------------- planner rules ----------------

def test_PLAN_housing_rules_applied_for_real_estate():
    b = db.get_brand(_brand("real_estate"))
    p = ad_planner.normalize_meta(META_RAW, b, 2000, "INR", "OUTCOME_LEADS")
    assert p["campaign"]["special_ad_category"] == "HOUSING"
    s0 = p["ad_sets"][0]["targeting"]
    assert (s0["age_min"], s0["age_max"]) == (18, 65) and s0["genders"] == [] and s0["exclusions"] == []
    assert s0["geo"]["cities"][0]["radius_km"] == 24 and "pincodes" not in s0["geo"]
    assert s0["lookalike"].startswith("Special Ad Audience")
    assert any("gender" in n for n in p["compliance"]["applied"]) and p["compliance"]["rules"]
    assert "tiktok" not in p["ad_sets"][0]["placements"]


def test_PLAN_non_housing_keeps_demographics():
    b = db.get_brand(_brand("dental"))
    p = ad_planner.normalize_meta(META_RAW, b, 1000, "INR", "OUTCOME_LEADS")
    assert p["campaign"]["special_ad_category"] == "NONE"
    s0 = p["ad_sets"][0]["targeting"]
    assert (s0["age_min"], s0["age_max"]) == (28, 45) and s0["genders"] == ["male"]
    assert p["targeting"]["genders"] == [1]


def test_PLAN_budget_capped_and_split_exactly():
    b = db.get_brand(_brand())
    p = ad_planner.normalize_meta(META_RAW, b, 999999, "INR", "OUTCOME_LEADS")
    assert p["budget"]["daily_total"] == 5000 and p["daily_budget"] == 5000
    assert round(sum(s["daily_budget"] for s in p["ad_sets"]), 2) == 5000
    assert p["ad_sets"][0]["daily_budget"] == 3500 and p["ad_sets"][1]["daily_budget"] == 1500
    assert p["budget"]["monthly_estimate"] == 150000
    assert p["ads"][0]["headline"] == "x" * 40 and len(p["ads"][0]["description"]) == 30


def test_PLAN_estimates_are_benchmarks_not_guesses():
    e = ad_planner.estimates("real_estate", 2000)
    assert "benchmark" in e["basis"] and e["daily"]["leads"][0] < e["daily"]["leads"][1]
    assert e["period"]["spend"] == 60000 and e["cpl_range"] == [250, 900]


def test_PLAN_google_normalised():
    b = db.get_brand(_brand())
    p = ad_planner.normalize_google(GOOGLE_RAW, b, 1500, "INR")
    g0 = p["ad_groups"][0]
    assert [k["match"] for k in g0["keywords"]] == ["EXACT", "PHRASE"] and len(g0["keywords"]) == 2
    assert len(g0["rsa"]["headlines"][0]) == 30 and len(g0["rsa"]["descriptions"][0]) == 90
    assert p["bidding"]["strategy"] == "MAXIMIZE_CONVERSIONS"
    assert round(sum(g["daily_budget"] for g in p["ad_groups"]), 2) == 1500
    assert "RERA" in p["compliance"]["policy_notes"][0]
    assert p["keywords"] and p["rsa"]["final_url"] == "https://www.neopolisinfra.com"


# ---------------- routes ----------------

def test_ROUTE_plan_meta_returns_full_structure(_mock_ai):
    bid = _brand(); h = _user("admin")
    r = client.post(f"/api/brands/{bid}/ads/meta/plan", json={"objective": "OUTCOME_LEADS", "daily_budget": 1200, "prompt": "site visits"}, headers=h)
    assert r.status_code == 200, r.text
    p = r.json()["plan"]
    assert r.json()["status"] == "draft" and len(p["ad_sets"]) == 2 and p["estimates"]["period_days"] == 30
    assert p["compliance"]["special_ad_category"] == "HOUSING" and p["summary"]
    assert "Client config" in _mock_ai["last"][1]
    row = db.get_doc("campaigns", r.json()["campaign_id"])
    assert row["status"] == "draft" and row["daily_budget"] == 1200
    assert client.get(f"/api/brands/{bid}/ads/meta/campaigns/{row['id']}", headers=h).json()["id"] == row["id"]


def test_ROUTE_edit_recaps_and_reapplies_compliance():
    bid = _brand(); h = _user("admin")
    cid = client.post(f"/api/brands/{bid}/ads/meta/plan", json={"daily_budget": 1000}, headers=h).json()["campaign_id"]
    plan = db.get_doc("campaigns", cid)["payload"]
    plan["ad_sets"][0]["targeting"]["age_min"] = 30
    plan["ad_sets"][0]["targeting"]["genders"] = ["female"]
    plan["ad_sets"][0]["budget_share"] = 0.2
    plan["ad_sets"][1]["budget_share"] = 0.8
    r = client.put(f"/api/brands/{bid}/ads/meta/campaigns/{cid}", json={"plan": {**plan, "daily_budget": 90000, "platform_ids": {"hack": 1}}}, headers=h)
    assert r.status_code == 200, r.text
    p = r.json()["plan"]
    assert p["daily_budget"] == 5000 and p["ad_sets"][1]["daily_budget"] == 4000
    assert p["ad_sets"][0]["targeting"]["age_min"] == 18 and p["ad_sets"][0]["targeting"]["genders"] == []
    assert not p.get("platform_ids")
    assert db.get_doc("campaigns", cid)["daily_budget"] == 5000
    # client logins may read but not edit
    ch = _user("client", bid)
    assert client.put(f"/api/brands/{bid}/ads/meta/campaigns/{cid}", json={"plan": plan}, headers=ch).status_code == 403
    # live campaigns must be paused first
    db.update_doc("campaigns", cid, status="live")
    assert client.put(f"/api/brands/{bid}/ads/meta/campaigns/{cid}", json={"plan": plan}, headers=h).status_code == 409


def test_ROUTE_plan_google_structure():
    bid = _brand(); h = _user("admin")
    r = client.post(f"/api/brands/{bid}/ads/google/plan", json={"daily_budget": 800}, headers=h)
    assert r.status_code == 200, r.text
    p = r.json()["plan"]
    assert p["campaign"]["type"] == "SEARCH" and len(p["ad_groups"]) == 2 and p["budget"]["daily_total"] == 800


def test_LAUNCH_meta_declares_housing_and_creates_each_adset(monkeypatch):
    bid = _brand(); h = _user("admin")
    cid = client.post(f"/api/brands/{bid}/ads/meta/plan", json={"daily_budget": 1000}, headers=h).json()["campaign_id"]
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "123", "page_id": "p"})
    calls = []

    class FakeResp:
        def __init__(self, path):
            self.path = path
        def raise_for_status(self):
            pass
        def json(self):
            return {"id": f"{self.path.split('/')[-1]}-{len(calls)}"}

    class FakeCli:
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def post(self, url, data=None):
            calls.append((url, data))
            return FakeResp(url)
    monkeypatch.setattr(meta_ads.httpx, "Client", FakeCli)
    r = client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": True}, headers=h)
    assert r.status_code == 200, r.text
    camp = next(d for u, d in calls if u.endswith("/campaigns"))
    assert camp["special_ad_categories"] == '["HOUSING"]' and camp["status"] == "PAUSED"
    adsets = [d for u, d in calls if u.endswith("/adsets")]
    assert len(adsets) == 2 and all(d["status"] == "PAUSED" for d in adsets)
    assert adsets[0]["daily_budget"] == 70000 and adsets[1]["daily_budget"] == 30000  # paise
    assert '"age_min": 18' in adsets[0]["targeting"] and "genders" not in adsets[0]["targeting"]
    assert r.json()["platform_ids"]["adset_ids"] and db.get_doc("campaigns", cid)["status"] == "approved"


def test_LAUNCH_still_blocked_without_approval():
    bid = _brand(); h = _user("admin")
    cid = client.post(f"/api/brands/{bid}/ads/meta/plan", json={"daily_budget": 1000}, headers=h).json()["campaign_id"]
    db.set_connector(bid, "meta_ads", {"access_token": "t", "ad_account_id": "123"})
    assert client.post(f"/api/brands/{bid}/ads/meta/launch", json={"campaign_id": cid, "approve": False}, headers=h).status_code == 403


# ---------------- connections hub ----------------

def test_HUB_catalog_is_honest_and_complete():
    h = _user("admin")
    c = client.get("/api/channels/catalog", headers=h).json()
    ids = {x["id"] for x in c["channels"]}
    assert {"instagram", "facebook", "linkedin", "twitter", "youtube", "google_business", "meta_ads", "google_ads",
            "mailchimp", "smartlead", "whatsapp", "airtable", "webhook"} <= ids
    tw = next(x for x in c["channels"] if x["id"] == "twitter")
    assert tw["status"] == "manual" and any("live posting" in s for s in tw["cannot"])
    assert all(x["fields"] and x["steps"] for x in c["channels"])


def test_HUB_connect_validates_fields_and_hub_shows_status():
    bid = _brand(); h = _user("admin")
    r = client.post(f"/api/brands/{bid}/channels/connect", json={"channel": "instagram", "credentials": {"access_token": "t"}}, headers=h)
    assert r.status_code == 400 and "ig_user_id" in r.json()["detail"]
    r = client.post(f"/api/brands/{bid}/channels/connect", json={"channel": "instagram", "credentials": {"access_token": "t", "ig_user_id": "9", "_status": {"ok": True}}}, headers=h)
    assert r.status_code == 200 and "_status" not in r.json()["fields"]
    assert client.post(f"/api/brands/{bid}/channels/connect", json={"channel": "myspace", "credentials": {}}, headers=h).status_code == 400
    hub = client.get(f"/api/brands/{bid}/channels/hub", headers=h).json()
    ig = next(x for x in hub["channels"] if x["id"] == "instagram")
    assert ig["connected"] and ig["last_test"] is None and hub["connected"] == ["instagram"]
    assert hub["limits"]["max_daily_ad_budget"] == 5000


def test_HUB_test_connection_is_read_only_and_recorded(monkeypatch):
    bid = _brand(); h = _user("admin")
    db.set_connector(bid, "instagram", {"access_token": "good", "ig_user_id": "17841400000"})
    seen = []

    class R:
        status_code = 200
        headers = {"content-type": "application/json"}
        def json(self):
            return {"username": "neopolisinfra", "name": "Neopolis Infra"}

    class FakeCli:
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def get(self, url, **kw):
            seen.append(url)
            return R()
        def post(self, *a, **k):
            raise AssertionError("probe must never POST")
    monkeypatch.setattr(channel_catalog.httpx, "Client", FakeCli)
    r = client.post(f"/api/brands/{bid}/channels/instagram/test", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] and r.json()["account"] == "neopolisinfra" and "17841400000" in seen[0]
    hub = client.get(f"/api/brands/{bid}/channels/hub", headers=h).json()
    ig = next(x for x in hub["channels"] if x["id"] == "instagram")
    assert ig["last_test"]["ok"] and ig["last_test"]["account"] == "neopolisinfra"
    # the recorded status never leaks into the API credentials used for publishing
    assert db.get_connectors(bid)["instagram"]["access_token"] == "good"
    assert client.post(f"/api/brands/{bid}/channels/facebook/test", headers=h).status_code == 400
    assert client.post(f"/api/brands/{bid}/channels/nope/test", headers=h).status_code == 404


def test_HUB_test_reports_bad_token(monkeypatch):
    bid = _brand(); h = _user("admin")
    db.set_connector(bid, "meta_ads", {"access_token": "bad", "ad_account_id": "act_1", "page_id": "p"})

    class R:
        status_code = 400
        headers = {"content-type": "application/json"}
        def json(self):
            return {"error": {"message": "Invalid OAuth access token."}}

    class FakeCli:
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
        def get(self, url, **kw):
            return R()
    monkeypatch.setattr(channel_catalog.httpx, "Client", FakeCli)
    r = client.post(f"/api/brands/{bid}/channels/meta_ads/test", headers=h).json()
    assert r["ok"] is False and "Invalid OAuth" in r["detail"]


def test_HUB_disconnect_and_tenancy():
    a, c = _brand(), _brand()
    ha = _user("owner", a)
    db.set_connector(a, "facebook", {"access_token": "t", "page_id": "1"})
    db.set_connector(c, "facebook", {"access_token": "t", "page_id": "2"})
    assert client.delete(f"/api/brands/{c}/channels/facebook", headers=ha).status_code == 403
    assert client.delete(f"/api/brands/{a}/channels/facebook", headers=ha).status_code == 200
    assert "facebook" not in db.get_connectors(a) and "facebook" in db.get_connectors(c)
    cl = _user("client", a)
    db.set_connector(a, "facebook", {"access_token": "t", "page_id": "1"})
    assert client.delete(f"/api/brands/{a}/channels/facebook", headers=cl).status_code == 403


def test_HUB_manual_channel_probe_needs_no_network():
    r = channel_catalog.probe("youtube", {"channel_id": "UC123"})
    assert r["ok"] and "manual" in r["detail"]
    assert channel_catalog.probe("webhook", {"url": "http://127.0.0.1/x"})["ok"] is False


def test_PLAN_schedule_never_in_the_past_and_lookalike_not_double_wrapped():
    import time as _t
    b = db.get_brand(_brand("real_estate"))
    raw = json.loads(json.dumps(META_RAW)) if False else __import__("copy").deepcopy(META_RAW)
    raw["ad_sets"][0]["schedule"] = {"start": "2023-10-01", "end": "2023-09-01", "dayparting": "9am-10pm"}
    p = ad_planner.normalize_meta(raw, b, 1000, "INR", "OUTCOME_LEADS")
    today = _t.strftime("%Y-%m-%d")
    assert p["ad_sets"][0]["schedule"]["start"] == today and p["ad_sets"][0]["schedule"]["end"] is None
    assert p["ad_sets"][0]["schedule"]["dayparting"] == "9am-10pm"
    # an operator edit re-normalises: the Special Ad Audience wrapper must not nest
    p2 = ad_planner.apply_edit(p, {"ad_sets": p["ad_sets"]}, b, "meta")
    assert p2["ad_sets"][0]["targeting"]["lookalike"].count("Special Ad Audience") == 1

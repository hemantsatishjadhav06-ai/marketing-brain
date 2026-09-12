"""Cinematic Storyboard Film — storyboard first, video second.

The two invariants the module owns are pinned here: timecodes are recomputed
from durations (clamped) on every edit, and nothing renders until a human
approves the storyboard (and any edit re-opens that gate). AI is faked.
"""
from __future__ import annotations

import io
import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "film.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ["BG_SYNC"] = "1"
os.environ.pop("DIRECT_ACCESS", None)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.ai import engine  # noqa: E402
from app.core import auth, database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import film_studio, workspace as ws  # noqa: E402

client = TestClient(app)


def _png():
    buf = io.BytesIO(); Image.new("RGB", (108, 192), (10, 30, 80)).save(buf, "PNG"); return buf.getvalue()


STORY = {
    "title": "Direct from the landowner",
    "logline": "Why landlord-share flats cost less.",
    "hook": "Skip the broker chain.",
    "look": "warm-neutral-premium", "music": "warm ambient, 90bpm",
    "cuts": [
        {"n": 1, "duration_s": 40, "camera": "35mm dolly-in", "lighting": "golden hour", "vo_line": "Most buyers overpay.",
         "vo_tone": "calm", "on_screen_text": "Overpaying?", "visual": "keys on a table", "transition": "match cut", "negatives": "no text"},
        {"n": 2, "duration_s": 1, "camera": "wide static", "lighting": "soft", "vo_line": "We go direct.",
         "vo_tone": "confident", "on_screen_text": "", "visual": "apartment towers at dusk", "transition": "hard cut"},
        {"n": 3, "duration_s": 6, "camera": "orbit", "lighting": "key", "vo_line": "Save 8 to 14 percent.",
         "vo_tone": "warm", "on_screen_text": "8-14% less", "visual": "family on a balcony", "transition": "cross dissolve"},
    ],
    "cta_text": "Reply VISIT to see it.", "caption": "Landlord-share flats, direct.", "hashtags": ["#hyderabad", "#realestate"],
}


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    calls = {"story": [], "img": [], "vo": []}
    def story(brand, source, look, cuts, target, aspect):
        import copy
        calls["story"].append((look, cuts, target, aspect, source))
        s = copy.deepcopy(STORY); s["look"] = look; return s
    monkeypatch.setattr(engine, "film_storyboard", story)
    monkeypatch.setattr(engine, "generate_image", lambda p, *a, **k: (calls["img"].append(k.get("aspect")), _png())[-1])
    monkeypatch.setattr(engine, "generate_voiceover", lambda t, v="alloy": (calls["vo"].append((t, v)), b"RIFFwav")[-1])
    monkeypatch.setattr(engine, "brand_palette", lambda b: ["#081d4a", "#ff6600"])
    monkeypatch.delenv("GENERATION_DISABLED", raising=False)
    return calls


def _brand():
    slug = "fl" + uuid.uuid4().hex[:6]
    bid = db.create_brand("Neo " + slug, slug, "https://www.neopolisinfra.com", {}, "")
    ws.create_workspace(slug, ["instagram"])
    return bid


def _user(role, bid=""):
    uid = db.create_user(f"{role}-{uuid.uuid4().hex[:6]}@t.local", auth.hash_pw("pw12345678"), role=role, brand_id=bid)
    return {"Authorization": "Bearer " + auth.make_token(uid, role, bid)}


def _approve(bid, cid, h):
    return client.post(f"/api/brands/{bid}/creatives/{cid}/approval", json={"state": "approved", "comment": "ok"}, headers=h)


# ---------------- unit: timecodes ----------------

def test_RECOMPUTE_clamps_renumbers_and_times():
    r = film_studio.recompute([{"duration_s": 40}, {"duration_s": 1}, {"duration_s": 6}], target_seconds=30)
    cuts = r["cuts"]
    assert [c["duration_s"] for c in cuts] == [15, 3, 6]       # clamped to 3..15
    assert [c["n"] for c in cuts] == [1, 2, 3]
    assert [(c["t_in"], c["t_out"]) for c in cuts] == [(0, 15), (15, 18), (18, 24)]
    assert r["total_seconds"] == 24 and r["target_seconds"] == 30


# ---------------- plan (no render) ----------------

def test_PLAN_creates_storyboard_and_renders_nothing(_fake):
    bid = _brand(); h = _user("admin")
    r = client.post(f"/api/brands/{bid}/film/plan", json={"prompt": "why landlord-share flats cost less",
                     "look": "teal-orange-cinematic", "aspect": "9:16", "cuts": 3, "target_seconds": 24}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json(); assert d["state"] == "done" and d["status"] == "storyboard" and d["cuts"] == 3
    c = db.get_doc("creatives", d["creative_id"])
    assert c["format"] == "film" and c["payload"]["film"]["status"] == "storyboard"
    film = c["payload"]["film"]
    assert film["look"] == "teal-orange-cinematic" and film["aspect"] == "9:16"
    assert [cu["duration_s"] for cu in film["cuts"]] == [15, 3, 6] and film["total_seconds"] == 24
    assert film["cuts"][0]["t_in"] == 0 and film["cuts"][1]["t_in"] == 15
    assert not film["rendered"] and all("asset" not in cu for cu in film["cuts"])
    assert not c.get("asset_path") and _fake["img"] == [] and _fake["vo"] == []   # NOTHING rendered
    assert _fake["story"][0][0] == "teal-orange-cinematic"
    # it is a normal creative — shows in the approval queue
    assert any(i["id"] == d["creative_id"] for i in client.get("/api/approvals", headers=h).json()["waiting_for_approval"])


def test_PLAN_needs_a_brief_and_blocks_client():
    bid = _brand(); h = _user("admin")
    assert client.post(f"/api/brands/{bid}/film/plan", json={"prompt": "hi"}, headers=h).status_code == 400
    ch = _user("client", bid)
    assert client.post(f"/api/brands/{bid}/film/plan", json={"prompt": "a proper film brief here"}, headers=ch).status_code == 403


# ---------------- edit re-opens the gate ----------------

def _plan(bid, h):
    return client.post(f"/api/brands/{bid}/film/plan", json={"prompt": "landlord share flats film", "cuts": 3}, headers=h).json()["creative_id"]


def test_EDIT_recomputes_and_clears_approval(_fake):
    bid = _brand(); h = _user("admin")
    cid = _plan(bid, h)
    assert _approve(bid, cid, h).status_code == 200
    assert db.get_doc("creatives", cid)["payload"]["approval"]["state"] == "approved"
    r = client.put(f"/api/brands/{bid}/film/{cid}/cut/0", json={"duration_s": 9, "vo_line": "New opening line"}, headers=h)
    assert r.status_code == 200
    film = r.json()["film"]
    assert film["cuts"][0]["duration_s"] == 9 and film["cuts"][0]["vo_line"] == "New opening line"
    assert film["cuts"][1]["t_in"] == 9   # timeline shifted
    assert db.get_doc("creatives", cid)["payload"].get("approval") is None   # edit re-opens the gate


def test_REORDER_and_add_remove(_fake):
    bid = _brand(); h = _user("admin")
    cid = _plan(bid, h)
    r = client.post(f"/api/brands/{bid}/film/{cid}/reorder", json={"order": [2, 0, 1]}, headers=h)
    assert r.status_code == 200 and [c["n"] for c in r.json()["film"]["cuts"]] == [1, 2, 3]
    assert r.json()["film"]["cuts"][0]["vo_line"] == "Save 8 to 14 percent."   # 3rd cut moved to front
    assert client.post(f"/api/brands/{bid}/film/{cid}/reorder", json={"order": [0, 1]}, headers=h).status_code == 400
    r = client.post(f"/api/brands/{bid}/film/{cid}/cut?after=0", headers=h)
    assert r.status_code == 200 and len(r.json()["film"]["cuts"]) == 4
    r = client.request("DELETE", f"/api/brands/{bid}/film/{cid}/cut/3", headers=h)
    assert r.status_code == 200 and len(r.json()["film"]["cuts"]) == 3


# ---------------- render gate ----------------

def test_RENDER_blocked_until_approved_then_generates(_fake):
    bid = _brand(); h = _user("admin")
    cid = _plan(bid, h)
    assert client.post(f"/api/brands/{bid}/film/{cid}/render", headers=h).status_code == 400   # not approved
    assert _fake["img"] == []
    _approve(bid, cid, h)
    r = client.post(f"/api/brands/{bid}/film/{cid}/render", headers=h)
    assert r.status_code == 200, r.text
    d = r.json(); assert d["state"] == "done" and d["status"] == "rendered" and d["frames"] == 3
    assert _fake["img"] == ["9:16", "9:16", "9:16"] and len(_fake["vo"]) == 1   # every frame at the film aspect + one VO
    c = db.get_doc("creatives", cid)
    film = c["payload"]["film"]
    assert film["rendered"] and film["status"] == "rendered" and all(cu.get("asset") for cu in film["cuts"])
    assert c.get("asset_path") and film.get("vo_asset")
    # editing after render clears it and re-requires approval before another render
    client.put(f"/api/brands/{bid}/film/{cid}/cut/0", json={"visual": "new frame"}, headers=h)
    assert db.get_doc("creatives", cid)["payload"]["film"]["rendered"] is False
    assert client.post(f"/api/brands/{bid}/film/{cid}/render", headers=h).status_code == 400


def test_RENDER_respects_kill_switch(_fake, monkeypatch):
    bid = _brand(); h = _user("admin")
    cid = _plan(bid, h); _approve(bid, cid, h)
    monkeypatch.setenv("GENERATION_DISABLED", "1")
    r = client.post(f"/api/brands/{bid}/film/{cid}/render", headers=h)
    assert r.status_code == 429 or (r.status_code == 200 and r.json().get("frames", 0) == 0)


# ---------------- routes / tenancy ----------------

def test_OPTIONS_and_get_and_list(_fake):
    bid = _brand(); h = _user("admin")
    o = client.get("/api/film-studio/options", headers=h).json()
    assert {"warm-neutral-premium", "teal-orange-cinematic"} <= {x["id"] for x in o["looks"]}
    assert "9:16" in o["aspects"] and o["voices"] and o["limits"]["max_cuts"] == 12
    cid = _plan(bid, h)
    g = client.get(f"/api/brands/{bid}/film/{cid}", headers=h).json()
    assert g["film"]["status"] == "storyboard" and g["summary"] and g["editable"] is True
    lst = client.get(f"/api/brands/{bid}/films", headers=h).json()
    assert any(x["id"] == cid and x["status"] == "storyboard" for x in lst)


def test_TENANCY_and_client_readonly(_fake):
    a = _brand(); other = _brand(); h = _user("admin")
    cid = _plan(a, h)
    ch = _user("client", a)
    assert client.get(f"/api/brands/{a}/film/{cid}", headers=ch).status_code == 200          # client can review
    assert client.get(f"/api/brands/{a}/film/{cid}", headers=ch).json()["editable"] is False
    assert client.put(f"/api/brands/{a}/film/{cid}/cut/0", json={"vo_line": "x"}, headers=ch).status_code == 403
    assert client.post(f"/api/brands/{a}/film/{cid}/render", headers=ch).status_code == 403
    # a client may still approve (the review gate) — that route already allows it
    assert client.post(f"/api/brands/{a}/creatives/{cid}/approval", json={"state": "approved"}, headers=ch).status_code == 200
    # other brand cannot see it
    hb = _user("owner", other)
    assert client.get(f"/api/brands/{other}/film/{cid}", headers=hb).status_code == 404

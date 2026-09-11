"""Design QA — the art director that reviews and fixes visuals.

Mechanical checks are facts (ratio, resolution, blank frames) and get mechanical
fixes; the vision review is faked here and drives the regenerate-once loop.
"""
from __future__ import annotations

import io
import os
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "dqa.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ.pop("DIRECT_ACCESS", None)

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.ai import engine  # noqa: E402
from app.core import auth, database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import design_qa, workspace as ws  # noqa: E402

client = TestClient(app)


def png(w, h, color=(200, 90, 30)):
    buf = io.BytesIO(); Image.new("RGB", (w, h), color).save(buf, "PNG"); return buf.getvalue()


def _brand():
    slug = "dq" + uuid.uuid4().hex[:6]
    bid = db.create_brand("DQ " + slug, slug, "", {}, "")
    ws.create_workspace(slug, ["instagram"])
    return db.get_brand(bid)


def _creative(b, blob, fmt="post", channel="instagram"):
    cid = db.insert_doc("creatives", b["id"], {"title": "T", "caption": "Buy flats", "format": fmt, "image_prompt": "flats at dusk"},
                        channel=channel, format=fmt)
    rel = f"{channel}/assets/{cid}.png"
    ws.write_bytes(b["slug"], rel, blob)
    db.update_doc("creatives", cid, asset_path=rel)
    return db.get_doc("creatives", cid)


def _admin():
    uid = db.create_user(f"a-{uuid.uuid4().hex[:6]}@t.local", auth.hash_pw("pw12345678"), role="admin")
    return {"Authorization": "Bearer " + auth.make_token(uid, "admin", "")}


@pytest.fixture
def vision(monkeypatch):
    calls = {"n": 0, "score": 90, "regen": False}

    def fake(system, user, blob, **k):
        calls["n"] += 1
        return {"score": calls["score"], "verdict": "fine", "issues": [{"area": "text", "severity": "low", "problem": "p", "fix": "f"}],
                "regenerate": calls["regen"], "revised_image_prompt": "better prompt, no text",
                "text_in_image": {"present": False}, "logo": {"visible": True, "placement_ok": True}}
    monkeypatch.setattr(engine, "_json_chat_vision", fake)
    monkeypatch.setattr(engine, "generate_image", lambda *a, **k: png(1080, 1350, (10, 30, 80)))
    return calls


def test_CHECKS_ratio_and_resolution():
    f = design_qa.checks(png(1600, 900), "instagram", "post")
    assert "crop_to_target" in f["fixes"] and "upscale" in f["fixes"] and f["target"] == [1080, 1350]
    ok = design_qa.checks(png(1080, 1350), "instagram", "post")
    assert ok["issues"] == []
    assert design_qa.target_for("instagram", "reel") == (1080, 1920) and design_qa.target_for("linkedin", "post") == (1200, 1200)


def test_CROP_never_stretches():
    out = design_qa.crop_to_target(png(1600, 900), "instagram", "post")
    im = Image.open(io.BytesIO(out))
    assert im.size == (1080, 1350)
    out2 = design_qa.crop_to_target(png(1000, 3000), "instagram", "reel")
    assert Image.open(io.BytesIO(out2)).size == (1080, 1920)


def test_REVIEW_caps_score_when_mechanics_fail(vision):
    b = _brand(); c = _creative(b, png(1600, 900))
    rv = design_qa.review(b, c)
    assert rv["ok"] and rv["score"] == 74 and any(i["area"] == "quality" for i in rv["issues"])
    assert vision["n"] == 1


def test_FIX_mechanical_only_when_score_is_good(vision):
    b = _brand(); c = _creative(b, png(1600, 900))
    out = design_qa.fix(b, c)
    assert out["ok"] and "cropped/resized to the platform ratio" in out["applied"]
    assert out["after"]["asset"].endswith("-qa.png") and out["after"]["score"] == 90
    c2 = db.get_doc("creatives", c["id"])
    assert c2["asset_path"].endswith("-qa.png") and c2["payload"]["design_qa"]["publish_ready"]
    assert c2["payload"]["asset_history"][0]["asset"] == c["asset_path"]
    assert Image.open(io.BytesIO(design_qa.load_asset(b, c2["asset_path"]))).size == (1080, 1350)
    assert out["regen"] is None


def test_FIX_regenerates_once_when_score_low_and_keeps_better(vision, monkeypatch):
    b = _brand(); c = _creative(b, png(1080, 1350))
    scores = iter([50, 88])  # first review low, review of the regenerated image high
    monkeypatch.setattr(engine, "_json_chat_vision", lambda s, u, blob, **k: {"score": next(scores), "verdict": "v", "issues": [],
                                                                               "regenerate": True, "revised_image_prompt": "np"})
    out = design_qa.fix(b, c)
    assert out["ok"] and "regenerated with the revised art direction" in out["applied"]
    assert out["before"]["score"] is None or out["before"]["score"] == 50
    assert out["after"]["score"] == 88 and out["regen"]["score"] == 88
    assert db.get_doc("creatives", c["id"])["payload"]["design_qa"]["publish_ready"]


def test_FIX_keeps_original_when_regeneration_is_worse(vision, monkeypatch):
    b = _brand(); c = _creative(b, png(1080, 1350))
    scores = iter([70, 40])
    monkeypatch.setattr(engine, "_json_chat_vision", lambda s, u, blob, **k: {"score": next(scores), "verdict": "v", "issues": [],
                                                                               "regenerate": True, "revised_image_prompt": "np"})
    out = design_qa.fix(b, c)
    assert "kept the previous version" in " ".join(out["applied"])
    assert db.get_doc("creatives", c["id"])["asset_path"] == c["asset_path"]
    assert out["publish_ready"] is False


def test_ROUTES_review_and_fix(vision):
    b = _brand(); c = _creative(b, png(1600, 900)); h = _admin()
    r = client.post(f"/api/brands/{b['id']}/creatives/{c['id']}/design-review", headers=h)
    assert r.status_code == 200 and r.json()["score"] == 74
    assert db.get_doc("creatives", c["id"])["payload"]["design_review"]["score"] == 74
    r = client.post(f"/api/brands/{b['id']}/creatives/{c['id']}/design-fix", headers=h)
    assert r.status_code == 200 and r.json()["applied"]
    # no visual → 400; other brand's creative → 404
    bare = db.insert_doc("creatives", b["id"], {"title": "x"}, channel="instagram", format="post")
    assert client.post(f"/api/brands/{b['id']}/creatives/{bare}/design-review", headers=h).status_code == 400
    b2 = _brand()
    assert client.post(f"/api/brands/{b2['id']}/creatives/{c['id']}/design-fix", headers=h).status_code == 404


def test_REVIEW_survives_vision_outage(monkeypatch):
    b = _brand(); c = _creative(b, png(1080, 1350))
    monkeypatch.setattr(engine, "_json_chat_vision", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    rv = design_qa.review(b, c)
    assert rv["ok"] and rv["score"] is None and "unavailable" in rv["verdict"]

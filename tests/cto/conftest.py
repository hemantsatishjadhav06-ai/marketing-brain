"""Shared fixtures for the CTO test mandate.

Rules enforced here (no exceptions):
  * authentication is ON — DIRECT_ACCESS / AUTH_DEV_TOKENS are stripped for every test;
  * no real network: httpx.Client is replaced by a class that raises, DNS is blocked,
    and every AI entry point (engine._chat/_json_chat/generate_image/generate_voiceover,
    brain.fal_image/fal_video/fal_voice) is replaced by a recording fake;
  * the DB is whatever DB_PATH points at (the runner exports a fresh temp file).
"""
from __future__ import annotations

import ipaddress
import io
import json
import os
import socket
import tempfile
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "cto_test.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
for _v in ("DIRECT_ACCESS", "AUTH_DEV_TOKENS"):
    os.environ.pop(_v, None)

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.ai import brain, engine  # noqa: E402
from app.core import auth, database as db, guard  # noqa: E402
from app.main import app  # noqa: E402
from app.services import onboarding  # noqa: E402

# Real AI entry points captured BEFORE any fixture patches them — used by the
# kill-switch tests, which must exercise the real guard (they raise before I/O).
REAL_CHAT, REAL_JSON_CHAT, REAL_GENERATE_IMAGE = engine._chat, engine._json_chat, engine.generate_image

client = TestClient(app)
# A second client that surfaces 500s as status codes instead of re-raising —
# used only where the test is *about* how the server fails.
client_no_raise = TestClient(app, raise_server_exceptions=False)


CTO_PREFIXES = ("AUTH", "AUTHZ", "TENANT", "IDOR", "APPROVAL", "PUBLISH", "IDEMP", "STATE", "RACE",
                "AUTOPILOT", "API", "SEC", "PI", "DB", "JOBS")


def pytest_configure(config):
    config.addinivalue_line("markers", "defect: asserts the secure/correct behaviour and FAILS today — documents an open defect")
    # CTO naming convention: <CATEGORY>_<what_is_asserted>, no test_ prefix.
    for p in CTO_PREFIXES:
        config.addinivalue_line("python_functions", p + "_*")


# --------------------------------------------------------------------------- helpers

def u():
    return uuid.uuid4().hex[:8]


def hdr(token):
    return {"Authorization": "Bearer " + token}


def make_admin():
    email = f"admin+{u()}@cto.test"
    uid = db.create_user(email, auth.hash_pw("adminsecret1"), role="admin")
    return {"uid": uid, "email": email, "password": "adminsecret1",
            "token": auth.make_token(uid, "admin", "")}


def signup_org(name, website="https://example.invalid"):
    """Create a company + owner through the real onboarding service (no HTTP gate)."""
    email = f"owner+{u()}@cto.test"
    d = onboarding.signup(name + " " + u(), website, email, "ownersecret1")
    d["password"] = "ownersecret1"
    d["brand"] = db.get_brand(d["brand_id"])
    return d


def make_client_user(bid):
    email = f"client+{u()}@cto.test"
    uid = db.create_user(email, auth.hash_pw("clientsecret1"), role="client", brand_id=bid)
    return {"uid": uid, "email": email, "password": "clientsecret1",
            "token": auth.make_token(uid, "client", bid)}


def seed_creative(bid, approved=False, **payload_extra):
    payload = {"title": "Seeded creative", "format": "post", "caption": "hello world",
               "hashtags": {"broad": ["a"]}}
    payload.update(payload_extra)
    if approved:
        payload["approval"] = {"state": "approved", "comment": "", "by": "seed", "role": "admin", "at": 0}
    return db.insert_doc("creatives", bid, payload, channel="instagram", format="post")


def seed_idea(bid, **payload_extra):
    payload = {"title": "Seeded idea", "format": "post", "hook": "h", "concept": "c"}
    payload.update(payload_extra)
    return db.insert_doc("ideas", bid, payload, channel="instagram")


def png_bytes(size=(64, 64)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- fixtures

@pytest.fixture(autouse=True)
def _auth_enforced(monkeypatch):
    for v in ("DIRECT_ACCESS", "AUTH_DEV_TOKENS", "OPENROUTER_API_KEY", "FAL_KEY", "PUBLIC_WORKSPACES",
              "SIGNUPS_OPEN", "GENERATION_DISABLED", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    guard._hits.clear()
    yield
    guard._hits.clear()


class _BlockedHttpx:
    def __init__(self, *a, **k):
        raise AssertionError("TEST VIOLATION: a real network call was attempted via httpx.Client")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _BlockedHttpx)
    real = socket.getaddrinfo

    def fake_getaddrinfo(host, *a, **k):
        try:
            ipaddress.ip_address(host)
        except ValueError:
            raise socket.gaierror("DNS is blocked in tests")
        return real(host, *a, **k)  # IP literal: no DNS query

    monkeypatch.setattr(guard.socket, "getaddrinfo", fake_getaddrinfo)


FAKE_JSON = {
    "ideas": [
        {"title": f"Idea {n}", "format": "post", "hook": "h", "concept": "c", "pillar": "p",
         "funnel_stage": "awareness", "effort": "low", "why_it_works": "w", "cta": "c",
         "virality": {"score": 50}} for n in range(1, 5)
    ],
    "calendar": [
        {"idea_id": None, "channel": "instagram", "date": "2030-01-0%d" % n, "time": "10:00",
         "title": f"Slot {n}", "format": "post", "notes": "n"} for n in range(1, 4)
    ],
    "title": "Fake creative", "format": "post", "caption": "fake caption", "cta": "cta",
    "hashtags": {"broad": ["fake"]}, "image_prompt": "fake prompt",
    "copy_variants": [{"variant": "A", "text": "a"}],
    "hook": "hook", "cta_text": "cta", "scenes": [
        {"n": 1, "vo_line": "v", "on_screen_text": "t", "image_prompt": "p"},
        {"n": 2, "vo_line": "v", "on_screen_text": "t", "image_prompt": "p"},
        {"n": 3, "vo_line": "v", "on_screen_text": "t", "image_prompt": "p"},
    ],
    "one_move_this_month": "m", "gaps_we_can_own": [],
    "score": 42, "breakdown": {}, "verdict": "meh",
    "reply": "ok",
}


class AIRecorder:
    """Records every prompt that would have reached a model."""

    def __init__(self):
        self.chat_calls = []      # list of message lists
        self.json_calls = []      # list of (system, user)
        self.image_calls = []
        self.voice_calls = []
        self.fal_calls = []
        self.image_result = png_bytes()

    def _chat(self, messages, *a, **k):
        self.chat_calls.append(messages)
        return "agent prose"

    def _json_chat(self, system, user, *a, **k):
        self.json_calls.append((system, user))
        return json.loads(json.dumps(FAKE_JSON))

    def generate_image(self, prompt, *a, **k):
        self.image_calls.append(prompt)
        return self.image_result

    def generate_voiceover(self, text, *a, **k):
        self.voice_calls.append(text)
        return b"RIFF\x00\x00\x00\x00WAVEfake"

    def fal_image(self, prompt, **kw):
        self.fal_calls.append(("image", prompt, kw))
        return "https://fal.invalid/asset.png"

    def fal_video(self, prompt, **kw):
        self.fal_calls.append(("video", prompt, kw))
        return "https://fal.invalid/video.mp4"

    def fal_voice(self, text, **kw):
        self.fal_calls.append(("voice", text, kw))
        return "https://fal.invalid/voice.mp3"

    def all_text(self):
        out = []
        for msgs in self.chat_calls:
            out.extend(m["content"] for m in msgs)
        for s, us in self.json_calls:
            out += [s, us]
        return out


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    rec = AIRecorder()
    monkeypatch.setattr(engine, "_chat", rec._chat)
    monkeypatch.setattr(engine, "_json_chat", rec._json_chat)
    monkeypatch.setattr(engine, "generate_image", rec.generate_image)
    monkeypatch.setattr(engine, "generate_voiceover", rec.generate_voiceover)
    monkeypatch.setattr(brain, "fal_image", rec.fal_image)
    monkeypatch.setattr(brain, "fal_video", rec.fal_video)
    monkeypatch.setattr(brain, "fal_voice", rec.fal_voice)
    return rec


@pytest.fixture
def admin():
    return make_admin()


@pytest.fixture
def org_a():
    return signup_org("Neopolis Realty")


@pytest.fixture
def org_b():
    return signup_org("BrightSmile Dental Clinic")
